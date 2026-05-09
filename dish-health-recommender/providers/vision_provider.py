from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from local_config import get_secret, local_secret_hint
from .ocr_provider import recognize_image_text

LOW_VALUE_EXACT_CANDIDATES = {
    '非菜', '其他', '未知', '行政', '清真菜单', '特色档口菜单', '档口位置',
    '配菜：', '主荤', '半荤', '素菜', '例汤', '主食', '粗粮', '小吃',
}
LOW_VALUE_SUBSTRINGS = [
    'administration', '档口', '位置', '菜单', '四选一', '三选一', '件套',
    '配餐', '饮料', '小食', '永远好滋味', 'hot wings', 'french fries',
    'pepsi', 'cola', 'lemon tea', 'egg tart', 'potato', 'gravy',
]
DISH_NAME_HINTS = ['饭', '面', '汤', '粉', '鱼', '虾', '鸡', '肉', '菜', '饺', '馄饨', '堡', '豆腐', '肠粉', '手抓饭', '烤翅', '鸡翅', '鸡腿', '牛肚', '牛肉']
BAIDU_TOKEN_URL = 'https://aip.baidubce.com/oauth/2.0/token'
BAIDU_DISH_URL = 'https://aip.baidubce.com/rest/2.0/image-classify/v2/dish'


@dataclass
class VisionResult:
    provider_name: str
    status: str
    latency_ms: int
    candidates: list[str]
    raw_result: dict
    error_message: str = ''
    credential_hint: str = ''
    degrade_strategy: str = ''

    def to_dict(self) -> dict:
        return asdict(self)


def _clean_candidate(candidate: str) -> str:
    cleaned = candidate.strip().strip('•·').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned


def _is_low_value_candidate(candidate: str) -> bool:
    normalized = _clean_candidate(candidate)
    if not normalized:
        return True
    lowered = normalized.lower()
    if normalized in LOW_VALUE_EXACT_CANDIDATES:
        return True
    if any(token in lowered for token in LOW_VALUE_SUBSTRINGS):
        return True
    if any(token in normalized for token in {'@', '◎'}):
        return True
    if re.fullmatch(r'[0-9A-Za-z@◎+\-_/(). ]+', normalized):
        return True
    if not re.search(r'[一-鿿]{2,}', normalized):
        return True
    if len(normalized) <= 2 and normalized not in {'豆浆', '豆花'}:
        return True
    if not any(hint in normalized for hint in DISH_NAME_HINTS) and len(normalized) <= 5:
        return True
    if not any(hint in normalized for hint in DISH_NAME_HINTS) and any(word in normalized for word in ['菜单', '档口', '位置', '配菜']):
        return True
    return False


def _is_low_value_candidate_list(candidates: list[str]) -> bool:
    if not candidates:
        return True
    normalized = [_clean_candidate(c) for c in candidates if _clean_candidate(c)]
    if not normalized:
        return True
    return all(_is_low_value_candidate(item) for item in normalized)


class OCRAssistedVisionProvider:
    provider_name = 'ocr_assisted_vision'

    def detect(self, image_path: str) -> VisionResult:
        start = time.time()
        ocr = recognize_image_text(image_path)
        lines = ocr.lines or []
        candidates = []
        for line in lines:
            cleaned = _clean_candidate(line)
            if not cleaned or _is_low_value_candidate(cleaned):
                continue
            candidates.append(cleaned)
        unique = []
        for item in candidates:
            if item not in unique:
                unique.append(item)
        status = 'validated' if unique else 'degraded'
        return VisionResult(
            self.provider_name,
            status,
            int((time.time() - start) * 1000),
            unique[:8],
            {'ocr_provider': ocr.provider_name, 'ocr_status': ocr.status},
            ocr.error_message,
            '',
            'use OCR text / manual review',
        )


class BaiduDishRecognitionProvider:
    provider_name = 'baidu_dish_recognition'

    def _get_access_token(self) -> str:
        api_key = get_secret('BAIDU_API_KEY')
        secret_key = get_secret('BAIDU_SECRET_KEY')
        if not api_key or not secret_key:
            raise RuntimeError('missing BAIDU_API_KEY or BAIDU_SECRET_KEY')
        params = urllib.parse.urlencode({
            'grant_type': 'client_credentials',
            'client_id': api_key,
            'client_secret': secret_key,
        })
        with urllib.request.urlopen(f'{BAIDU_TOKEN_URL}?{params}', timeout=12) as response:
            raw = json.loads(response.read().decode('utf-8'))
        token = raw.get('access_token', '')
        if not token:
            raise RuntimeError(f'baidu token fetch failed: {raw}')
        return token

    def detect(self, image_path: str) -> VisionResult:
        start = time.time()
        try:
            token = self._get_access_token()
        except Exception as exc:
            if 'missing BAIDU_API_KEY or BAIDU_SECRET_KEY' in str(exc):
                return VisionResult(self.provider_name, 'needs_credentials', int((time.time() - start) * 1000), [], {}, str(exc), local_secret_hint('BAIDU_API_KEY', 'BAIDU_SECRET_KEY'), 'fallback to OCR-assisted vision')
            return VisionResult(self.provider_name, 'degraded', int((time.time() - start) * 1000), [], {}, str(exc), '', 'fallback to OCR-assisted vision')
        try:
            image_bytes = Path(image_path).read_bytes()
            encoded = base64.b64encode(image_bytes).decode('utf-8')
            body = urllib.parse.urlencode({'image': encoded, 'top_num': 5}).encode('utf-8')
            req = urllib.request.Request(f'{BAIDU_DISH_URL}?access_token={token}', data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = json.loads(response.read().decode('utf-8'))
            result_items = raw.get('result', []) or []
            candidates = [cleaned for item in result_items if (cleaned := _clean_candidate(item.get('name', ''))) and not _is_low_value_candidate(cleaned)]
            status = 'validated' if candidates else 'degraded'
            return VisionResult(self.provider_name, status, int((time.time() - start) * 1000), candidates[:8], raw, '', '', 'fallback to OCR-assisted vision')
        except Exception as exc:
            return VisionResult(self.provider_name, 'degraded', int((time.time() - start) * 1000), [], {}, str(exc), '', 'fallback to OCR-assisted vision')


def get_vision_providers():
    return [BaiduDishRecognitionProvider(), OCRAssistedVisionProvider()]


def detect_dish_candidates(image_path: str) -> VisionResult:
    results = [provider.detect(image_path) for provider in get_vision_providers()]
    for result in results:
        result.candidates = [_clean_candidate(item) for item in result.candidates if not _is_low_value_candidate(item)][:8]
        if result.status == 'validated' and result.candidates and not _is_low_value_candidate_list(result.candidates):
            return result
    for result in results:
        if result.status == 'validated' and result.candidates:
            return result
    return results[0]
