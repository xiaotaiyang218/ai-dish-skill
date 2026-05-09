from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from local_config import get_secret, local_secret_hint

SKILL_DIR = Path(__file__).resolve().parents[1]
QUANTIFIED_RECIPES_PATH = SKILL_DIR / 'data' / 'quantified_recipes.json'
COOKBOOK_KG_URL = 'https://raw.githubusercontent.com/ngl567/CookBook-KG/master/visualization/vizdata.json'
XIA_CHU_FANG_SEARCH_URL = 'https://www.xiachufang.com/search/?keyword=%E7%BA%A2%E7%83%A7%E8%82%89&cat=1001&via=home'
DOU_GUO_SEARCH_URL = 'https://www.douguo.com/caipu/%E7%BA%A2%E7%83%A7%E8%82%89'
XIANG_HA_SEARCH_URL = 'https://www.xiangha.com/so/?s=%E7%BA%A2%E7%83%A7%E8%82%89'
SPOONACULAR_COMPLEX_SEARCH_URL = 'https://api.spoonacular.com/recipes/complexSearch'
USDA_SEARCH_URL = 'https://api.nal.usda.gov/fdc/v1/foods/search?query=tomato&api_key=DEMO_KEY&pageSize=1'
SOURCE_MANIFEST_PATH = SKILL_DIR / 'data' / 'source_manifest.json'


@dataclass
class ApiValidationRecord:
    provider_name: str
    provider_type: str
    status: str
    request_sample: dict[str, Any]
    response_sample: dict[str, Any]
    error_message: str = ''
    latency_ms: int = 0
    credential_hint: str = ''
    degrade_strategy: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_source_manifest() -> dict[str, Any]:
    if not SOURCE_MANIFEST_PATH.exists():
        return {'sources': []}
    return json.loads(SOURCE_MANIFEST_PATH.read_text(encoding='utf-8'))


class QuantifiedRecipeProvider:
    provider_name = 'local_quantified_recipes'

    def load(self) -> dict[str, Any]:
        if not QUANTIFIED_RECIPES_PATH.exists():
            return {'recipes': []}
        return json.loads(QUANTIFIED_RECIPES_PATH.read_text(encoding='utf-8'))

    def find(self, dish_name: str) -> dict[str, Any] | None:
        query = str(dish_name or '').strip()
        if not query:
            return None
        data = self.load()
        exact_match = None
        fuzzy_match = None
        for item in data.get('recipes', []):
            canonical = str(item.get('dish_name', '')).strip()
            aliases = [str(alias).strip() for alias in item.get('aliases', []) if str(alias).strip()]
            names = [canonical] + aliases
            if query in names:
                return item
            if any(name and (query in name or name in query) for name in names):
                if canonical == query:
                    exact_match = item
                elif fuzzy_match is None:
                    fuzzy_match = item
        return exact_match or fuzzy_match


def validate_cookbook_kg() -> ApiValidationRecord:
    start = time.time()
    try:
        with urllib.request.urlopen(COOKBOOK_KG_URL, timeout=8) as response:
            raw = json.loads(response.read().decode('utf-8'))
        sample = {'nodes': len(raw.get('nodes', [])), 'links': len(raw.get('links', []))}
        return ApiValidationRecord('CookBook-KG', 'fallback', 'validated', {'url': COOKBOOK_KG_URL}, sample, latency_ms=int((time.time() - start) * 1000))
    except Exception as exc:
        return ApiValidationRecord('CookBook-KG', 'fallback', 'degraded', {'url': COOKBOOK_KG_URL}, {}, str(exc), int((time.time() - start) * 1000), degrade_strategy='use local dishes.json only')


def validate_usda() -> ApiValidationRecord:
    start = time.time()
    try:
        with urllib.request.urlopen(USDA_SEARCH_URL, timeout=8) as response:
            raw = json.loads(response.read().decode('utf-8'))
        sample = {'foods': len(raw.get('foods', []))}
        return ApiValidationRecord('USDA_FDC', 'fallback', 'validated', {'url': USDA_SEARCH_URL}, sample, latency_ms=int((time.time() - start) * 1000))
    except Exception as exc:
        return ApiValidationRecord('USDA_FDC', 'fallback', 'degraded', {'url': USDA_SEARCH_URL}, {}, str(exc), int((time.time() - start) * 1000), degrade_strategy='use local nutrition_knowledge.json only')


def validate_search_provider(name: str, url: str, provider_type: str = 'reference') -> ApiValidationRecord:
    start = time.time()
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36', 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}
    if name == 'douguo':
        headers.update({'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1', 'Referer': 'https://m.douguo.com/'})
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode('utf-8', 'ignore')
        sample = {
            'matched_titles': len(re.findall(r'/recipe/\d+/|/cookbook/\d+\.html|/caipu/\d+\.html', body)),
        }
        return ApiValidationRecord(name, provider_type, 'validated', {'url': url, 'method': 'GET'}, sample, latency_ms=int((time.time() - start) * 1000), degrade_strategy='skip online search provider and keep local-first fallback chain')
    except Exception as exc:
        return ApiValidationRecord(name, provider_type, 'degraded', {'url': url, 'method': 'GET'}, {}, str(exc), int((time.time() - start) * 1000), degrade_strategy='skip online search provider and keep local-first fallback chain')


def validate_spoonacular() -> ApiValidationRecord:
    api_key = get_secret('SPOONACULAR_API_KEY')
    if not api_key:
        return ApiValidationRecord(
            'Spoonacular',
            'reference',
            'needs_credentials',
            {'url': SPOONACULAR_COMPLEX_SEARCH_URL},
            {},
            credential_hint=local_secret_hint('SPOONACULAR_API_KEY'),
            degrade_strategy='skip Spoonacular and keep local-first fallback chain',
        )
    start = time.time()
    params = urllib.parse.urlencode({
        'query': 'tomato soup',
        'number': 1,
        'addRecipeInformation': 'true',
        'fillIngredients': 'true',
        'apiKey': api_key,
    })
    request_url = f'{SPOONACULAR_COMPLEX_SEARCH_URL}?{params}'
    request = urllib.request.Request(request_url, headers={'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = json.loads(response.read().decode('utf-8'))
        sample = {'results': len(raw.get('results', []))}
        return ApiValidationRecord('Spoonacular', 'reference', 'validated', {'url': request_url}, sample, latency_ms=int((time.time() - start) * 1000), credential_hint='SPOONACULAR_API_KEY')
    except Exception as exc:
        return ApiValidationRecord('Spoonacular', 'reference', 'degraded', {'url': request_url}, {}, str(exc), int((time.time() - start) * 1000), credential_hint='SPOONACULAR_API_KEY', degrade_strategy='skip Spoonacular and keep local-first fallback chain')


def validate_all_providers() -> list[dict[str, Any]]:
    manifest = load_source_manifest()
    runtime_enabled_sources = [
        source for source in manifest.get('sources', [])
        if source.get('enabled_for_runtime')
    ]
    records = [
        validate_cookbook_kg().to_dict(),
        validate_search_provider('xiachufang', XIA_CHU_FANG_SEARCH_URL).to_dict(),
        validate_search_provider('douguo', DOU_GUO_SEARCH_URL).to_dict(),
        validate_search_provider('xiangha', XIANG_HA_SEARCH_URL).to_dict(),
        validate_spoonacular().to_dict(),
        validate_usda().to_dict(),
    ]
    for record in records:
        record['runtime_mode'] = 'local_snapshot_first'
        record['runtime_enabled_sources'] = [source.get('name') for source in runtime_enabled_sources]
    return records
