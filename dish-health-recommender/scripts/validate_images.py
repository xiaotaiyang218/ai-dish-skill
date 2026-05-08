#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from scripts.image_cases import load_image_test_cases  # noqa: E402
import scripts.recommend as recommend_module  # noqa: E402

OUTPUT_PATH = SKILL_DIR.parents[2] / 'specs' / '20260508-dish-multi-verify' / 'validation' / 'image-validation-report.json'


def main() -> None:
    cases = load_image_test_cases()
    results = []
    passed = 0
    for case in cases:
        payload = {'image_path': str(SKILL_DIR.parents[2] / case['image_path']), 'output_mode': 'json'}
        result = recommend_module.recommend(payload)
        expected_hits = [
            dish for dish in case.get('expected_dishes', [])
            if dish in (result.get('ocr_text') or '') or any(dish in str(c) for c in result.get('candidates', []))
        ]
        status = 'passed' if expected_hits or case.get('need_confirm_allowed') else 'needs_review'
        if status == 'passed':
            passed += 1
        results.append({
            'image_id': case['image_id'],
            'image_path': case['image_path'],
            'image_type': case['image_type'],
            'status': status,
            'expected_dishes': case.get('expected_dishes', []),
            'matched_expected': expected_hits,
            'recommendation': result.get('recommendation'),
            'need_confirm': result.get('need_confirm', []),
            'raw_image_result': result.get('raw_image_result', {}),
        })
    report = {'total': len(cases), 'passed': passed, 'failed': len(cases) - passed, 'results': results}
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
