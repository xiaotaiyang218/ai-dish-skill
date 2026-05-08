#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOWED_STATUS = {"implemented", "degradable", "pending_validation"}
SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parent
REPORT_PATH = REPO_ROOT / 'report' / 'AI创想家_菜谱识别推荐系统_优化版报告.md'


def default_items() -> list[dict]:
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
            "validation_refs": ["dish-health-recommender/tests/test_multimodal.py"],
            "metric_summary": "已建立图片样本底表，并让 OCR/vision 候选参与主链路归一化和推荐判断。",
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
            "metric_summary": "已支持标准配方命中时的量化输出，未命中时回退到定性标签与边界说明。",
            "boundary_note": "定量值仅在命中标准配方时输出，未覆盖菜品不会伪造精确营养值。",
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
            "metric_summary": "已支持 accept/reject/favorite/correct_dish_name 四类反馈，并可影响 confidence、说明文本与推荐等级。",
            "boundary_note": "当前为最小本地闭环，不是训练式排序或强化学习系统。",
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
            "boundary_note": "当前已具备自动化验证与示例证据，正式比赛指标仍需继续补真实统计。",
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
    counts = {name: sum(1 for item in items if item.get('status') == name) for name in ALLOWED_STATUS}
    return {'valid': not invalid, 'invalid_items': invalid, **counts}


def main() -> None:
    if len(sys.argv) > 1:
        payload = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        print(json.dumps(validate_items(payload.get('items', [])), ensure_ascii=False, indent=2))
        return
    print(json.dumps({'report': str(REPORT_PATH), 'items': default_items(), 'summary': validate_items(default_items())}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
