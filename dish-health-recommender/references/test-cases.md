# Test Cases

Use these examples to validate the skill in Codex and other agent platforms.

## Single Dish

Input: `我鸡蛋过敏，番茄炒蛋能吃吗？`

Expected: `不推荐`; reason mentions egg allergy.

Input: `减脂控糖时能不能吃提拉米苏？`

Expected: `谨慎`; reason mentions mascarpone/cream fat, added sugar, biscuit carbohydrate, portion control.

Expected quantitative detail: if standard recipe data is used, energy should include unit `kcal` or `千卡` and mention standard portion, not measured weight.

Input: `海鲜过敏的人吃鱼香肉丝有风险吗？`

Expected: usually `谨慎` or `需要确认`; explain that common recipes do not contain fish but variants should be confirmed.

## Ambiguous Dish

Input: `招牌小炒适合低盐饮食吗？`

Expected: `需要确认`; ask for ingredients/photo/menu description.

## Quantitative Range

Input: `我减脂控糖，鱼香肉丝能不能吃？`

Expected: `谨慎` or `需要确认` depending on strictness; if exact recipe is not available, may output `nutrition_quantitative_range` such as `热量约 250-450 千卡` and must mark it as common range estimate, not measured weight.

## User Profile Memory

First input: `请记住，我海鲜过敏，最近在减脂并且低盐。`

Expected: record `set_user_profile`; store seafood allergy under `persistent_constraints.allergies`, weight-loss/low-salt under `temporary_goals`.

Next input with same `user_id`: `油爆虾能吃吗？`

Expected: `不推荐`; explanation mentions applied user profile and seafood allergy.

## Script JSON

```json
{
  "dish_name": "提拉米苏",
  "user_profile": {
    "goals": ["减脂"],
    "conditions": ["控糖"]
  }
}
```

Expected: `caution`; reason mentions added sugar, dairy fat, biscuit carbohydrate, portion.

## Data Source Checks

Input: `可乐鸡翅 + 控糖`

Expected: uses local `data/dishes.json` from CookBook-KG and returns `caution` because the recipe contains `可乐`.

Input: `鱼香红烧带鱼 + 鱼类过敏`

Expected: if missing from local cache and network is available, uses CookBook-KG online fallback and returns `avoid` because ingredients include `带鱼`.

Input: `番茄炒蛋 + 鸡蛋过敏`

Expected: returns `avoid` and includes nutrition evidence for `鸡蛋` with `含蛋` risk tag.

Input JSON:

```json
{
  "dish_name": "巧克力甜点",
  "ingredients": ["chocolate"],
  "user_profile": {"conditions": ["控糖"], "goals": ["减脂"]}
}
```

Expected: if network is available, uses USDA FoodData Central fallback, caches `chocolate`, and returns `caution` with `可能高糖` and `可能高脂`.

## Executable Regression Source

- `tests/fixtures/*.json` stores canonical input payloads.
- `tests/expected/*.json` stores expected recommendation level, key risk tags, `need_confirm`, and explanation substring assertions.
- Naming convention: use the same stem in both directories, for example `us1_egg_allergy_tomato_egg.json`.
- Regression cases should be offline-first; if a case depends on online fallback it must be marked separately and must not block local validation.

## Metrics Evidence Entry

- 图片样本底表：`dish-health-recommender/data/image_test_cases.json`
- 多模态字段校验：`dish-health-recommender/tests/test_multimodal.py`
- 指标产物生成：`python3 dish-health-recommender/scripts/validate_images.py`
- 指标 JSON：`dish-health-recommender/validation/image-validation-report.json`
- 当前样本统计：OCR hit rate `1.0`，Top-1 `0.3636`，Top-3 `0.3636`，health rule accuracy `0.8636`，p50/p95 latency `5083/9828ms`
- 报告对齐产物：`dish-health-recommender/validation/report-alignment-report.json`
- 建议验证顺序：先 `test_multimodal.py`，再 `validate_images.py`，再 `test_alignment.py`，最后 `report_alignment.py`

## Fixture Mapping

| 用例 | fixture | expected |
| --- | --- | --- |
| 鸡蛋过敏 + 番茄炒蛋 | `tests/fixtures/us1_egg_allergy_tomato_egg.json` | `tests/expected/us1_egg_allergy_tomato_egg.json` |
| 减脂/控糖 + 提拉米苏 | `tests/fixtures/us1_weight_loss_tiramisu.json` | `tests/expected/us1_weight_loss_tiramisu.json` |
| 海鲜过敏/严格模式 + 鱼香肉丝 | `tests/fixtures/us1_seafood_allergy_yuxiang.json` | `tests/expected/us1_seafood_allergy_yuxiang.json` |
| 低盐 + 招牌小炒 | `tests/fixtures/us1_low_salt_signature_stirfry.json` | `tests/expected/us1_low_salt_signature_stirfry.json` |
| 自定义食材 + 巧克力甜点 | `tests/fixtures/us1_custom_chocolate.json` | `tests/expected/us1_custom_chocolate.json` |
| 仅图片引用 | `tests/fixtures/us1_image_only_need_confirm.json` | `tests/expected/us1_image_only_need_confirm.json` |
| 用户画像记忆 + 油爆虾 | `tests/test_feedback.py` | `test_stored_user_profile_is_applied_to_recommendation` |
| 常见范围估算 + 鱼香肉丝 | `tests/test_quantization.py` | `test_common_range_estimate_for_known_dish_without_standard_recipe` |
