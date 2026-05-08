---
name: dish-health-recommender
description: Analyze dish names, menu text, food photos, and user health constraints to produce Chinese health-aware dish recommendations. Use when the user asks whether a dish is suitable, wants nutrition/risk reasoning, needs menu screening, or wants a portable agent skill for food recognition and recommendation without building a dedicated backend service.
---

# Dish Health Recommender

## Purpose

Use this skill to help an agent act as a dish understanding and health-aware recommendation assistant. It should work without a dedicated backend service: rely on the host agent's text, image, file, search, and memory abilities when available, and use bundled scripts for deterministic local checks when useful.

## Workflow

1. Parse the user's input:
   - Dish name, menu text, or user description.
   - Food/menu image, if the host platform provides vision.
   - User constraints: allergies, disease-related restrictions, dietary goals, preferences, dislikes.
2. Normalize and understand the dish:
   - Normalize common aliases such as `西红柿炒鸡蛋` -> `番茄炒蛋`.
   - Treat ambiguous names conservatively. For example, `鱼香肉丝` usually does not contain fish, but recipe variants should be confirmed for allergy-sensitive users.
   - Infer likely ingredients, cooking method, and risk tags; separate confirmed facts from assumptions.
3. Compare against user constraints:
   - Allergens and explicit medical restrictions have highest priority.
   - Low-salt, low-sugar, weight-loss, high-protein, vegetarian, and low-fat goals affect the recommendation level.
   - If evidence is weak or data is missing, return `需要确认` instead of a confident answer.
4. Explain the recommendation in Chinese:
   - Start with the conclusion: `推荐`、`谨慎`、`不推荐`、or `需要确认`.
   - Give 2-4 concise reasons tied to ingredients, cooking method, nutrition risk, or user constraints.
   - Ask for missing information only when it changes the answer materially.

## Using Bundled Resources

- For deterministic local MVP output, run `scripts/recommend.py` with JSON input. It now supports `dish_name`, `menu_text`, `ocr_text`, `image_reference`, `ingredients`, `user_profile`, and `output_mode`.
- For report-to-implementation evidence mapping, run `scripts/report_alignment.py` to emit or validate `ReportAlignmentItem` payloads.
- To refresh the local recipe cache from CookBook-KG, run `scripts/fetch_cookbook_kg.py`. It writes `data/dishes.json` and `data/source_manifest.json`.
- For domain rules and uncertainty policy, read `references/recommendation-rules.md`.
- For data source priorities, read `references/data-sources.md`.
- For WeChat-style responses or cross-platform prompt migration, read `references/output-templates.md`.
- For platforms that only support a single system prompt, adapt `references/platform-prompt.md`.
- For validation examples, read `references/test-cases.md`.
- For report evidence review, read `references/report-alignment-checklist.md`.

## Script Contract

`scripts/recommend.py` reads JSON from stdin or a file path argument and writes JSON to stdout.
It resolves data in this order:

1. Built-in safety examples for common dishes.
2. Local file library at `data/dishes.json`.
3. Online CookBook-KG fallback when the local library misses and network is available.
4. Local qualitative nutrition knowledge at `data/nutrition_knowledge.json` to enrich ingredient nutrition tags, risk tags, and constraint-specific cautions.
5. Online USDA FoodData Central fallback when an ingredient is missing from the local nutrition knowledge base.
6. `need_confirm` when no reliable candidate is found.

Example:

```bash
python3 dish-health-recommender/scripts/recommend.py <<'JSON'
{
  "dish_name": "番茄炒蛋",
  "user_profile": {
    "allergies": ["鸡蛋"],
    "goals": ["低脂"]
  }
}
JSON
```

Expected output fields:

- `normalized_dish`
- `recommendation`: `recommend`、`caution`、`avoid`、or `need_confirm`
- `confidence`
- `ingredients`
- `cooking_method`
- `nutrition_tags`
- `risk_tags`
- `nutrition_evidence`
- `explanation`
- `need_confirm`

The script accepts optional `ingredients` for custom dishes when a recipe is not found, and also supports `output_mode: "human_readable_cn"` for direct end-user display:

```json
{
  "dish_name": "巧克力甜点",
  "ingredients": ["chocolate"],
  "user_profile": {"conditions": ["控糖"], "goals": ["减脂"]}
}
```

## Boundaries

- Do not present outputs as medical diagnosis or treatment advice.
- Do not invent exact calories, protein, sodium, sugar, or fat values unless a verified data source is available in the current task.
- Do not claim an external API is available unless it has been tested in the current environment.
- Do not overrule allergy or severe restriction warnings based on taste preference.
- If the current runtime lacks OCR or vision, explicitly degrade and ask for text or ingredients rather than pretending image recognition succeeded.
- Use domestic Chinese recipe and nutrition knowledge first; use foreign sources only as optional extensions.
