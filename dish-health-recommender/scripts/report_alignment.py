#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ALLOWED_STATUS = {"implemented", "degradable", "pending_validation"}
REPO_ROOT = Path(__file__).resolve().parents[4]
REPORT_PATH = REPO_ROOT / 'AI创想家_菜谱识别推荐系统_优化版报告.md'


def default_items() -> list[dict]:
    return [
        {
            "report_section": "摘要/总体能力",
            "claim": "支持菜名、菜单文字、OCR 文本、图片引用等输入",
            "implementation_refs": [
                ".agents/skills/dish-health-recommender/scripts/recommend.py",
                ".agents/skills/dish-health-recommender/references/platform-prompt.md",
            ],
            "test_refs": [
                ".agents/skills/dish-health-recommender/tests/test_recommend.py",
                ".agents/skills/dish-health-recommender/tests/fixtures/us1_image_only_need_confirm.json",
            ],
            "status": "degradable",
            "validation_refs": ["specs/20260508-dish-multi-verify/validation/image-validation.md"],
            "metric_summary": "图片输入契约已接入，未知图会显式降级。",
            "boundary_note": "当前支持 image_reference/OCR 文本输入契约和显式降级，不直接执行真实视觉识别。",
        },
        {
            "report_section": "创新点一",
            "claim": "多模态菜谱识别与语义还原",
            "implementation_refs": [
                ".agents/skills/dish-health-recommender/scripts/recommend.py",
                ".agents/skills/dish-health-recommender/data/dishes.json",
            ],
            "test_refs": [
                ".agents/skills/dish-health-recommender/tests/fixtures/us2_alias_xihongshi_chaojidan.json",
                ".agents/skills/dish-health-recommender/tests/test_recommend.py",
            ],
            "status": "implemented",
            "validation_refs": ["specs/20260508-dish-multi-verify/validation/image-validation.md"],
            "metric_summary": "已建立 22 张图片验证底表，并跑通菜单图/菜肴图 OCR 与候选识别测试。",
            "boundary_note": "多模态图片验证链路已打通，但仍允许模糊图返回 need_confirm。",
        },
        {
            "report_section": "创新点二",
            "claim": "标准菜谱库与营养知识库联动的健康比对引擎",
            "implementation_refs": [
                ".agents/skills/dish-health-recommender/data/dishes.json",
                ".agents/skills/dish-health-recommender/data/nutrition_knowledge.json",
                ".agents/skills/dish-health-recommender/scripts/recommend.py",
            ],
            "test_refs": [
                ".agents/skills/dish-health-recommender/tests/fixtures/us3_gout_crayfish.json",
                ".agents/skills/dish-health-recommender/tests/test_recommend.py",
            ],
            "status": "implemented",
            "validation_refs": ["specs/20260508-dish-multi-verify/nutrition-quantization-notes.md"],
            "metric_summary": "已支持标准菜谱级量化输出，并保留无标准配方时的降级说明。",
            "boundary_note": "定量值仅在命中标准配方时输出。",
        },
        {
            "report_section": "创新点三",
            "claim": "用户反馈驱动的可解释推荐机制",
            "implementation_refs": [
                ".agents/skills/dish-health-recommender/references/output-templates.md",
                ".agents/skills/dish-health-recommender/scripts/recommend.py",
            ],
            "test_refs": [
                ".agents/skills/dish-health-recommender/tests/fixtures/us4_human_mode_tomato_egg.json",
                ".agents/skills/dish-health-recommender/tests/test_recommend.py",
            ],
            "status": "implemented",
            "validation_refs": ["specs/20260508-dish-multi-verify/validation/innovation-evidence.md"],
            "metric_summary": "已支持 accept/reject/favorite/correct_dish_name 四类反馈闭环。",
            "boundary_note": "当前为最小本地闭环，不涉及训练式优化。",
        },
        {
            "report_section": "实验与结果/推荐结果示例",
            "claim": "报告中的典型推荐示例可由真实脚本回归产生",
            "implementation_refs": [
                ".agents/skills/dish-health-recommender/references/test-cases.md",
                ".agents/skills/dish-health-recommender/tests/expected/",
            ],
            "test_refs": [
                ".agents/skills/dish-health-recommender/tests/test_recommend.py",
            ],
            "status": "implemented",
            "validation_refs": ["specs/20260508-dish-multi-verify/validation/innovation-evidence.md"],
            "metric_summary": "回归样例、图片验证、反馈闭环和量化验证可共同支撑实验更新。",
            "boundary_note": "当前已具备本地回归样例，实验指标仍需继续实测补全。",
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
