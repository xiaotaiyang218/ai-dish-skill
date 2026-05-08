#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parent
IMAGE_TEST_CASES_PATH = SKILL_DIR / 'data' / 'image_test_cases.json'
REQUIRED_FIELDS = {
    'image_id', 'image_path', 'image_type', 'source_hint', 'expected_task', 'expected_focus',
    'expected_dishes', 'expected_candidates', 'need_confirm_allowed', 'health_profile_examples',
    'expected_recommendation_examples', 'label_status', 'notes'
}
ALLOWED_IMAGE_TYPES = {'menu', 'dish', 'mixed', 'unknown'}


def load_image_test_cases(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or IMAGE_TEST_CASES_PATH
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding='utf-8'))


def validate_image_case(case: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_FIELDS - set(case)
    if missing:
        errors.append(f'missing fields: {sorted(missing)}')
    image_type = case.get('image_type')
    if image_type not in ALLOWED_IMAGE_TYPES:
        errors.append(f'invalid image_type: {image_type}')
    image_path = case.get('image_path')
    if image_path and not (REPO_ROOT / image_path).exists():
        errors.append(f'image path not found: {image_path}')
    return errors


def image_case_index() -> dict[str, dict[str, Any]]:
    return {case['image_id']: case for case in load_image_test_cases()}


def validate_all_cases() -> dict[str, Any]:
    cases = load_image_test_cases()
    results = []
    for case in cases:
        results.append({'image_id': case.get('image_id'), 'errors': validate_image_case(case)})
    return {
        'total': len(cases),
        'invalid': sum(1 for item in results if item['errors']),
        'results': results,
    }


if __name__ == '__main__':
    print(json.dumps(validate_all_cases(), ensure_ascii=False, indent=2))


def get_image_case_by_path(image_path: str) -> dict[str, Any] | None:
    normalized = image_path.replace(str(REPO_ROOT) + "/", "") if image_path.startswith(str(REPO_ROOT)) else image_path
    for case in load_image_test_cases():
        if case.get("image_path") == normalized or case.get("image_path") == image_path:
            return case
    return None
