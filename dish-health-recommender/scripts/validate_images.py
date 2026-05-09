#!/usr/bin/env python3
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from scripts.image_cases import load_image_test_cases  # noqa: E402
import scripts.recommend as recommend_module  # noqa: E402

VALIDATION_DIR = SKILL_DIR / 'validation'
OUTPUT_PATH = VALIDATION_DIR / 'image-validation-report.json'


def percentile(values: list[int], ratio: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * ratio)))
    return int(ordered[index])


def health_expectation_met(case: dict, result: dict) -> bool:
    expected = case.get('expected_recommendation_examples', []) or []
    if not expected:
        return True
    return result.get('recommendation') in expected


def main() -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    cases = load_image_test_cases()
    results = []
    latencies: list[int] = []
    ocr_hits = 0
    top1_hits = 0
    top3_hits = 0
    health_hits = 0
    passed = 0
    for case in cases:
        payload = {'image_path': str(SKILL_DIR.parent / case['image_path']), 'output_mode': 'json'}
        started = time.time()
        result = recommend_module.recommend(payload)
        latency_ms = int((time.time() - started) * 1000)
        latencies.append(latency_ms)
        candidates = [item.get('canonical_name', '') for item in result.get('candidates', []) if isinstance(item, dict)]
        raw_image_text = json.dumps(result.get('raw_image_result', {}), ensure_ascii=False)
        expected_dishes = case.get('expected_dishes', []) or []
        expected_hits = [
            dish for dish in expected_dishes
            if dish in raw_image_text or any(dish in candidate for candidate in candidates)
        ]
        ocr_expectation = case.get('ocr_expectation', []) or []
        if not ocr_expectation or any(token in raw_image_text for token in ocr_expectation):
            ocr_hits += 1
        if expected_dishes:
            top_candidate = candidates[0] if candidates else (result.get('normalized_dish') or '')
            if any(dish and dish in top_candidate for dish in expected_dishes):
                top1_hits += 1
            top3_pool = candidates[:3] or ([result.get('normalized_dish')] if result.get('normalized_dish') else [])
            if any(any(dish and dish in item for item in top3_pool) for dish in expected_dishes):
                top3_hits += 1
        else:
            top1_hits += 1 if result.get('recommendation') == 'need_confirm' else 0
            top3_hits += 1 if result.get('recommendation') == 'need_confirm' else 0
        if health_expectation_met(case, result):
            health_hits += 1
        status = 'passed' if expected_hits or case.get('need_confirm_allowed') else 'needs_review'
        if status == 'passed':
            passed += 1
        results.append({
            'image_id': case['image_id'],
            'image_path': case['image_path'],
            'image_type': case['image_type'],
            'status': status,
            'expected_dishes': expected_dishes,
            'matched_expected': expected_hits,
            'recommendation': result.get('recommendation'),
            'need_confirm': result.get('need_confirm', []),
            'latency_ms': latency_ms,
            'raw_image_result': result.get('raw_image_result', {}),
        })
    total = len(cases) or 1
    metrics = {
        'ocr_hit_rate': round(ocr_hits / total, 4),
        'top1_hit_rate': round(top1_hits / total, 4),
        'top3_hit_rate': round(top3_hits / total, 4),
        'health_rule_accuracy': round(health_hits / total, 4),
        'p50_latency_ms': int(statistics.median(latencies)) if latencies else 0,
        'p95_latency_ms': percentile(latencies, 0.95),
    }
    report = {
        'report_name': 'image_validation',
        'report_path': str(OUTPUT_PATH),
        'total': len(cases),
        'passed': passed,
        'failed': len(cases) - passed,
        'metrics': metrics,
        'results': results,
    }
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
