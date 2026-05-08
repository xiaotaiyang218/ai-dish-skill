# Test Cases

Use these examples to validate the skill in Codex and other agent platforms.

## Single Dish

Input: `我鸡蛋过敏，番茄炒蛋能吃吗？`

Expected: `不推荐`; reason mentions egg allergy.

Input: `减脂期能不能吃红烧肉？`

Expected: `谨慎`; reason mentions fatty pork, sugar/oil risk, portion control.

Input: `海鲜过敏的人吃鱼香肉丝有风险吗？`

Expected: usually `谨慎` or `需要确认`; explain that common recipes do not contain fish but variants should be confirmed.

## Ambiguous Dish

Input: `招牌小炒适合低盐饮食吗？`

Expected: `需要确认`; ask for ingredients/photo/menu description.

## Script JSON

```json
{
  "dish_name": "红烧肉",
  "user_profile": {
    "goals": ["减脂"],
    "conditions": ["控糖"]
  }
}
```

Expected: `caution`; reason mentions fatty pork, sugar, oil, portion.

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

## Fixture Mapping

| 用例 | fixture | expected |
| --- | --- | --- |
| 鸡蛋过敏 + 番茄炒蛋 | `tests/fixtures/us1_egg_allergy_tomato_egg.json` | `tests/expected/us1_egg_allergy_tomato_egg.json` |
| 减脂/控糖 + 红烧肉 | `tests/fixtures/us1_weight_loss_braised_pork.json` | `tests/expected/us1_weight_loss_braised_pork.json` |
| 海鲜过敏/严格模式 + 鱼香肉丝 | `tests/fixtures/us1_seafood_allergy_yuxiang.json` | `tests/expected/us1_seafood_allergy_yuxiang.json` |
| 低盐 + 招牌小炒 | `tests/fixtures/us1_low_salt_signature_stirfry.json` | `tests/expected/us1_low_salt_signature_stirfry.json` |
| 自定义食材 + 巧克力甜点 | `tests/fixtures/us1_custom_chocolate.json` | `tests/expected/us1_custom_chocolate.json` |
| 仅图片引用 | `tests/fixtures/us1_image_only_need_confirm.json` | `tests/expected/us1_image_only_need_confirm.json` |

