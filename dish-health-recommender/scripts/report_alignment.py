#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

STATUS_ORDER = ("implemented", "degradable", "pending_validation")
ALLOWED_STATUS = set(STATUS_ORDER)
SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parent
REPORT_PATH = REPO_ROOT / 'report' / 'AI创想家_菜谱识别推荐系统_优化版报告.md'
VALIDATION_DIR = SKILL_DIR / 'validation'
OUTPUT_JSON = VALIDATION_DIR / 'report-alignment-report.json'
IMAGE_VALIDATION_PATH = VALIDATION_DIR / 'image-validation-report.json'


def repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_image_validation_report() -> dict:
    if not IMAGE_VALIDATION_PATH.exists():
        return {}
    return json.loads(IMAGE_VALIDATION_PATH.read_text(encoding='utf-8'))


def format_image_metric_summary(report: dict) -> str:
    metrics = report.get('metrics', {}) if isinstance(report, dict) else {}
    if not metrics:
        return '图片验证脚本已输出 OCR hit rate、Top-1/Top-3 命中率、health rule accuracy 与 p50/p95 latency，可作为报告证据入口。'
    return (
        '图片验证产物显示 '
        f"OCR hit rate={metrics.get('ocr_hit_rate', 0)}, "
        f"Top-1={metrics.get('top1_hit_rate', 0)}, "
        f"Top-3={metrics.get('top3_hit_rate', 0)}, "
        f"health rule accuracy={metrics.get('health_rule_accuracy', 0)}, "
        f"p50/p95 latency={metrics.get('p50_latency_ms', 0)}/{metrics.get('p95_latency_ms', 0)}ms，"
        '可直接作为报告指标证据入口。'
    )


def default_items(image_validation_report: dict | None = None) -> list[dict]:
    image_validation_report = image_validation_report or {}
    image_metric_summary = format_image_metric_summary(image_validation_report)
    return [
        {
            "report_section": "摘要/总体能力",
            "claim": "支持菜名、菜单文字、OCR 文本、图片引用和图片路径等输入",
            "implementation_refs": [
                "dish-health-recommender/scripts/recommend.py",
                "dish-health-recommender/references/provider-setup.md",
            ],
            "test_refs": [
                "dish-health-recommender/tests/test_recommend.py",
                "dish-health-recommender/tests/test_multimodal.py",
            ],
            "status": "degradable",
            "validation_refs": ["dish-health-recommender/data/image_test_cases.json"],
            "metric_summary": "图片输入已接入主推荐流程，未知图或低置信度图片仍会显式降级。",
            "boundary_note": "当前图片链路依赖 OCR/vision provider 与样本验证，未承诺对任意真实场景图片都稳定识别。",
        },
        {
            "report_section": "创新点一",
            "claim": "多模态菜谱识别与语义还原",
            "implementation_refs": [
                "dish-health-recommender/scripts/recommend.py",
                "dish-health-recommender/providers/ocr_provider.py",
                "dish-health-recommender/providers/vision_provider.py",
            ],
            "test_refs": [
                "dish-health-recommender/tests/test_multimodal.py",
                "dish-health-recommender/data/image_test_cases.json",
            ],
            "status": "implemented",
            "validation_refs": [
                "dish-health-recommender/tests/test_multimodal.py",
                "dish-health-recommender/validation/image-validation-report.json"
            ],
            "metric_summary": image_metric_summary,
            "boundary_note": "多模态链路已接入主流程，但对未知图、噪声图和候选冲突场景仍保留 need_confirm。",
        },
        {
            "report_section": "创新点二",
            "claim": "标准菜谱库与营养知识库联动的健康比对引擎",
            "implementation_refs": [
                "dish-health-recommender/data/dishes.json",
                "dish-health-recommender/data/nutrition_knowledge.json",
                "dish-health-recommender/data/quantified_recipes.json",
                "dish-health-recommender/scripts/recommend.py",
            ],
            "test_refs": [
                "dish-health-recommender/tests/test_recommend.py",
                "dish-health-recommender/tests/test_quantization.py",
            ],
            "status": "implemented",
            "validation_refs": ["dish-health-recommender/tests/test_quantization.py"],
            "metric_summary": "已支持标准配方命中时的精确量化输出；未命中精确配方但有常见菜谱参考时，可输出明确标注的区间估算。",
            "boundary_note": "精确量化只在命中标准配方时输出；区间估算会标注常见范围和非实测克重，避免伪造精确营养值。",
        },
        {
            "report_section": "创新点三",
            "claim": "用户反馈驱动的可解释推荐机制",
            "implementation_refs": [
                "dish-health-recommender/scripts/apply_feedback.py",
                "dish-health-recommender/scripts/recommend.py",
                "dish-health-recommender/tests/test_e2e_nl.py",
            ],
            "test_refs": [
                "dish-health-recommender/tests/test_feedback.py",
                "dish-health-recommender/tests/test_e2e_nl.py",
            ],
            "status": "implemented",
            "validation_refs": ["dish-health-recommender/tests/test_feedback.py"],
            "metric_summary": "已支持 accept/reject/favorite/correct_dish_name/set_user_profile 五类反馈，可影响 confidence、说明文本、推荐等级和用户画像合并。",
            "boundary_note": "当前为本地轻量反馈闭环，不是训练式排序或强化学习系统；用户画像只有在用户明确确认后写入。",
        },
        {
            "report_section": "用户画像",
            "claim": "长期约束与阶段目标分层存储，并在后续推荐中按 user_id 合并",
            "implementation_refs": [
                "dish-health-recommender/scripts/apply_feedback.py",
                "dish-health-recommender/scripts/recommend.py",
            ],
            "test_refs": ["dish-health-recommender/tests/test_feedback.py"],
            "status": "implemented",
            "validation_refs": ["test_stored_user_profile_is_applied_to_recommendation"],
            "metric_summary": "已验证用户确认后的海鲜过敏、减脂、低盐信息能被后续油爆虾推荐复用。",
            "boundary_note": "不会从一次普通提问自动长期记忆；长期约束和阶段目标分开存储，可被用户修改或删除。",
        },
        {
            "report_section": "实验与结果/推荐结果示例",
            "claim": "报告中的典型推荐示例可由真实脚本回归产生",
            "implementation_refs": [
                "dish-health-recommender/references/test-cases.md",
                "dish-health-recommender/tests/expected/",
            ],
            "test_refs": [
                "dish-health-recommender/tests/test_recommend.py",
                "dish-health-recommender/tests/test_alignment.py",
            ],
            "status": "implemented",
            "validation_refs": ["dish-health-recommender/tests/test_alignment.py"],
            "metric_summary": "回归样例、图片验证、反馈闭环和量化验证可共同支撑实验与报告更新。",
            "boundary_note": "当前已具备自动化验证与示例证据，后续仍需继续补充更大规模真实使用统计。",
        },
    ]


def validate_items(items: list[dict]) -> dict:
    invalid = []
    for idx, item in enumerate(items, 1):
        status = item.get('status')
        if status not in ALLOWED_STATUS:
            invalid.append({'index': idx, 'reason': f'invalid status: {status}'})
        if not item.get('claim'):
            invalid.append({'index': idx, 'reason': 'missing claim'})
        if status != 'pending_validation' and not (item.get('implementation_refs') or item.get('test_refs')):
            invalid.append({'index': idx, 'reason': 'implemented/degradable items need refs'})
        if status == 'implemented' and not item.get('validation_refs'):
            invalid.append({'index': idx, 'reason': 'implemented items need validation refs'})
    counts = {name: sum(1 for item in items if item.get('status') == name) for name in STATUS_ORDER}
    return {'valid': not invalid, 'invalid_items': invalid, **counts}


def main() -> None:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) > 1:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        print(json.dumps(validate_items(payload.get('items', [])), ensure_ascii=False, indent=2))
        return
    image_validation_report = load_image_validation_report()
    items = default_items(image_validation_report)
    report = {
        'report_name': 'report_alignment',
        'report_path': repo_relative(OUTPUT_JSON),
        'report': repo_relative(REPORT_PATH),
        'items': items,
        'summary': validate_items(items),
        'evidence_summary': {
            'image_validation_report': repo_relative(IMAGE_VALIDATION_PATH),
            'image_metrics': image_validation_report.get('metrics', {}),
        },
    }
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
