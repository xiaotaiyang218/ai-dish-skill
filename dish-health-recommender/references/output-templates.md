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

客观信息：
- 识别菜品：{标准菜名或未确认}
- 主要食材：{食材列表；未知则写“未确认”}
- 常见做法：{做法；未知则写“未确认”}
- 风险标签：{风险标签；没有则写“暂无明显风险标签”}
- 营养估算：{有标准份量时写热量/蛋白质/脂肪/碳水/糖/钠；没有则说明缺少标准份量或克重}

结论：{推荐等级}

原因：
1. {原因1}
2. {原因2}

建议：{可执行建议}

需要确认：{缺失信息；没有则写“暂无”}

提示：以上仅作饮食参考，不能替代医生或营养师建议。

## Detailed Agent Answer

**客观信息：**
- 菜品识别：{标准菜名、置信度、是否存在歧义}
- 可能食材：{食材列表}
- 烹饪方式：{做法}
- 风险标签：{过敏、低盐、控糖、减脂、高蛋白、素食等命中情况}
- 营养估算：{标准份量、热量 kcal、蛋白质 g、脂肪 g、碳水 g、糖 g、钠 mg；如果没有可靠数据，说明原因}
- 命中规则：{过敏、低盐、控糖、减脂、高蛋白、素食等}
- 降级说明：{是否因无 OCR/视觉能力而依赖文本推断}

**结论：** {推荐等级}

**判断依据：**
- {与食材、做法、风险标签和用户约束直接相关的 2-4 条原因}

**建议：** {份量、替换、少盐少油、确认配方等}

**需要确认：** {图片不清晰、配方不明、过敏风险等}

## Image Ingredient vs Dish Name

当图片中的标准菜名不确定，但主要食材较明确时，回答要拆开：

- 菜名识别：`不确定，可能是 A/B`。
- 食材事实：`可以明确看到虾/蟹/蛋/内脏等`。
- 健康判断：过敏和明确禁忌可基于食材事实直接给 `不推荐`；普通营养建议则标注为 `谨慎` 或 `需要确认`。
- 需要确认：`标准菜名、调味方式、是否含隐藏配料`。

## Multi-Dish Menu Screening

按优先级输出：

1. 更适合选择：{菜名 + 理由}
2. 谨慎选择：{菜名 + 理由}
3. 建议避开：{菜名 + 理由}
4. 需要补充确认：{菜名 + 缺失信息}
