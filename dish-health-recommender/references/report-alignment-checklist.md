# Report Alignment Checklist

| 报告章节 | 能力声明 | 实现文件 | 测试证据 | 状态 | 边界说明 |
| --- | --- | --- | --- | --- | --- |
| 摘要 / 总体能力 | 支持菜名、菜单文字、OCR 文本、图片引用等输入 | `scripts/recommend.py`、`references/platform-prompt.md` | `tests/test_recommend.py`、`tests/fixtures/us1_image_only_need_confirm.json` | degradable | 图片引用与 OCR 输入已建模并可显式降级，但未直接接入真实视觉识别。 |
| 创新点一 | 多模态菜谱识别与语义还原 | `scripts/recommend.py`、`data/dishes.json` | `tests/fixtures/us2_alias_xihongshi_chaojidan.json`、`tests/test_recommend.py` | degradable | 文本/别名/OCR 文本归一化已实现，多模态视觉识别仍待验证。 |
| 创新点二 | 标准菜谱库与营养知识库联动的健康比对引擎 | `data/dishes.json`、`data/nutrition_knowledge.json`、`scripts/recommend.py` | `tests/fixtures/us3_gout_crayfish.json`、`tests/test_recommend.py` | implemented | 当前实现为定性标签与规则推理，不输出未验证精确营养值。 |
| 创新点三 | 用户反馈驱动的可解释推荐机制 | `scripts/recommend.py`、`references/output-templates.md` | `tests/fixtures/us4_human_mode_tomato_egg.json`、`tests/test_recommend.py` | pending_validation | 已实现可解释输出，但尚未实现真实反馈采集和权重更新闭环。 |
| 实验与结果 / 推荐示例 | 报告中的典型推荐示例可由真实脚本回归产生 | `references/test-cases.md`、`tests/expected/` | `tests/test_recommend.py` | implemented | 已具备回归样例，量化实验指标仍需继续实测。 |
