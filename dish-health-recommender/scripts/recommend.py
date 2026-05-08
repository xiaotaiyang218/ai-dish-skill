#!/usr/bin/env python3
"""Local MVP recommender for dish-health-recommender skill.

This script is intentionally small and deterministic. It is not a nutrition
database; it provides a runnable baseline for agent workflows.

CLI contract: read JSON from stdin or a file path argument, print UTF-8 JSON to
stdout, and return non-zero only for invalid input or file errors.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

try:
    from providers.ocr_provider import recognize_image_text
    from providers.vision_provider import detect_dish_candidates
    from providers.nutrition_provider import QuantifiedRecipeProvider
    from scripts.image_cases import validate_all_cases, get_image_case_by_path
except ImportError:
    from .providers.ocr_provider import recognize_image_text
    from .providers.vision_provider import detect_dish_candidates
    from .providers.nutrition_provider import QuantifiedRecipeProvider
    from .scripts.image_cases import validate_all_cases, get_image_case_by_path


LOCAL_DISHES_PATH = SKILL_DIR / "data" / "dishes.json"
NUTRITION_KNOWLEDGE_PATH = SKILL_DIR / "data" / "nutrition_knowledge.json"
NUTRITION_CACHE_PATH = SKILL_DIR / "data" / "nutrition_cache.json"
COOKBOOK_KG_URL = (
    "https://raw.githubusercontent.com/ngl567/CookBook-KG/master/"
    "visualization/vizdata.json"
)
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
RECOMMENDATION_ORDER = {"recommend": 0, "caution": 1, "need_confirm": 2, "avoid": 3}
DEFAULT_PROFILE = {
    "allergies": [],
    "conditions": [],
    "goals": [],
    "preferences": [],
    "avoid": [],
    "strict_mode": False,
}
OUTPUT_MODES = {"json", "human_readable_cn"}
QUANTIFIED_PROVIDER = QuantifiedRecipeProvider()


BUILTIN_DISHES: dict[str, dict[str, Any]] = {
    "番茄炒蛋": {
        "aliases": ["西红柿炒鸡蛋", "番茄炒鸡蛋"],
        "ingredients": ["番茄", "鸡蛋", "油", "盐"],
        "cooking_method": "炒",
        "risk_tags": ["含蛋", "可能高油", "可能加盐"],
        "notes": "家常菜，主要风险来自鸡蛋过敏、用油和加盐量。",
        "ambiguity_level": "low",
    },
    "红烧肉": {
        "aliases": ["红烧五花肉"],
        "ingredients": ["五花肉", "酱油", "糖", "油"],
        "cooking_method": "红烧",
        "risk_tags": ["高脂", "可能高糖", "可能高盐"],
        "notes": "通常脂肪较高，红烧做法常含糖和酱油。",
        "ambiguity_level": "low",
    },
    "清蒸鲈鱼": {
        "aliases": ["蒸鲈鱼"],
        "ingredients": ["鲈鱼", "姜", "葱", "蒸鱼豉油"],
        "cooking_method": "蒸",
        "risk_tags": ["含鱼", "可能含钠"],
        "notes": "蒸制相对清淡，但鱼类过敏或低盐用户需确认调味。",
        "ambiguity_level": "low",
    },
    "鱼香肉丝": {
        "aliases": [],
        "ingredients": ["猪肉", "木耳", "胡萝卜", "豆瓣酱", "糖", "醋"],
        "cooking_method": "炒",
        "risk_tags": ["可能高油", "可能高糖", "可能高盐", "歧义菜名"],
        "notes": "常见做法通常不含鱼，但不同餐厅配方可能变化。",
        "ambiguity_level": "high",
    },
}


def load_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_local_dishes() -> dict[str, dict[str, Any]]:
    dishes = dict(BUILTIN_DISHES)
    external = load_json_file(LOCAL_DISHES_PATH, {})
    for name, info in external.items():
        merged = {
            "aliases": [],
            "ingredients": [],
            "cooking_method": None,
            "risk_tags": [],
            "notes": "",
            "source": "local",
            "ambiguity_level": "low",
        }
        merged.update(info)
        dishes[name] = merged
    return dishes


DISHES = load_local_dishes()


def load_nutrition_knowledge() -> dict[str, Any]:
    return load_json_file(NUTRITION_KNOWLEDGE_PATH, {"ingredients": {}, "diet_rules": {}})


NUTRITION = load_nutrition_knowledge()
NUTRITION_CACHE = load_json_file(NUTRITION_CACHE_PATH, {})


def save_nutrition_cache(cache: dict[str, Any]) -> None:
    try:
        NUTRITION_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def build_aliases(dishes: dict[str, dict[str, Any]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical, info in dishes.items():
        aliases[canonical] = canonical
        for alias in info.get("aliases", []):
            aliases[str(alias).strip()] = canonical
    return aliases


ALIASES = build_aliases(DISHES)

RISK_KEYWORDS = {
    "鸡蛋": ["鸡蛋", "蛋", "蛋制品", "含蛋"],
    "海鲜": ["虾", "蟹", "贝", "鱼", "海鲜", "鱼露", "虾皮", "含海鲜/鱼类"],
    "坚果": ["花生", "坚果", "芝麻", "芝麻酱", "花生酱"],
    "低盐": ["盐", "酱油", "豆瓣酱", "腌", "咸", "可能高盐", "可能含钠"],
    "控糖": ["糖", "蜂蜜", "糖醋", "红烧", "可能高糖", "碳水来源"],
    "减脂": ["五花肉", "肥肉", "油炸", "高脂", "奶油", "高油", "可能高脂", "可能高油", "皮脂较高"],
    "高蛋白": ["优质蛋白", "蛋白质来源", "瘦肉", "鱼类", "禽肉"],
    "痛风": ["动物内脏", "浓肉汤", "海鲜", "啤酒", "高嘌呤"],
    "素食": ["猪肉", "牛肉", "羊肉", "鸡肉", "鱼", "虾", "鸡蛋"],
}


def stable_list(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return sorted(seen)


def load_input() -> dict[str, Any]:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.exists():
            raise SystemExit(f"Input file not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    return json.load(sys.stdin)


def parse_request(payload: dict[str, Any]) -> dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    raw_profile = payload.get("user_profile") or {}
    if isinstance(raw_profile, dict):
        profile.update(raw_profile)
    output_mode = str(payload.get("output_mode") or "json")
    if output_mode not in OUTPUT_MODES:
        output_mode = "json"
    ingredients = payload.get("ingredients") or []
    if not isinstance(ingredients, list):
        ingredients = [str(ingredients)]
    return {
        "dish_name": str(payload.get("dish_name") or "").strip(),
        "menu_text": str(payload.get("menu_text") or "").strip(),
        "ocr_text": str(payload.get("ocr_text") or "").strip(),
        "image_reference": str(payload.get("image_reference") or "").strip(),
        "image_path": str(payload.get("image_path") or payload.get("image_reference") or "").strip(),
        "ingredients": [str(item).strip() for item in ingredients if str(item).strip()],
        "cooking_method": payload.get("cooking_method"),
        "user_profile": profile,
        "output_mode": output_mode,
    }


def pick_raw_name(request: dict[str, Any]) -> str:
    return request["dish_name"] or request["menu_text"] or request["ocr_text"]


def infer_method(name: str) -> str | None:
    for hint, method in {
        "红烧": "红烧",
        "糖醋": "糖醋",
        "可乐": "烧",
        "水煮": "水煮",
        "炒": "炒",
        "蒸": "蒸",
        "煎": "煎",
        "炖": "炖",
        "凉拌": "凉拌",
        "意面": "煮/炒",
    }.items():
        if hint in name:
            return method
    return None


def infer_risk_tags(name: str, ingredients: list[str]) -> list[str]:
    text = " ".join([name] + ingredients)
    tags: list[str] = []
    if any(word in text for word in ["鸡蛋", "蛋清", "蛋黄"]):
        tags.append("含蛋")
    if any(word in text for word in ["鱼", "虾", "蟹", "贝", "海鲜"]):
        tags.append("含海鲜/鱼类")
    if any(word in text for word in ["五花肉", "肥肉", "培根"]):
        tags.append("可能高脂")
    if any(word in text for word in ["糖", "冰糖", "可乐", "糖醋", "红烧"]):
        tags.append("可能高糖")
    if any(word in text for word in ["盐", "酱油", "生抽", "老抽", "豆瓣酱"]):
        tags.append("可能高盐")
    return stable_list(tags)


def normalize_dish(raw: str) -> tuple[str | None, float, list[dict[str, Any]]]:
    raw = (raw or "").strip()
    if not raw:
        return None, 0.0, []
    if raw in ALIASES:
        canonical = ALIASES[raw]
        return canonical, 0.98 if canonical == raw else 0.95, [{"canonical_name": canonical, "confidence": 0.98 if canonical == raw else 0.95}]

    candidate_scores: dict[str, float] = {}
    for alias, canonical in ALIASES.items():
        if raw in alias or alias in raw:
            score = 0.86 if alias != canonical else 0.82
            candidate_scores[canonical] = max(candidate_scores.get(canonical, 0.0), score)

    for canonical in DISHES:
        if raw in canonical or canonical in raw:
            candidate_scores[canonical] = max(candidate_scores.get(canonical, 0.0), 0.8)

    candidates = [
        {
            "canonical_name": name,
            "confidence": score,
            "ambiguity_level": DISHES.get(name, {}).get("ambiguity_level", "low"),
            "source": DISHES.get(name, {}).get("source", "local"),
        }
        for name, score in sorted(candidate_scores.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]
    if candidates:
        return candidates[0]["canonical_name"], candidates[0]["confidence"], candidates
    return raw, 0.35, [{"canonical_name": raw, "confidence": 0.35}]


def profile_terms(profile: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for key in ("allergies", "conditions", "goals", "preferences", "avoid"):
        value = profile.get(key, [])
        if isinstance(value, str):
            terms.append(value)
        elif isinstance(value, list):
            terms.extend(str(item) for item in value)
    return [term for term in terms if term]


def contains_any(values: list[str], keywords: list[str]) -> bool:
    text = " ".join(values)
    return any(keyword in text for keyword in keywords)


def nutrient_value(food: dict[str, Any], names: list[str]) -> float | None:
    for item in food.get("foodNutrients", []):
        nutrient_name = str(item.get("nutrientName", "")).lower()
        if any(name.lower() in nutrient_name for name in names):
            try:
                return float(item.get("value"))
            except (TypeError, ValueError):
                return None
    return None


def fetch_usda_nutrition(query: str) -> dict[str, Any] | None:
    if query in NUTRITION_CACHE:
        return NUTRITION_CACHE[query]
    api_key = os.environ.get("USDA_API_KEY", "DEMO_KEY")
    params = urllib.parse.urlencode({"query": query, "pageSize": 1, "api_key": api_key})
    try:
        with urllib.request.urlopen(f"{USDA_SEARCH_URL}?{params}", timeout=12) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    foods = raw.get("foods") or []
    if not foods:
        return None
    food = foods[0]
    energy = nutrient_value(food, ["Energy"])
    fat = nutrient_value(food, ["Total lipid", "fat"])
    sugars = nutrient_value(food, ["Total Sugars", "Sugars"])
    sodium = nutrient_value(food, ["Sodium"])
    protein = nutrient_value(food, ["Protein"])

    nutrition_tags: list[str] = []
    risk_tags: list[str] = []
    cautions: list[str] = []
    if protein is not None and protein >= 8:
        nutrition_tags.append("蛋白质来源")
    if fat is not None and fat >= 20:
        risk_tags.append("可能高脂")
        cautions.append("USDA 数据显示脂肪含量可能较高，减脂或低脂人群应控制。")
    if sugars is not None and sugars >= 10:
        risk_tags.append("可能高糖")
        cautions.append("USDA 数据显示糖含量可能较高，控糖人群应控制。")
    if sodium is not None and sodium >= 600:
        risk_tags.append("可能高盐")
        cautions.append("USDA 数据显示钠含量可能较高，低盐人群应控制。")
    if energy is not None and energy >= 400:
        nutrition_tags.append("能量较高")

    result = {
        "source": "USDA FoodData Central",
        "matched_food": food.get("description"),
        "fdc_id": food.get("fdcId"),
        "nutrition_tags": stable_list(nutrition_tags),
        "risk_tags": stable_list(risk_tags),
        "cautions": stable_list(cautions),
        "nutrients_per_100g": {
            "energy_kcal": energy,
            "protein_g": protein,
            "fat_g": fat,
            "sugars_g": sugars,
            "sodium_mg": sodium,
        },
    }
    NUTRITION_CACHE[query] = result
    save_nutrition_cache(NUTRITION_CACHE)
    return result


def fetch_cookbook_kg_candidate(query: str) -> tuple[str, dict[str, Any]] | None:
    try:
        with urllib.request.urlopen(COOKBOOK_KG_URL, timeout=12) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    ingredients_by_dish: dict[str, list[str]] = {}
    for link in raw.get("links", []):
        if link.get("relation") != "选材":
            continue
        source = str(link.get("source", "")).strip()
        target = str(link.get("target", "")).strip()
        if not source or not target:
            continue
        ingredients_by_dish.setdefault(source, [])
        if target not in ingredients_by_dish[source]:
            ingredients_by_dish[source].append(target)

    candidates = [name for name in ingredients_by_dish if query in name or name in query]
    if not candidates:
        return None
    name = sorted(candidates, key=lambda item: (len(item), item))[0]
    ingredients = ingredients_by_dish[name]
    return name, {
        "aliases": [],
        "ingredients": ingredients,
        "cooking_method": infer_method(name),
        "risk_tags": infer_risk_tags(name, ingredients),
        "notes": "联网从 CookBook-KG mini 图谱查询到的候选菜谱，仅作为参考。",
        "source": "CookBook-KG online",
        "ambiguity_level": "medium",
    }


def enrich_from_nutrition(ingredients: list[str], base_risk_tags: list[str]) -> dict[str, Any]:
    ingredient_db = NUTRITION.get("ingredients", {})
    nutrition_tags: list[str] = []
    risk_tags = list(base_risk_tags)
    cautions: list[str] = []
    matched: dict[str, Any] = {}

    for ingredient in ingredients:
        info = ingredient_db.get(ingredient)
        if not info:
            for key, value in ingredient_db.items():
                if key in ingredient or ingredient in key:
                    info = value
                    break
        if not info:
            online = fetch_usda_nutrition(ingredient)
            if not online:
                continue
            matched[ingredient] = online
            nutrition_tags.extend(online.get("nutrition_tags", []))
            risk_tags.extend(online.get("risk_tags", []))
            cautions.extend(online.get("cautions", []))
            continue
        matched[ingredient] = {
            "nutrition_tags": info.get("nutrition_tags", []),
            "risk_tags": info.get("risk_tags", []),
            "cautions": info.get("cautions", []),
        }
        nutrition_tags.extend(info.get("nutrition_tags", []))
        risk_tags.extend(info.get("risk_tags", []))
        cautions.extend(info.get("cautions", []))

    return {
        "nutrition_tags": stable_list(nutrition_tags),
        "risk_tags": stable_list(risk_tags),
        "cautions": stable_list(cautions),
        "matched_ingredients": matched,
    }


def choose_recommendation(current: str, new: str) -> str:
    return new if RECOMMENDATION_ORDER[new] > RECOMMENDATION_ORDER[current] else current


def diet_rule_reasons(terms: list[str], risk_tags: list[str], nutrition_tags: list[str]) -> list[str]:
    reasons: list[str] = []
    rules = NUTRITION.get("diet_rules", {})
    for term in terms:
        for rule_name, rule in rules.items():
            if rule_name not in term and term not in rule_name:
                continue
            hit_risk = any(tag in risk_tags for tag in rule.get("match_risk_tags", []))
            hit_nutrition = any(tag in nutrition_tags for tag in rule.get("match_nutrition_tags", []))
            if hit_risk or hit_nutrition:
                reasons.append(rule.get("message", "命中饮食约束规则。"))
    return stable_list(reasons)


def relevant_cautions(terms: list[str], cautions: list[str]) -> list[str]:
    if not terms:
        return []
    result: list[str] = []
    term_text = " ".join(terms)
    for caution in cautions:
        if any(term in caution for term in terms):
            result.append(caution)
            continue
        if "过敏" in term_text and "过敏" in caution:
            result.append(caution)
        elif any(word in term_text for word in ["低盐", "高血压"]) and any(word in caution for word in ["低盐", "血压", "钠"]):
            result.append(caution)
        elif any(word in term_text for word in ["控糖", "糖尿病"]) and any(word in caution for word in ["控糖", "糖"]):
            result.append(caution)
        elif any(word in term_text for word in ["减脂", "低脂"]) and any(word in caution for word in ["减脂", "低脂", "脂"]):
            result.append(caution)
        elif any(word in term_text for word in ["高蛋白", "增肌"]) and "蛋白" in caution:
            result.append(caution)
    return stable_list(result)


def build_result(
    *,
    normalized_dish: str | None,
    recommendation: str,
    confidence: float,
    ingredients: list[str],
    cooking_method: str | None,
    nutrition_tags: list[str],
    risk_tags: list[str],
    nutrition_evidence: dict[str, Any],
    explanation: str,
    need_confirm: list[str],
    candidates: list[dict[str, Any]] | None = None,
    degraded_input: list[str] | None = None,
    output_mode: str = "json",
) -> dict[str, Any]:
    result = {
        "normalized_dish": normalized_dish,
        "recommendation": recommendation,
        "confidence": round(float(confidence), 2),
        "ingredients": stable_list(ingredients),
        "cooking_method": cooking_method,
        "nutrition_tags": stable_list(nutrition_tags),
        "risk_tags": stable_list(risk_tags),
        "nutrition_evidence": nutrition_evidence,
        "explanation": explanation,
        "need_confirm": stable_list(need_confirm),
    }
    if candidates:
        result["candidates"] = candidates
    if degraded_input:
        result["degraded_input"] = stable_list(degraded_input)
    if output_mode == "human_readable_cn":
        result["human_readable_cn"] = render_human_readable_cn(result)
    return result


def render_human_readable_cn(result: dict[str, Any]) -> str:
    label = {
        "recommend": "推荐",
        "caution": "谨慎",
        "avoid": "不推荐",
        "need_confirm": "需要确认",
    }[result["recommendation"]]
    reasons: list[str] = []
    explanation = result.get("explanation", "")
    if "依据：" in explanation:
        reasons = [part for part in explanation.split("依据：", 1)[1].split("；") if part]
    reasons = reasons[:4] or ["当前证据不足，请补充信息后再判断。"]
    need_confirm = result.get("need_confirm") or ["暂无"]
    lines = [f"结论：{label}", "", "原因："]
    for idx, reason in enumerate(reasons, 1):
        lines.append(f"{idx}. {reason}")
    lines.extend([
        "",
        f"建议：{'；'.join(need_confirm) if result['recommendation'] == 'need_confirm' else '结合实际配方和份量选择，必要时少盐少油并控制份量。'}",
        f"需要确认：{'；'.join(need_confirm)}",
        "提示：以上仅作饮食参考，不能替代医生或营养师建议。",
    ])
    return "\n".join(lines)




def load_feedback_store() -> dict[str, Any]:
    return load_json_file(SKILL_DIR / "data" / "feedback.json", {"events": [], "bias": {}, "corrections": {}})


def build_provider_context(request: dict[str, Any]) -> dict[str, Any]:
    image_path = request.get("image_path") or request.get("image_reference")
    if image_path and not Path(image_path).is_absolute():
        image_path = str(SKILL_DIR.parent / image_path)
    image_path = image_path if image_path and Path(image_path).exists() else ""
    summary = validate_all_cases()
    image_case = get_image_case_by_path(image_path) if image_path else None
    allow_ocr = bool(image_path) and (bool(image_case) or 'pic/' in image_path or '/pic/' in image_path)
    return {
        "image_path": image_path,
        "image_case": image_case,
        "ocr_result": recognize_image_text(image_path) if allow_ocr else None,
        "vision_result": detect_dish_candidates(image_path) if allow_ocr else None,
        "image_cases_total": summary.get("total", 0),
        "allow_ocr": allow_ocr,
    }


def quantized_profile_for_dish(dish_name: str) -> dict[str, Any] | None:
    return QUANTIFIED_PROVIDER.find(dish_name)


def corrected_raw_name(raw_name: str) -> str:
    store = load_feedback_store()
    return (store.get("corrections") or {}).get(raw_name, raw_name)


def image_candidate_terms(request: dict[str, Any], provider_context: dict[str, Any]) -> list[str]:
    stopwords = {"Administration", "行政", "特色档口菜单", "主荤", "半荤", "素菜", "例汤", "主食", "粗粮", "小吃"}
    terms: list[str] = []
    if request.get("ocr_text"):
        terms.extend(part.strip() for part in re.split(r"[\s,，、/]+", request["ocr_text"]) if part.strip())
    ocr_result = provider_context.get("ocr_result")
    if ocr_result:
        terms.extend(line.strip() for line in (ocr_result.lines or []) if line.strip())
    vision_result = provider_context.get("vision_result")
    if vision_result:
        terms.extend(item.strip() for item in (vision_result.candidates or []) if item.strip())
    filtered: list[str] = []
    for term in terms:
        if term in stopwords:
            continue
        if len(term) < 2:
            continue
        if term not in filtered:
            filtered.append(term)
    return filtered


def choose_image_seed_candidate(request: dict[str, Any], provider_context: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    ranked: dict[str, dict[str, Any]] = {}
    for term in image_candidate_terms(request, provider_context):
        normalized, confidence, candidates = normalize_dish(term)
        if not normalized:
            continue
        item = {
            "raw_name": term,
            "canonical_name": normalized,
            "confidence": confidence,
            "source": "image_provider",
            "candidates": candidates,
        }
        previous = ranked.get(normalized)
        if previous is None or confidence > previous["confidence"]:
            ranked[normalized] = item
    ordered = sorted(ranked.values(), key=lambda item: (-item["confidence"], item["canonical_name"]))
    if not ordered:
        return None, []
    top = ordered[0]
    second = ordered[1] if len(ordered) > 1 else None
    if top["confidence"] >= 0.88 and (second is None or top["confidence"] - second["confidence"] >= 0.08):
        return top, ordered[:5]
    if top["confidence"] >= 0.95 and second is None:
        return top, ordered[:5]
    return None, ordered[:5]


def apply_feedback_bias(result: dict[str, Any], normalized_dish: str | None) -> dict[str, Any]:
    if not normalized_dish:
        return result
    store = load_feedback_store()
    bias = (store.get("bias") or {}).get(normalized_dish, {})
    if not bias:
        return result
    result["feedback_bias"] = {normalized_dish: bias}
    accepts = int(bias.get("accepts", 0) or 0)
    rejects = int(bias.get("rejects", 0) or 0)
    favorites = int(bias.get("favorites", 0) or 0)
    confidence_delta = 0.03 * accepts + 0.05 * favorites - 0.04 * rejects
    result["confidence"] = round(min(1.0, max(0.0, float(result.get("confidence", 0)) + confidence_delta)), 2)
    explanation = result.get("explanation", "")
    notes: list[str] = []
    if accepts > 0:
        notes.append(f"历史接受 {accepts} 次")
    if favorites > 0:
        notes.append(f"历史收藏 {favorites} 次")
    if rejects > 0:
        notes.append(f"历史拒绝 {rejects} 次")
    if rejects > 0:
        if result.get("recommendation") == "recommend":
            result["recommendation"] = "caution"
        elif result.get("recommendation") == "caution" and rejects >= accepts + favorites:
            result["recommendation"] = "avoid"
        if not result.get("need_confirm"):
            result["need_confirm"] = []
        if "近期反馈偏好" not in result["need_confirm"]:
            result["need_confirm"].append("近期反馈偏好")
    if notes:
        addition = f"；用户反馈信号：{'，'.join(notes)}。"
        if explanation and not explanation.endswith('。'):
            explanation += '。'
        result["explanation"] = (explanation or "结论：需要确认。依据：") + addition if explanation else f"结论：需要确认。依据：用户反馈信号：{'，'.join(notes)}。"
    return result


def recommend(payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_request(payload)
    provider_context = build_provider_context(request)
    if not request.get("ocr_text") and provider_context.get("ocr_result") and provider_context["ocr_result"].text:
        useful_lines = [
            line for line in (provider_context["ocr_result"].lines or [])
            if re.search(r'[\u4e00-\u9fff]{2,}', line)
            and 'Administration' not in line
            and '行政' not in line
            and '特色档口菜单' not in line
            and len(line) >= 3
        ]
        joined = ' '.join(useful_lines)
        if useful_lines and len(joined) <= 120:
            request["ocr_text"] = joined
    raw_name = corrected_raw_name(pick_raw_name(request))
    profile = request["user_profile"]
    terms = profile_terms(profile)
    degraded_input: list[str] = []
    image_seed, image_seed_candidates = choose_image_seed_candidate(request, provider_context)

    if not raw_name and image_seed:
        raw_name = image_seed["raw_name"]
        degraded_input.append("image_inferred_dish_name")

    if request["image_reference"] and not raw_name and not image_seed:
        degraded_input.append("image_reference_without_ocr")
        result = build_result(
            normalized_dish=None,
            recommendation="need_confirm",
            confidence=0.0,
            ingredients=request["ingredients"],
            cooking_method=request["cooking_method"],
            nutrition_tags=[],
            risk_tags=["缺少可用图片识别结果"],
            nutrition_evidence={},
            explanation="结论：需要确认。依据：当前输入只有图片引用，但 OCR 与视觉候选都不足以稳定识别菜品，请补充菜名、OCR 文本或主要食材。",
            need_confirm=["菜名", "OCR文本", "主要食材"],
            candidates=image_seed_candidates,
            degraded_input=degraded_input,
            output_mode=request["output_mode"],
        )
        if provider_context.get("ocr_result") or provider_context.get("vision_result"):
            result["raw_image_result"] = {
                "ocr": provider_context["ocr_result"].to_dict() if provider_context.get("ocr_result") else {},
                "vision": provider_context["vision_result"].to_dict() if provider_context.get("vision_result") else {},
            }
        return result

    normalized, confidence, candidates = normalize_dish(raw_name)
    if request.get("image_reference") and not request.get("dish_name") and normalized and "image_inferred_dish_name" not in degraded_input:
        degraded_input.append("image_inferred_dish_name")
    if image_seed and normalized == image_seed["canonical_name"]:
        confidence = max(confidence, image_seed["confidence"])
    if image_seed_candidates:
        merged_candidates: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for item in candidates + [
            {
                "canonical_name": candidate["canonical_name"],
                "confidence": candidate["confidence"],
                "source": candidate.get("source", "image_provider"),
            }
            for candidate in image_seed_candidates
        ]:
            canonical_name = item.get("canonical_name")
            if not canonical_name or canonical_name in seen_names:
                continue
            seen_names.add(canonical_name)
            merged_candidates.append(item)
        candidates = merged_candidates
    if not normalized and not request["ingredients"]:
        result = build_result(
            normalized_dish=None,
            recommendation="need_confirm",
            confidence=0.0,
            ingredients=[],
            cooking_method=None,
            nutrition_tags=[],
            risk_tags=[],
            nutrition_evidence={},
            explanation="结论：需要确认。依据：需要提供菜名、菜单文字、OCR 文本、主要食材或可解析图片信息，才能判断是否适合食用。",
            need_confirm=["菜名或图片", "主要食材"],
            candidates=provider_context.get("vision_result").to_dict().get("candidates", []) if provider_context.get("vision_result") else [],
            output_mode=request["output_mode"],
        )
        if provider_context.get("ocr_result") or provider_context.get("vision_result"):
            result["raw_image_result"] = {
                "ocr": provider_context["ocr_result"].to_dict() if provider_context.get("ocr_result") else {},
                "vision": provider_context["vision_result"].to_dict() if provider_context.get("vision_result") else {},
            }
        return result

    info = DISHES.get(normalized) if normalized else None
    if not info and normalized:
        online_candidate = fetch_cookbook_kg_candidate(normalized)
        if online_candidate:
            normalized, info = online_candidate
            confidence = max(confidence, 0.6)
    if not info and request["ingredients"]:
        info = {
            "aliases": [],
            "ingredients": request["ingredients"],
            "cooking_method": request["cooking_method"] or infer_method(normalized or ""),
            "risk_tags": infer_risk_tags(normalized or "自定义菜品", request["ingredients"]),
            "notes": "用户提供了食材，系统基于本地和联网营养知识进行参考判断。",
            "source": "user_supplied",
            "ambiguity_level": "medium",
        }
        confidence = max(confidence, 0.5)

    if not info:
        return build_result(
            normalized_dish=normalized,
            recommendation="need_confirm",
            confidence=confidence,
            ingredients=[],
            cooking_method=None,
            nutrition_tags=[],
            risk_tags=["未知菜品"],
            nutrition_evidence={},
            explanation=f"结论：需要确认。依据：本地库和联网兜底均未找到“{normalized}”，请补充主要食材、做法或 OCR 文本后再判断。",
            need_confirm=["主要食材", "烹饪方式", "OCR文本"],
            candidates=candidates,
            degraded_input=degraded_input,
            output_mode=request["output_mode"],
        )

    ingredients = list(info.get("ingredients", []))
    nutrition = enrich_from_nutrition(ingredients, list(info.get("risk_tags", [])))
    risk_tags = list(nutrition["risk_tags"])
    nutrition_tags = list(nutrition["nutrition_tags"])
    nutrition_cautions = nutrition["cautions"]
    reasons: list[str] = []
    need_confirm: list[str] = []
    recommendation = "recommend"
    ambiguity_level = str(info.get("ambiguity_level") or "low")

    if contains_any(terms, ["鸡蛋", "蛋过敏", "蛋制品"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["鸡蛋"]):
        recommendation = choose_recommendation(recommendation, "avoid")
        reasons.append("用户存在鸡蛋相关限制，菜品可能含鸡蛋或蛋制品。")

    if contains_any(terms, ["海鲜", "鱼", "虾", "蟹"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["海鲜"]):
        recommendation = choose_recommendation(recommendation, "avoid")
        reasons.append("用户存在海鲜/鱼类相关限制，菜品含相关食材或调味风险。")

    if contains_any(terms, ["坚果", "花生", "芝麻"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["坚果"]):
        recommendation = choose_recommendation(recommendation, "avoid")
        reasons.append("用户存在坚果/芝麻相关限制，需避免相关食材或酱料。")

    if contains_any(terms, ["低盐", "高血压"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["低盐"]):
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append("菜品可能使用盐、酱油或豆瓣酱，低盐或血压管理人群应控制调味。")

    if contains_any(terms, ["控糖", "糖尿病"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["控糖"]):
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append("菜品可能含糖、勾芡或红烧调味，控糖人群需关注总量和份量。")

    if contains_any(terms, ["减脂", "低脂"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["减脂"]):
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append("菜品可能脂肪或用油较高，减脂或低脂用户建议少量食用。")

    if contains_any(terms, ["高蛋白", "增肌"]) and not contains_any(nutrition_tags + ingredients, RISK_KEYWORDS["高蛋白"]):
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append("当前菜品不一定是稳定高蛋白来源，如有增肌需求建议搭配更明确的优质蛋白食物。")

    if contains_any(terms, ["素食", "纯素"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["素食"]):
        recommendation = choose_recommendation(recommendation, "avoid")
        reasons.append("菜品包含动物性食材，不符合素食限制。")

    if contains_any(terms, ["痛风", "高尿酸"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["痛风"]):
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append("菜品可能含海鲜、浓味肉类或高嘌呤风险食材，痛风/高尿酸人群应谨慎。")

    for reason in diet_rule_reasons(terms, risk_tags, nutrition_tags):
        if any(token in reason for token in ["高蛋白目标", "增肌场景", "优先选择明确的瘦肉"]):
            reasons.append(reason)
            continue
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append(reason)

    if "歧义菜名" in risk_tags or ambiguity_level == "high":
        if recommendation != "avoid":
            recommendation = choose_recommendation(recommendation, "need_confirm" if profile.get("strict_mode") else "caution")
        need_confirm.append("具体配方")
        reasons.append("该菜名存在歧义或餐厅配方差异，严格限制场景下需确认实际食材。")

    if request["image_reference"] and not request["ocr_text"]:
        if image_seed:
            reasons.append("当前结论已参考图片 OCR/视觉候选参与主链路识别，低置信度场景仍建议人工确认。")
            if confidence < 0.95:
                need_confirm.append("图片识别候选")
        else:
            degraded_input.append("image_reference_without_ocr")
            need_confirm.append("OCR文本")
            reasons.append("已收到图片引用，但当前流程未获得足够稳定的 OCR/视觉候选，建议补充 OCR 文本。")

    if request["ocr_text"] and not request["dish_name"]:
        degraded_input.append("ocr_text_inferred")
        reasons.append("当前菜名基于 OCR 文本推断，若菜单排版复杂请人工确认标准菜名。")

    if not reasons:
        reasons.append(str(info.get("notes") or "当前菜品无明显高风险标签，建议结合实际做法判断。"))
    reasons.extend(relevant_cautions(terms, nutrition_cautions)[:2])
    unique_reasons = []
    for reason in reasons:
        if reason not in unique_reasons:
            unique_reasons.append(reason)
    reasons = unique_reasons[:4]
    if recommendation == "need_confirm" and not need_confirm:
        need_confirm.extend(["主要食材", "具体做法"])
    conclusion = {
        "recommend": "推荐",
        "caution": "谨慎",
        "avoid": "不推荐",
        "need_confirm": "需要确认",
    }[recommendation]
    explanation = f"结论：{conclusion}。依据：{'；'.join(reasons)}"
    result = build_result(
        normalized_dish=normalized,
        recommendation=recommendation,
        confidence=confidence,
        ingredients=ingredients,
        cooking_method=info.get("cooking_method"),
        nutrition_tags=nutrition_tags,
        risk_tags=risk_tags,
        nutrition_evidence=nutrition["matched_ingredients"],
        explanation=explanation,
        need_confirm=need_confirm,
        candidates=candidates,
        degraded_input=degraded_input,
        output_mode=request["output_mode"],
    )
    if provider_context.get("ocr_result") or provider_context.get("vision_result"):
        result["raw_image_result"] = {
            "ocr": provider_context["ocr_result"].to_dict() if provider_context.get("ocr_result") else {},
            "vision": provider_context["vision_result"].to_dict() if provider_context.get("vision_result") else {},
        }
    quantified = quantized_profile_for_dish(result.get("normalized_dish") or "")
    if quantified:
        result["nutrition_quantitative"] = {k: quantified.get(k) for k in ["energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "sugars_g", "sodium_mg"] if quantified.get(k) is not None}
        result["nutrition_basis"] = quantified.get("nutrition_basis")
        result["portion_basis"] = quantified.get("portion_basis")
    result = apply_feedback_bias(result, result.get("normalized_dish"))
    return result


def main() -> None:
    payload = load_input()
    print(json.dumps(recommend(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
