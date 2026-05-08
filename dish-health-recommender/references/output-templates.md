# Output Templates

## JSON Mode

Required fields:
- `normalized_dish`
- `recommendation`
- `confidence`
- `ingredients`
- `cooking_method`
- `nutrition_tags`
- `risk_tags`
- `nutrition_evidence`
- `explanation`
- `need_confirm`
- `candidates` (optional but recommended for fuzzy/ambiguous inputs)
- `degraded_input` (optional; indicates OCR/image downgrade)
- `human_readable_cn` (only when `output_mode=human_readable_cn`)

## WeChat-Style Short Answer

结论：{推荐等级}

原因：
1. {原因1}
2. {原因2}

建议：{可执行建议}

需要确认：{缺失信息；没有则写“暂无”}

提示：以上仅作饮食参考，不能替代医生或营养师建议。

## Detailed Agent Answer

**结论：** {推荐等级}

**判断依据：**
- 菜品识别：{标准菜名、置信度、是否存在歧义}
- 可能食材：{食材列表}
- 烹饪方式：{做法}
- 命中规则：{过敏、低盐、控糖、减脂、高蛋白、素食等}
- 降级说明：{是否因无 OCR/视觉能力而依赖文本推断}

**建议：** {份量、替换、少盐少油、确认配方等}

**需要确认：** {图片不清晰、配方不明、过敏风险等}

## Multi-Dish Menu Screening

按优先级输出：

1. 更适合选择：{菜名 + 理由}
2. 谨慎选择：{菜名 + 理由}
3. 建议避开：{菜名 + 理由}
4. 需要补充确认：{菜名 + 缺失信息}
