# Report Alignment Checklist

| 报告章节 | 能力声明 | 实现文件 | 测试证据 | 状态 | 边界说明 |
| --- | --- | --- | --- | --- | --- |
| 摘要 / 总体能力 | 支持菜名、菜单文字、OCR 文本、图片引用和图片路径等输入 | `dish-health-recommender/scripts/recommend.py`、`dish-health-recommender/references/provider-setup.md` | `dish-health-recommender/tests/test_recommend.py`、`dish-health-recommender/tests/test_multimodal.py` | degradable | 图片输入已接入主推荐流程，但未知图、噪声图和低置信度结果仍会显式降级。 |
| 创新点一 | 多模态菜谱识别与语义还原 | `dish-health-recommender/scripts/recommend.py`、`dish-health-recommender/providers/ocr_provider.py`、`dish-health-recommender/providers/vision_provider.py` | `dish-health-recommender/tests/test_multimodal.py`、`dish-health-recommender/data/image_test_cases.json` | implemented | OCR/vision 候选已接入主链路，仍保留低置信度 `need_confirm` 机制，不宣称通用稳定识别。 |
| 创新点二 | 标准菜谱库与营养知识库联动的健康比对引擎 | `dish-health-recommender/data/dishes.json`、`dish-health-recommender/data/nutrition_knowledge.json`、`dish-health-recommender/data/quantified_recipes.json`、`dish-health-recommender/scripts/recommend.py` | `dish-health-recommender/tests/test_recommend.py`、`dish-health-recommender/tests/test_quantization.py` | implemented | 当前已支持标准配方命中时的量化输出；未命中标准配方时只输出定性标签与边界说明。 |
| 创新点三 | 用户反馈驱动的可解释推荐机制 | `dish-health-recommender/scripts/apply_feedback.py`、`dish-health-recommender/scripts/recommend.py`、`dish-health-recommender/scripts/chat_recommend.py` | `dish-health-recommender/tests/test_feedback.py`、`dish-health-recommender/tests/test_e2e_nl.py` | implemented | 当前为本地轻量反馈闭环，可影响 confidence、说明文本和部分推荐等级，但不是训练式排序系统。 |
| 实验与结果 / 推荐示例 | 报告中的典型推荐示例可由真实脚本回归产生 | `dish-health-recommender/references/test-cases.md`、`dish-health-recommender/tests/expected/` | `dish-health-recommender/tests/test_recommend.py`、`dish-health-recommender/tests/test_alignment.py` | implemented | 已具备自动化回归和对齐验证，正式比赛指标仍需继续补真实统计。 |
