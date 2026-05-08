from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
QUANTIFIED_RECIPES_PATH = SKILL_DIR / 'data' / 'quantified_recipes.json'
COOKBOOK_KG_URL = 'https://raw.githubusercontent.com/ngl567/CookBook-KG/master/visualization/vizdata.json'
USDA_SEARCH_URL = 'https://api.nal.usda.gov/fdc/v1/foods/search?query=tomato&api_key=DEMO_KEY&pageSize=1'


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


class QuantifiedRecipeProvider:
    provider_name = 'local_quantified_recipes'

    def load(self) -> dict[str, Any]:
        if not QUANTIFIED_RECIPES_PATH.exists():
            return {'recipes': []}
        return json.loads(QUANTIFIED_RECIPES_PATH.read_text(encoding='utf-8'))

    def find(self, dish_name: str) -> dict[str, Any] | None:
        data = self.load()
        for item in data.get('recipes', []):
            names = [item.get('dish_name', '')] + list(item.get('aliases', []))
            if any(name and (name == dish_name or name in dish_name or dish_name in name) for name in names):
                return item
        return None


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


def validate_all_providers() -> list[dict[str, Any]]:
    return [
        validate_cookbook_kg().to_dict(),
        validate_usda().to_dict(),
    ]
