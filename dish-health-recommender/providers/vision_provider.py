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

from .ocr_provider import recognize_image_text

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


class OCRAssistedVisionProvider:
    provider_name = 'ocr_assisted_vision'

    def detect(self, image_path: str) -> VisionResult:
        start = time.time()
        ocr = recognize_image_text(image_path)
        lines = ocr.lines or []
        candidates = []
        for line in lines:
            if re.search(r'[\u4e00-\u9fff]{2,}', line) and 'Administration' not in line and '行政' not in line and '特色档口菜单' not in line:
                candidates.append(line)
        unique = []
        for item in candidates:
            if item not in unique:
                unique.append(item)
        status = 'validated' if unique else 'degraded'
        return VisionResult(self.provider_name, status, int((time.time() - start) * 1000), unique[:8], {'ocr_provider': ocr.provider_name, 'ocr_status': ocr.status}, ocr.error_message, '', 'use OCR text / manual review')


class BaiduDishRecognitionProvider:
    provider_name = 'baidu_dish_recognition'

    def _get_access_token(self) -> str:
        api_key = os.getenv('BAIDU_API_KEY', '')
        secret_key = os.getenv('BAIDU_SECRET_KEY', '')
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
                return VisionResult(self.provider_name, 'needs_credentials', int((time.time() - start) * 1000), [], {}, str(exc), 'set BAIDU_API_KEY and BAIDU_SECRET_KEY', 'fallback to OCR-assisted vision')
            return VisionResult(self.provider_name, 'degraded', int((time.time() - start) * 1000), [], {}, str(exc), '', 'fallback to OCR-assisted vision')
        try:
            image_bytes = Path(image_path).read_bytes()
            encoded = base64.b64encode(image_bytes).decode('utf-8')
            body = urllib.parse.urlencode({'image': encoded, 'top_num': 5}).encode('utf-8')
            req = urllib.request.Request(f'{BAIDU_DISH_URL}?access_token={token}', data=body, headers={'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=15) as response:
                raw = json.loads(response.read().decode('utf-8'))
            result_items = raw.get('result', []) or []
            candidates = [item.get('name', '') for item in result_items if item.get('name')]
            status = 'validated' if candidates else 'degraded'
            return VisionResult(self.provider_name, status, int((time.time() - start) * 1000), candidates[:8], raw, '', '', 'fallback to OCR-assisted vision')
        except Exception as exc:
            return VisionResult(self.provider_name, 'degraded', int((time.time() - start) * 1000), [], {}, str(exc), '', 'fallback to OCR-assisted vision')


def get_vision_providers():
    # Prefer paid/provider vision first when configured, but fall back aggressively if output is low-value.
    return [BaiduDishRecognitionProvider(), OCRAssistedVisionProvider()]


def _is_low_value_candidate_list(candidates: list[str]) -> bool:
    if not candidates:
        return True
    normalized = [c.strip() for c in candidates if c.strip()]
    if not normalized:
        return True
    low_value = {'非菜', '其他', '未知'}
    return all(item in low_value for item in normalized)


def detect_dish_candidates(image_path: str) -> VisionResult:
    results = [provider.detect(image_path) for provider in get_vision_providers()]
    for result in results:
        if result.status == 'validated' and result.candidates and not _is_low_value_candidate_list(result.candidates):
            return result
    for result in results:
        if result.status == 'validated' and result.candidates:
            return result
    return results[0]
