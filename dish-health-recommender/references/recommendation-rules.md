# Recommendation Rules

## Recommendation Levels

- `recommend`: likely suitable under the stated constraints.
- `caution`: can be eaten with portion, cooking, or ingredient adjustments.
- `avoid`: conflicts with allergy, explicit restriction, or high-risk ingredient.
- `need_confirm`: insufficient evidence, ambiguous dish, unclear ingredient, or no image/text confidence.

## Priority Order

1. Allergies and severe restrictions.
2. Disease-related constraints such as low salt, sugar control, gout/purine caution, low fat.
3. Dietary goals such as weight loss, high protein, vegetarian, light diet.
4. Taste preference and convenience.

## Common Risk Tags

- Egg allergy: 鸡蛋、蛋液、蛋黄、蛋白、蛋制品.
- Seafood allergy: 虾、蟹、贝、鱼、海鲜、鱼露、虾皮.
- Nut allergy: 花生、坚果、芝麻酱.
- Low salt concern: 腌、咸、酱油、豆瓣酱、咸菜、火腿、腊肉.
- Sugar control concern: 糖、蜂蜜、甜面酱、糖醋、红烧、勾芡、主食过多.
- Weight loss concern: 油炸、肥肉、五花肉、奶油、重油、裹粉.
- Gout/purine concern: 动物内脏、浓肉汤、海鲜、啤酒.

## Uncertainty Policy

For dish names with misleading literal meanings, state the common recipe and the uncertainty. Example: `鱼香肉丝` usually does not contain fish, but may contain sugar, oil, and bean paste; seafood allergy risk is usually low but recipe should be confirmed for strict users.

For vague dish names such as `招牌小炒`, `家常一品锅`, or `老板推荐`, return `need_confirm` unless the user supplies a photo, menu description, or ingredients.

## Ambiguous Dish Handling Addendum

- 菜名命中高歧义词（如“招牌”“农家一品锅”“老板推荐”）时，即使命中本地候选，也应在严格模式下优先返回 `need_confirm`。
- 当菜名来自 `ocr_text` 推断而不是用户明确输入时，需要在解释中提示“基于 OCR 文本推断”，并建议人工核对标准菜名。
- 候选召回应保留前若干候选及置信度，避免把模糊输入伪装为唯一确定结果。

## Additional Health Scenarios

- High-protein goal: prefer dishes with clear lean protein sources such as chicken breast, fish, eggs, tofu, or lean meat, while avoiding heavy oil as the main signal.
- Vegetarian goal: if a common recipe contains meat, fish, or egg, return `avoid` or `need_confirm` based on recipe certainty.
- Gout / high uric acid: high-purine seafood, organ meats, and heavy drinking dishes should default to `caution` or `avoid` depending on user strictness and recipe certainty.
- When multiple rules hit, explanation should be compressed to 2-4 user-readable reasons rather than listing every internal tag.

