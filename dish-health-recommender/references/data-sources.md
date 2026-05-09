# Data Sources

Use domestic Chinese sources first because the target domain is Chinese dishes and WeChat-style user scenarios.

## Preferred Domestic Sources

- CookBook-KG: Chinese recipe knowledge graph. Use for dish names, aliases, ingredients, seasonings, cooking steps, cuisine, and taste tags.
- Laoxiangji public standardized recipes: use for gram-level Chinese fast-food recipe examples and nutrition calculation demonstrations.
- Chinese Nutrition Society food composition tables: use as the preferred basis for ingredient-level nutrition.
- Chinese Dietary Guidelines 2022: use for general rules such as low salt, low oil, food diversity, sugar control, and balanced diet.
- Wake Food API or Baidu food knowledge graph: optional enhancement only after access and licensing are verified.
- NutriData: currently not suitable as a runtime source. The observed web endpoints depend on short-lived session login, token headers, and encrypted request/response payloads rather than a stable anonymous public API.

## Foreign Extension Sources

- USDA FoodData Central.
- Open Food Facts.
- Edamam.
- Spoonacular.
- TheMealDB.

Use these only when domestic data is missing, international dishes are requested, or packaged-food labels are relevant.

## Evidence Policy

- If exact ingredient weights are missing, provide risk labels and qualitative advice, not exact totals.
- If multiple recipes match the same dish name, mention common variants and ask for confirmation when allergies or strict restrictions matter.
- If data source licensing or API availability is unknown, describe it as an optional source, not an implemented dependency.
- Validation and import evidence should be written to stable local artifacts under `dish-health-recommender/validation/` and `data/source_manifest.json`, so report updates can reuse the same evidence path.

## Current Implementation

当前扩展源只允许通过离线导入进入本地快照，不能变成运行时强依赖；在线源只能算可选增强，不是必需链路。

The skill currently implements CookBook-KG as the first real recipe data source:

- `scripts/fetch_cookbook_kg.py` downloads `visualization/vizdata.json` from the CookBook-KG GitHub repository.
- The fetch script converts `选材` graph edges into `data/dishes.json`.
- `scripts/recommend.py` loads `data/dishes.json` before using online fallback.
- If a dish is missing locally, `recommend.py` first tries the same CookBook-KG raw data online and builds a temporary candidate from matching recipe nodes.
- If CookBook-KG misses, `recommend.py` can further try Chinese recipe search pages in this order: `xiachufang` search, `douguo` keyword page, `xiangha` search.
- The current verified search entry shapes are:
  - `xiachufang`: `GET https://www.xiachufang.com/search/?keyword=<query>&cat=1001&via=home`
  - `douguo`: `GET https://www.douguo.com/caipu/<urlencoded-query>`
  - `xiangha`: `GET https://www.xiangha.com/so/?s=<query>`
- These three Chinese sites are runtime reference-only search providers. They are not imported into `source_manifest.json`, not treated as stable contracts, and may degrade when page structure or anti-bot behavior changes.
- If `SPOONACULAR_API_KEY` is configured by environment variable or `.local-secrets.json`, `recommend.py` can further query Spoonacular `complexSearch` as an optional reference-only recipe source.

This keeps the skill portable: it can work offline from the local JSON cache and improve coverage when the host agent can access the internet. `xiachufang`、`douguo`、`xiangha` 与 Spoonacular 都是 optional enhancement only, not required dependencies. Chinese site search pages are especially sensitive to HTML changes or access controls and should be treated as degradable runtime hints rather than guaranteed APIs.

离线导入入口：`python3 dish-health-recommender/scripts/import_sources.py`。
导入证据会落到 `dish-health-recommender/validation/source-import-report.json`，manifest 会在 `dish-health-recommender/data/source_manifest.json` 记录 `source_type`、`import_mode`、`license_status`、`target_files`、`enabled_for_runtime`、`records_imported` 与 `last_import_report`。

The skill also includes a local qualitative nutrition knowledge base:

- `data/nutrition_knowledge.json` maps common ingredients and seasonings to nutrition tags, risk tags, and cautions.
- It is used for qualitative recommendations such as `可能高盐`, `可能高糖`, `含蛋`, `含海鲜/鱼类`, `皮脂较高`.
- It does not provide exact calories, sodium, protein, carbohydrate, or fat totals.
- It should be expanded with verified food composition data before supporting precise nutrition calculations.

Nutrition lookup now follows this order:

1. Local `data/nutrition_knowledge.json`.
2. Local cache `data/nutrition_cache.json`.
3. USDA FoodData Central search API with `USDA_API_KEY`, falling back to `DEMO_KEY`.

USDA fallback is implemented for missing ingredients and returns qualitative tags plus available per-100g nutrients. It is an extension source, not the primary domestic source, and should be treated as reference data for ingredients or packaged/international foods.
