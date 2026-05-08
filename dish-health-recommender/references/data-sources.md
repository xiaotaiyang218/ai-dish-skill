# Data Sources

Use domestic Chinese sources first because the target domain is Chinese dishes and WeChat-style user scenarios.

## Preferred Domestic Sources

- CookBook-KG: Chinese recipe knowledge graph. Use for dish names, aliases, ingredients, seasonings, cooking steps, cuisine, and taste tags.
- Laoxiangji public standardized recipes: use for gram-level Chinese fast-food recipe examples and nutrition calculation demonstrations.
- Chinese Nutrition Society food composition tables: use as the preferred basis for ingredient-level nutrition.
- Chinese Dietary Guidelines 2022: use for general rules such as low salt, low oil, food diversity, sugar control, and balanced diet.
- Wake Food API, Baidu food knowledge graph, or NutriData: optional enhancement only after access and licensing are verified.

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

## Current Implementation

The skill currently implements CookBook-KG as the first real recipe data source:

- `scripts/fetch_cookbook_kg.py` downloads `visualization/vizdata.json` from the CookBook-KG GitHub repository.
- The fetch script converts `选材` graph edges into `data/dishes.json`.
- `scripts/recommend.py` loads `data/dishes.json` before using online fallback.
- If a dish is missing locally, `recommend.py` tries the same CookBook-KG raw data online and builds a temporary candidate from matching recipe nodes.

This keeps the skill portable: it can work offline from the local JSON cache and improve coverage when the host agent can access the internet.

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
