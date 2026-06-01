# Report Alignment Checklist

| 报告章节 | 能力声明 | 实现文件 | 测试证据 | 指标/产物证据 | 状态 | 边界说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 摘要 / 总体能力 | 支持菜名、菜单文字、OCR 文本、图片引用和图片路径等输入 | `dish-health-recommender/scripts/recommend.py`、`dish-health-recommender/references/provider-setup.md` | `dish-health-recommender/tests/test_recommend.py`、`dish-health-recommender/tests/test_multimodal.py` | `dish-health-recommender/data/image_test_cases.json` | degradable | 图片输入已接入主推荐流程，但未知图、噪声图和低置信度结果仍会显式降级。 |
| 创新点一 | 多模态菜谱识别与语义还原 | `dish-health-recommender/scripts/recommend.py`、`dish-health-recommender/providers/ocr_provider.py`、`dish-health-recommender/providers/vision_provider.py` | `dish-health-recommender/tests/test_multimodal.py`、`dish-health-recommender/data/image_test_cases.json` | `dish-health-recommender/validation/image-validation-report.json`（OCR hit rate=1.0，Top-1=0.3636，Top-3=0.3636，health rule accuracy=0.8636，p50/p95=5083/9828ms） | implemented | OCR/vision 候选已接入主链路，仍保留低置信度 `need_confirm` 机制，不宣称通用稳定识别。 |
| 创新点二 | 标准菜谱库与营养知识库联动的健康比对引擎 | `dish-health-recommender/data/dishes.json`、`dish-health-recommender/data/nutrition_knowledge.json`、`dish-health-recommender/data/quantified_recipes.json`、`dish-health-recommender/scripts/recommend.py` | `dish-health-recommender/tests/test_recommend.py`、`dish-health-recommender/tests/test_quantization.py` | `dish-health-recommender/tests/test_quantization.py` | implemented | 当前已支持标准配方命中时的精确量化输出；未命中精确配方但有常见菜谱参考时，可输出明确标注的区间估算。 |
| 创新点三 | 用户反馈驱动的可解释推荐机制 | `dish-health-recommender/scripts/apply_feedback.py`、`dish-health-recommender/scripts/recommend.py`、`dish-health-recommender/scripts/chat_recommend.py` | `dish-health-recommender/tests/test_feedback.py`、`dish-health-recommender/tests/test_e2e_nl.py` | `dish-health-recommender/tests/test_feedback.py` | implemented | 当前为本地轻量反馈闭环，可影响 confidence、说明文本、部分推荐等级和用户画像合并，但不是训练式排序系统。 |
| 用户画像 | 长期约束与阶段目标分层存储 | `dish-health-recommender/scripts/apply_feedback.py`、`dish-health-recommender/scripts/recommend.py` | `dish-health-recommender/tests/test_feedback.py` | `test_stored_user_profile_is_applied_to_recommendation` | implemented | 只有用户明确确认后才写入；长期约束与临时目标分开，推荐时通过 `user_id` 合并。 |
| 实验与结果 / 推荐示例 | 报告中的典型推荐示例可由真实脚本回归产生 | `dish-health-recommender/references/test-cases.md`、`dish-health-recommender/tests/expected/` | `dish-health-recommender/tests/test_recommend.py`、`dish-health-recommender/tests/test_alignment.py` | `dish-health-recommender/validation/report-alignment-report.json`、`dish-health-recommender/validation/image-validation-report.json` | implemented | 已具备自动化回归和对齐验证，后续仍需继续补充更大规模真实使用统计。 |

## 验证顺序

1. 先运行 `python3 dish-health-recommender/tests/test_multimodal.py`，确认图片样本字段与多模态链路稳定。
2. 再运行 `python3 dish-health-recommender/scripts/validate_images.py`，生成 `validation/image-validation-report.json` 指标产物。
3. 运行 `python3 dish-health-recommender/tests/test_alignment.py`，确认对齐条目引用了 metrics artifact 与边界说明。
4. 最后运行 `python3 dish-health-recommender/scripts/report_alignment.py`，生成 `validation/report-alignment-report.json` 供报告引用。
