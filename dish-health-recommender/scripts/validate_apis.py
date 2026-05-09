#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from providers.nutrition_provider import validate_all_providers as validate_nutrition_providers  # noqa: E402
from providers.ocr_provider import DomesticOCRProvider, MacVisionOCRProvider  # noqa: E402
from providers.vision_provider import BaiduDishRecognitionProvider, OCRAssistedVisionProvider  # noqa: E402

VALIDATION_DIR = SKILL_DIR / 'validation'
OUTPUT_JSON = VALIDATION_DIR / 'api-validation-report.json'
OUTPUT_MD = VALIDATION_DIR / 'api-validation.md'
SAMPLE_IMAGE_PATH = SKILL_DIR.parent / 'pic' / '20260508-123047.jpg'


def provider_record_from_result(provider_type: str, request_sample: dict, result) -> dict:
    response_sample = {}
    if hasattr(result, 'lines'):
        response_sample['lines'] = (result.lines or [])[:5]
        response_sample['text'] = getattr(result, 'text', '')[:120]
    if hasattr(result, 'candidates'):
        response_sample['candidates'] = (result.candidates or [])[:5]
    raw_result = getattr(result, 'raw_result', {}) or {}
    if raw_result:
        response_sample['raw_result'] = raw_result
    return {
        'provider_name': result.provider_name,
        'provider_type': provider_type,
        'status': result.status,
        'request_sample': request_sample,
        'response_sample': response_sample,
        'error_message': getattr(result, 'error_message', ''),
        'latency_ms': getattr(result, 'latency_ms', 0),
        'credential_hint': getattr(result, 'credential_hint', ''),
        'degrade_strategy': getattr(result, 'degrade_strategy', ''),
    }


def validate_image_runtime_providers() -> list[dict]:
    request_sample = {'image_path': str(SAMPLE_IMAGE_PATH)}
    if not SAMPLE_IMAGE_PATH.exists():
        return [{
            'provider_name': 'image_runtime_providers',
            'provider_type': 'vision',
            'status': 'unavailable',
            'request_sample': request_sample,
            'response_sample': {},
            'error_message': f'sample image not found: {SAMPLE_IMAGE_PATH}',
            'latency_ms': 0,
            'credential_hint': '',
            'degrade_strategy': '',
        }]
    records = []
    for provider_type, provider in [
        ('vision', BaiduDishRecognitionProvider()),
        ('vision', OCRAssistedVisionProvider()),
        ('vision', DomesticOCRProvider()),
        ('vision', MacVisionOCRProvider()),
    ]:
        result = provider.detect(str(SAMPLE_IMAGE_PATH)) if hasattr(provider, 'detect') else provider.recognize(str(SAMPLE_IMAGE_PATH))
        records.append(provider_record_from_result(provider_type, request_sample, result))
    return records


def main() -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    records = validate_nutrition_providers() + validate_image_runtime_providers()
    report = {'report_name': 'api_validation', 'report_path': str(OUTPUT_JSON), 'records': records}
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# API Validation Matrix',
        '',
        '| Provider | Type | Status | Credential Requirement | Notes |',
        '| --- | --- | --- | --- | --- |',
    ]
    for item in records:
        cred = item.get('credential_hint') or 'none'
        notes = item.get('error_message') or item.get('degrade_strategy') or ''
        lines.append(f"| {item['provider_name']} | {item['provider_type']} | {item['status']} | {cred} | {notes} |")
    OUTPUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
