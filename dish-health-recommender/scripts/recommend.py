#!/usr/bin/env python3
"""Local MVP recommender for dish-health-recommender skill.

This script is intentionally small and deterministic. It is not a nutrition
database; it provides a runnable baseline for agent workflows.

CLI contract: read JSON from stdin or a file path argument, print UTF-8 JSON to
stdout, and return non-zero only for invalid input or file errors.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from local_config import get_secret, local_secret_hint

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
XIA_CHU_FANG_SEARCH_URL = "https://www.xiachufang.com/search/"
DOU_GUO_SEARCH_URL = "https://www.douguo.com/caipu/"
XIANG_HA_SEARCH_URL = "https://www.xiangha.com/so/"
SPOONACULAR_COMPLEX_SEARCH_URL = "https://api.spoonacular.com/recipes/complexSearch"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
RECOMMENDATION_ORDER = {"recommend": 0, "caution": 1, "need_confirm": 2, "avoid": 3}
IMAGE_TEXT_STOPWORDS = {
    "Administration", "行政", "特色档口菜单", "清真菜单", "档口位置", "主荤", "半荤", "素菜", "例汤", "主食", "粗粮", "小吃",
    "双拼套餐", "三拼套餐", "配菜", "水果", "汤品", "热轻食", "冷轻食", "单品", "经典", "招牌", "特色", # 增加通用低价值词
}
IMAGE_TEXT_SUBSTRINGS = [
    "菜单", "档口", "位置", "四选一", "三选一", "件套", "配餐", "饮料", "小食", "永远好滋味",
    "hot wings", "french fries", "pepsi", "cola", "lemon tea", "egg tart", "potato", "gravy",
]
IMAGE_DISH_HINTS = [
    "饭", "面", "汤", "粉", "鱼", "虾", "鸡", "肉", "菜", "饺", "馄饨", "堡", "豆腐", "肠粉", "手抓饭", "烤翅", "鸡翅", "鸡腿", "牛肚", "牛肉",
    "鸭", "鳝", "蟹", "草头", "圈子", "肥肠", "大肠", "猪蹄", "猪尾", "煲", "锅", "粥", "米线", "麻辣烫", "烤鸭", "炒", "拌饭", "烧味", "水煮",
]
KNOWN_IMAGE_DISH_TERMS = {"腌笃鲜", "酱鸭", "猪蹄", "草头圈子", "响油鳝丝", "蟹粉豆腐"}
MENU_LINE_STOPWORDS = {
    "Administration", "行政", "双拼套餐", "三拼套餐", "档口菜单", "轻能补给站", "主荤", "冷轻食", "热轻食", "水果", "主食", "汤品",
    "配菜", "档口位置", "清真菜单",
}
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
        "notes": "本帮菜里的浓油赤酱代表菜，五花肉经黄酒、酱油、糖慢烧后酱色油亮、甜咸厚重；主要健康风险来自肥肉、糖和高钠调味。",
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
QUANTIFIED_ALIASES: dict[str, str] = {}
for recipe in QUANTIFIED_PROVIDER.load().get('recipes', []):
    canonical = str(recipe.get('dish_name') or '').strip()
    if not canonical:
        continue
    QUANTIFIED_ALIASES[canonical] = canonical
    for alias in recipe.get('aliases', []):
        alias_name = str(alias).strip()
        if alias_name:
            QUANTIFIED_ALIASES[alias_name] = canonical

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

INHERENT_CAUTION_RISK_TAGS = {"动物内脏", "高嘌呤"}
INHERENT_CAUTION_CLUSTER_TAGS = {"可能高脂", "可能高油", "可能高盐", "可能高糖", "红肉"}


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
    context_tags = payload.get("context_tags") or []
    if not isinstance(context_tags, list):
        context_tags = [str(context_tags)]
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
        "user_id": str(payload.get("user_id") or "").strip(),
        "context_tags": [str(item).strip() for item in context_tags if str(item).strip()],
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


def normalize_online_query(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-鿿]+", "", str(text or "").strip()).lower()


def overlap_score(query: str, title: str) -> int:
    normalized_query = normalize_online_query(query)
    normalized_title = normalize_online_query(title)
    if not normalized_query or not normalized_title:
        return 0
    if normalized_query == normalized_title:
        return 10
    if normalized_query in normalized_title or normalized_title in normalized_query:
        return 7
    common = {char for char in normalized_query if char in normalized_title}
    return len(common)


def online_recipe_request(url: str, headers: dict[str, str] | None = None, timeout: int = 8) -> str | None:
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "ignore")
    except Exception:
        return None


def clean_recipe_title(title: str) -> str:
    text = html.unescape(str(title or "")).strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip("-_|｜· ")


def contains_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", str(text or "")))


def stripped_online_match_text(text: str) -> str:
    normalized = normalize_online_query(clean_recipe_title(text))
    for token in [
        "家常", "招牌", "特色", "私房", "秘制", "经典", "独家", "家庭版", "简单版", "超简单", "超下饭", "下饭",
        "老爸的", "老妈的", "妈妈的", "爸爸的", "这样做", "做法", "教程", "合集", "精选集",
    ]:
        normalized = normalized.replace(normalize_online_query(token), "")
    return normalized


def longest_common_substring_length(left: str, right: str) -> int:
    if not left or not right:
        return 0
    table = [0] * (len(right) + 1)
    best = 0
    for left_char in left:
        previous = 0
        for idx, right_char in enumerate(right, 1):
            current = table[idx]
            if left_char == right_char:
                table[idx] = previous + 1
                best = max(best, table[idx])
            else:
                table[idx] = 0
            previous = current
    return best


def is_reliable_online_title_match(query: str, title: str) -> bool:
    normalized_query = normalize_online_query(query)
    normalized_title = normalize_online_query(title)
    if not normalized_query or not normalized_title:
        return False
    if normalized_query == normalized_title:
        return True
    if normalized_query in normalized_title or normalized_title in normalized_query:
        return True
    if not contains_chinese(query):
        return overlap_score(query, title) >= 2
    stripped_query = stripped_online_match_text(query)
    stripped_title = stripped_online_match_text(title)
    if not stripped_query or not stripped_title:
        return False
    shorter = min(len(stripped_query), len(stripped_title))
    longer = max(len(stripped_query), len(stripped_title))
    if shorter < 3:
        return False
    if stripped_query in stripped_title or stripped_title in stripped_query:
        return (shorter / longer) >= 0.75
    common_chars = len(set(stripped_query) & set(stripped_title))
    lcs = longest_common_substring_length(stripped_query, stripped_title)
    title_char_budget = max(len(set(stripped_title)), 1)
    return lcs >= max(2, len(stripped_query) - 1) and (common_chars / title_char_budget) >= 0.6


def normalize_ingredient_text(text: str) -> str:
    ingredient = clean_recipe_title(text)
    ingredient = re.sub(r"\([^)]*\)|（[^）]*）", "", ingredient)
    ingredient = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|kg|ml|l|克|千克|毫升|升|勺|汤匙|茶匙|个|只|片|段|把|适量)\b", "", ingredient, flags=re.IGNORECASE)
    ingredient = ingredient.strip(" ,，、/；;:+")
    return ingredient


def extract_anchor_texts(block: str) -> list[str]:
    return [
        clean_recipe_title(html.unescape(text))
        for text in re.findall(r">\s*([^<>]+?)\s*</a>", block, flags=re.IGNORECASE)
        if clean_recipe_title(html.unescape(text))
    ]


def build_online_recipe_candidate(
    *,
    query: str,
    title: str,
    ingredients: list[str],
    source: str,
    notes: str,
) -> tuple[str, dict[str, Any]] | None:
    title = clean_recipe_title(title)
    if not title or not is_reliable_online_title_match(query, title):
        return None
    cleaned_ingredients = stable_list([
        ingredient for ingredient in (normalize_ingredient_text(item) for item in ingredients)
        if ingredient and len(normalize_online_query(ingredient)) >= 1 and ingredient != title
    ])
    if not cleaned_ingredients:
        return None
    return title, {
        "aliases": [],
        "ingredients": cleaned_ingredients,
        "cooking_method": infer_method(title),
        "risk_tags": infer_risk_tags(title, cleaned_ingredients),
        "notes": notes,
        "source": source,
        "ambiguity_level": "medium",
    }


def rank_online_recipe_candidates(query: str, candidates: list[tuple[str, dict[str, Any]]]) -> tuple[str, dict[str, Any]] | None:
    if not candidates:
        return None
    source_priority = {
        "CookBook-KG online": 0,
        "xiachufang search": 1,
        "xiangha search": 2,
        "douguo search": 3,
        "Spoonacular search": 4,
    }
    ranked = sorted(
        candidates,
        key=lambda item: (
            -overlap_score(query, item[0]),
            source_priority.get(str(item[1].get("source") or ""), 99),
            len(item[0]),
        ),
    )
    return ranked[0]


def fetch_xiachufang_candidate(query: str) -> tuple[str, dict[str, Any]] | None:
    query = str(query or "").strip()
    if not query:
        return None
    params = urllib.parse.urlencode({"keyword": query, "cat": 1001, "via": "home"})
    url = f"{XIA_CHU_FANG_SEARCH_URL}?{params}"
    raw = online_recipe_request(url, headers={"Referer": "https://www.xiachufang.com/"})
    if not raw:
        return None
    blocks = re.findall(
        r'<div class="recipe recipe-215-horizontal pure-g image-link display-block">(.*?)</div>\s*</div>',
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates: list[tuple[str, dict[str, Any]]] = []
    for block in blocks[:8]:
        title_match = re.search(r'<p class="name">.*?<a [^>]*>\s*([^<>]+?)\s*</a>', block, flags=re.IGNORECASE | re.DOTALL)
        ingredients_match = re.search(r'<p class="ing ellipsis">(.*?)</p>', block, flags=re.IGNORECASE | re.DOTALL)
        candidate = build_online_recipe_candidate(
            query=query,
            title=title_match.group(1) if title_match else "",
            ingredients=extract_anchor_texts(ingredients_match.group(1)) if ingredients_match else [],
            source="xiachufang search",
            notes=f"联网从下厨房搜索页查询到的候选菜谱，仅作为参考。搜索入口：{url}",
        )
        if candidate:
            candidates.append(candidate)
    return rank_online_recipe_candidates(query, candidates)


def fetch_douguo_candidate(query: str) -> tuple[str, dict[str, Any]] | None:
    query = str(query or "").strip()
    if not query:
        return None
    url = f"{DOU_GUO_SEARCH_URL}{urllib.parse.quote(query)}"
    raw = online_recipe_request(url, headers={
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://m.douguo.com/",
    })
    if not raw:
        return None
    blocks = re.findall(
        r'<li class="menu-content">\s*<a href="([^"]*?/cookbook/\d+\.html[^\"]*)"[^>]*>.*?<h2 class="recipe-name text-clamp">(.*?)</h2>.*?<div class="recipe-cai text-lips">(.*?)</div>',
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not blocks:
        blocks = re.findall(
            r'<a class="cookname text-lips[^>]*?href="([^"]*?/cookbook/\d+\.html)"[^>]*>(.*?)</a>\s*<p class="major">(.*?)</p>',
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
    candidates: list[tuple[str, dict[str, Any]]] = []
    for _, title, ingredients_text in blocks[:10]:
        candidate = build_online_recipe_candidate(
            query=query,
            title=title,
            ingredients=re.split(r"[\s,，、]+", clean_recipe_title(ingredients_text)),
            source="douguo search",
            notes=f"联网从豆果搜索页查询到的候选菜谱，仅作为参考。搜索入口：{url}",
        )
        if candidate:
            candidates.append(candidate)
    return rank_online_recipe_candidates(query, candidates)


def fetch_xiangha_candidate(query: str) -> tuple[str, dict[str, Any]] | None:
    query = str(query or "").strip()
    if not query:
        return None
    params = urllib.parse.urlencode({"s": query})
    url = f"{XIANG_HA_SEARCH_URL}?{params}"
    raw = online_recipe_request(url, headers={"Referer": "https://www.xiangha.com/"})
    if not raw:
        return None
    blocks = re.findall(r"<li><a class=\"pic .*?</li>", raw, flags=re.IGNORECASE | re.DOTALL)
    candidates: list[tuple[str, dict[str, Any]]] = []
    for block in blocks[:10]:
        title_match = re.search(r'<p class="name kw"><a [^>]*title="([^"]+)"', block, flags=re.IGNORECASE)
        ingredients_match = re.search(r"<p class=\"info\">\s*用料：([^<]+)</p>", block, flags=re.IGNORECASE)
        candidate = build_online_recipe_candidate(
            query=query,
            title=title_match.group(1) if title_match else "",
            ingredients=re.split(r"\s*,\s*", clean_recipe_title(ingredients_match.group(1)) if ingredients_match else ""),
            source="xiangha search",
            notes=f"联网从香哈搜索页查询到的候选菜谱，仅作为参考。搜索入口：{url}",
        )
        if candidate:
            candidates.append(candidate)
    return rank_online_recipe_candidates(query, candidates)


def spoonacular_api_key() -> str:
    return get_secret("SPOONACULAR_API_KEY")


def spoonacular_credential_hint() -> str:
    return local_secret_hint("SPOONACULAR_API_KEY")


def fetch_spoonacular_candidate(query: str) -> tuple[str, dict[str, Any]] | None:
    api_key = spoonacular_api_key()
    query = str(query or "").strip()
    if not api_key or not query:
        return None

    params = {
        "query": query,
        "number": 3,
        "addRecipeInformation": "true",
        "fillIngredients": "true",
        "instructionsRequired": "false",
        "apiKey": api_key,
    }
    url = f"{SPOONACULAR_COMPLEX_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in raw.get("results", []):
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        score = overlap_score(query, title)
        if score < 2:
            continue
        ranked.append((score, item))
    if not ranked:
        return None

    ranked.sort(key=lambda pair: (-pair[0], len(str(pair[1].get("title") or ""))))
    best = ranked[0][1]
    title = str(best.get("title") or query).strip()
    ingredients = stable_list([
        str(ingredient.get("nameClean") or ingredient.get("name") or "").strip()
        for ingredient in best.get("extendedIngredients", [])
        if str(ingredient.get("nameClean") or ingredient.get("name") or "").strip()
    ])
    if not ingredients:
        return None
    risk_tags = infer_risk_tags(title, ingredients)
    notes = "联网从 Spoonacular complexSearch 查询到的候选菜谱，仅作为参考。"
    source_url = best.get("sourceUrl")
    if source_url:
        notes = f"{notes} 来源：{source_url}"
    return title, {
        "aliases": [],
        "ingredients": ingredients,
        "cooking_method": infer_method(title),
        "risk_tags": risk_tags,
        "notes": notes,
        "source": "Spoonacular search",
        "ambiguity_level": "medium",
    }


def fetch_online_recipe_candidate(query: str) -> tuple[str, dict[str, Any]] | None:
    for loader in (
        fetch_cookbook_kg_candidate,
        fetch_xiachufang_candidate,
        fetch_xiangha_candidate,
        fetch_douguo_candidate,
        fetch_spoonacular_candidate,
    ):
        candidate = loader(query)
        if candidate:
            return candidate
    return None


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


def inherent_risk_reason(risk_tags: list[str]) -> str | None:
    strong_hits = sorted(set(risk_tags) & INHERENT_CAUTION_RISK_TAGS)
    cluster_hits = sorted(set(risk_tags) & INHERENT_CAUTION_CLUSTER_TAGS)
    if strong_hits or len(cluster_hits) >= 3:
        hits = stable_list(strong_hits + cluster_hits)
        hit_text = "、".join(hits)
        return f"菜品本身命中{hit_text}等风险标签，即使没有明确禁忌也建议谨慎。"
    return None


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
        "feedback_bias": {},
    }
    if candidates:
        result["candidates"] = candidates
    if degraded_input:
        result["degraded_input"] = stable_list(degraded_input)
    if output_mode == "human_readable_cn":
        result["human_readable_cn"] = render_human_readable_cn(result)
    return result


def format_quantitative_display(value: Any) -> str:
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("text_cn")
                if not text and item.get("label_cn") and item.get("value") is not None:
                    unit = item.get("unit_cn") or item.get("unit") or ""
                    text = f"{item['label_cn']} {item['value']} {unit}".strip()
                if text:
                    parts.append(str(text))
            elif item:
                parts.append(str(item))
        return "；".join(parts)
    if isinstance(value, str):
        return value
    if value:
        return str(value)
    return ""


def render_human_readable_cn(result: dict[str, Any]) -> str:
    label = {
        "recommend": "推荐",
        "caution": "谨慎",
        "avoid": "不推荐",
        "need_confirm": "需要确认",
    }[result["recommendation"]]
    dish = result.get("normalized_dish") or "未确认"
    ingredients = "、".join(result.get("ingredients") or []) or "未确认"
    cooking_method = result.get("cooking_method") or "未确认"
    risk_tags = "、".join(result.get("risk_tags") or []) or "暂无明显风险标签"
    quantitative_display = format_quantitative_display(result.get("nutrition_quantitative_display"))
    if quantitative_display:
        nutrition_line = quantitative_display
    else:
        nutrition_line = "缺少标准份量或克重，暂不输出精确数值。"
    reasons: list[str] = []
    explanation = result.get("explanation", "")
    if "依据：" in explanation:
        reasons = [part for part in explanation.split("依据：", 1)[1].split("；") if part]
    reasons = reasons[:4] or ["当前证据不足，请补充信息后再判断。"]
    need_confirm = result.get("need_confirm") or ["暂无"]
    advice = {
        "recommend": "可以作为候选，但仍需结合实际做法和份量。",
        "caution": "建议少量食用，控制份量；高糖、高脂或高钠菜品可小份分享，并减少当天其他甜食、油脂或主食。",
        "avoid": "建议避开这道菜，改选不含相关过敏源或高风险食材的菜品。",
        "need_confirm": "请先确认会影响判断的食材、做法或图片识别结果，再决定是否食用。",
    }[result["recommendation"]]
    lines = [
        "客观信息：",
        f"- 识别菜品：{dish}",
        f"- 主要食材：{ingredients}",
        f"- 常见做法：{cooking_method}",
        f"- 风险标签：{risk_tags}",
        f"- 营养估算：{nutrition_line}",
        "",
        f"结论：{label}",
        "",
        "原因：",
    ]
    for idx, reason in enumerate(reasons, 1):
        lines.append(f"{idx}. {reason}")
    lines.extend([
        "",
        f"建议：{advice}",
        f"需要确认：{'；'.join(need_confirm)}",
        "提示：以上仅作饮食参考，不能替代医生或营养师建议。",
    ])
    return "\n".join(lines)


def load_feedback_store() -> dict[str, Any]:
    return load_json_file(
        SKILL_DIR / "data" / "feedback.json",
        {"input_events": [], "events": [], "profiles": {"dish": {}, "user_dish": {}}, "corrections": {}, "meta": {"last_feedback_at": ""}},
    )


def save_feedback_store(store: dict[str, Any]) -> None:
    path = SKILL_DIR / "data" / "feedback.json"
    try:
        normalized = {
            "input_events": list(store.get("input_events") or []),
            "events": list(store.get("events") or []),
            "profiles": dict(store.get("profiles") or {"dish": {}, "user_dish": {}}),
            "corrections": dict(store.get("corrections") or {}),
            "meta": dict(store.get("meta") or {}),
        }
        normalized["profiles"].setdefault("dish", {})
        normalized["profiles"].setdefault("user_dish", {})
        normalized["meta"].setdefault("last_feedback_at", "")
        path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def record_recommendation_input(payload: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    store = load_feedback_store()
    event = {
        "event_id": f"input-{int(time.time() * 1000)}",
        "timestamp": str(int(time.time())),
        "event_type": "recommendation_input",
        "input_payload": payload,
        "normalized_dish": result.get("normalized_dish") or "",
        "recommendation": result.get("recommendation") or "",
        "confidence": result.get("confidence", 0),
        "user_id": str(payload.get("user_id") or ""),
        "context_tags": list(payload.get("context_tags") or []),
    }
    store.setdefault("input_events", []).append(event)
    store.setdefault("meta", {})["last_input_at"] = event["timestamp"]
    save_feedback_store(store)
    return result


def is_low_value_image_term(term: str) -> bool:
    normalized = term.strip().strip("•·").strip()
    lowered = normalized.lower()
    if not normalized:
        return True
    if normalized in KNOWN_IMAGE_DISH_TERMS:
        return False
    if normalized in IMAGE_TEXT_STOPWORDS:
        return True
    if any(token in lowered for token in IMAGE_TEXT_SUBSTRINGS):
        return True
    if any(token in normalized for token in {"@", "◎"}):
        return True
    if re.fullmatch(r"[0-9A-Za-z@◎+\-_/(). ]+", normalized):
        return True
    if not re.search(r"[一-鿿]{2,}", normalized) and not re.search(r"[A-Za-z]{3,}", normalized):
        return True
    if len(normalized) <= 2 and normalized not in {"豆浆", "豆花", "小吃", "主食"}:
        return True
    if not any(hint in normalized for hint in IMAGE_DISH_HINTS) and len(normalized) <= 5 and not re.search(r"面|粉|汤|饭|粥|堡|饺|馄饨|饼|菜", normalized):
        return True
    return False


def attach_raw_image_result(result: dict[str, Any], provider_context: dict[str, Any]) -> dict[str, Any]:
    if provider_context.get("ocr_result") or provider_context.get("vision_result"):
        result["raw_image_result"] = {
            "ocr": provider_context["ocr_result"].to_dict() if provider_context.get("ocr_result") else {},
            "vision": provider_context["vision_result"].to_dict() if provider_context.get("vision_result") else {},
        }
    return result


def image_scene_from_context(provider_context: dict[str, Any]) -> dict[str, Any] | None:
    image_case = provider_context.get("image_case") or {}
    scene_type = str(image_case.get("scene_type") or "").strip()
    if scene_type != "multi_dish":
        return None
    hints = [str(item).strip() for item in image_case.get("visual_category_hints", []) or [] if str(item).strip()]
    return {
        "type": "multi_dish",
        "label_cn": "多菜同屏",
        "visual_category_hints": hints,
        "requires_manual_confirmation": True,
        "suggested_action": "请人工确认要分析的菜品，或将每个餐盘/小碗单独裁剪后再识别。",
    }


def build_multi_dish_scene_result(request: dict[str, Any], provider_context: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    hints = scene.get("visual_category_hints") or []
    hint_text = "、".join(hints[:5]) if hints else "多个餐盘或小碗"
    result = build_result(
        normalized_dish=None,
        recommendation="need_confirm",
        confidence=0.0,
        ingredients=request["ingredients"],
        cooking_method=request["cooking_method"],
        nutrition_tags=[],
        risk_tags=["多菜同屏"],
        nutrition_evidence={},
        explanation=f"结论：需要确认。依据：图片疑似多菜同屏，包含{hint_text}，当前不能可靠确定用户要分析哪一道菜；建议人工确认目标菜品，或逐盘裁剪后再识别。",
        need_confirm=["人工确认菜品区域", "逐盘裁剪识别", "主要食材"],
        candidates=[],
        degraded_input=["multi_dish_scene"],
        output_mode=request["output_mode"],
    )
    result["image_scene"] = scene
    return attach_raw_image_result(result, provider_context)


def build_provider_context(request: dict[str, Any]) -> dict[str, Any]:
    raw_image_path = request.get("image_path") or request.get("image_reference")
    image_path = raw_image_path
    if image_path and not Path(image_path).is_absolute():
        image_path = str(SKILL_DIR.parent / image_path)
    image_case = get_image_case_by_path(image_path or raw_image_path or "") if (image_path or raw_image_path) else None
    image_path = image_path if image_path and (Path(image_path).exists() or image_case) else ""
    summary = validate_all_cases()
    allow_ocr = bool(image_path)
    return {
        "image_path": image_path,
        "image_case": image_case,
        "ocr_result": recognize_image_text(image_path) if allow_ocr else None,
        "vision_result": detect_dish_candidates(image_path) if allow_ocr else None,
        "image_cases_total": summary.get("total", 0),
        "allow_ocr": allow_ocr,
    }


def is_human_confirmed_image_label(provider_context: dict[str, Any]) -> bool:
    ocr_result = provider_context.get("ocr_result")
    if not ocr_result:
        return False
    raw = ocr_result.raw_result or {}
    return raw.get("label_status") == "human_confirmed"


def quantized_profile_for_dish(dish_name: str) -> dict[str, Any] | None:
    query = str(dish_name or '').strip()
    if not query:
        return None
    canonical = QUANTIFIED_ALIASES.get(query, query)
    return QUANTIFIED_PROVIDER.find(canonical)


QUANTITATIVE_DISPLAY_FIELDS = [
    ("energy_kcal", "热量", "Energy", "kcal", "千卡"),
    ("protein_g", "蛋白质", "Protein", "g", "克"),
    ("fat_g", "脂肪", "Fat", "g", "克"),
    ("carbohydrate_g", "碳水化合物", "Carbohydrate", "g", "克"),
    ("sugars_g", "糖", "Sugars", "g", "克"),
    ("sodium_mg", "钠", "Sodium", "mg", "毫克"),
]


def format_quantitative_value(value: Any) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 1)


def quantitative_display(quantified: dict[str, Any]) -> list[dict[str, Any]]:
    display: list[dict[str, Any]] = []
    for key, label_cn, label_en, unit, unit_cn in QUANTITATIVE_DISPLAY_FIELDS:
        raw_value = quantified.get(key)
        if raw_value is None:
            continue
        value = format_quantitative_value(raw_value)
        display.append({
            "key": key,
            "label_cn": label_cn,
            "label_en": label_en,
            "value": value,
            "unit": unit,
            "unit_cn": unit_cn,
            "text_cn": f"{label_cn} {value} {unit_cn}",
            "text_en": f"{label_en} {value} {unit}",
        })
    return display


def corrected_raw_name(raw_name: str) -> str:
    store = load_feedback_store()
    return (store.get("corrections") or {}).get(raw_name, raw_name)


def image_candidate_terms(request: dict[str, Any], provider_context: dict[str, Any]) -> list[str]:
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
        normalized = term.strip().strip("•·").strip()
        if is_low_value_image_term(normalized):
            continue
        if normalized not in filtered:
            filtered.append(normalized)
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


def sync_explanation_conclusion(explanation: str, recommendation: str) -> str:
    label = {
        "recommend": "推荐",
        "caution": "谨慎",
        "avoid": "不推荐",
        "need_confirm": "需要确认",
    }.get(recommendation, "需要确认")
    if explanation.startswith("结论："):
        return re.sub(r"^结论：[^。]+。依据：", f"结论：{label}。依据：", explanation, count=1)
    return explanation


def apply_feedback_bias(result: dict[str, Any], normalized_dish: str | None, user_id: str = "", context_tags: list[str] | None = None) -> dict[str, Any]:
    if not normalized_dish:
        return result
    store = load_feedback_store()
    context_tags = context_tags or []
    dish_profile = ((store.get("profiles") or {}).get("dish") or {}).get(normalized_dish, {})
    user_key = f"{user_id}::{normalized_dish}" if user_id else ""
    user_profile = ((store.get("profiles") or {}).get("user_dish") or {}).get(user_key, {}) if user_key else {}
    active_profile = user_profile or dish_profile
    if not active_profile:
        return result
    result["feedback_bias"] = {normalized_dish: active_profile}
    accepts = int(active_profile.get("accepts", 0) or 0)
    rejects = int(active_profile.get("rejects", 0) or 0)
    favorites = int(active_profile.get("favorites", 0) or 0)
    confidence_delta = 0.03 * accepts + 0.05 * favorites - 0.04 * rejects
    if user_profile:
        confidence_delta += 0.02
    result["confidence"] = round(min(1.0, max(0.0, float(result.get("confidence", 0)) + confidence_delta)), 2)
    explanation = result.get("explanation", "")
    notes: list[str] = []
    if accepts > 0:
        notes.append(f"历史接受 {accepts} 次")
    if favorites > 0:
        notes.append(f"历史收藏 {favorites} 次")
    if rejects > 0:
        notes.append(f"历史拒绝 {rejects} 次")
    profile_label = "个人反馈" if user_profile else "近期反馈"
    merged_tags = []
    for tag in list(active_profile.get("context_tags") or []) + list(context_tags or []):
        if tag and tag not in merged_tags:
            merged_tags.append(tag)
    if merged_tags:
        notes.append(f"相关场景：{'、'.join(merged_tags[:3])}")
    if rejects > 0:
        if result.get("recommendation") == "recommend":
            result["recommendation"] = "caution"
        elif result.get("recommendation") == "caution" and rejects >= accepts + favorites:
            result["recommendation"] = "avoid"
        if not result.get("need_confirm"):
            result["need_confirm"] = []
        if "近期反馈偏好" not in result["need_confirm"]:
            result["need_confirm"].append("近期反馈偏好")
    explanation = sync_explanation_conclusion(explanation, result.get("recommendation", "need_confirm"))
    if notes:
        addition = f"；{profile_label}：{'，'.join(notes)}。"
        if explanation and not explanation.endswith('。'):
            explanation += '。'
        result["explanation"] = (explanation or "结论：需要确认。依据：") + addition if explanation else f"结论：需要确认。依据：{profile_label}：{'，'.join(notes)}。"
    return result


def is_menu_candidate_term(term: str) -> bool:
    normalized = term.strip().strip("•·：:，,。").strip()
    if not normalized:
        return False
    if normalized in MENU_LINE_STOPWORDS:
        return False
    if any(token in normalized for token in MENU_LINE_STOPWORDS):
        return False
    if re.fullmatch(r"[0-9A-Za-z•·()~＋+/ ]+", normalized):
        return False
    if len(normalized) < 2:
        return False
    return any(hint in normalized for hint in IMAGE_DISH_HINTS)


def is_menu_stall_line(term: str) -> bool:
    normalized = term.strip().strip("：:，,。").strip()
    if not normalized:
        return False
    if "菜单" in normalized or normalized in IMAGE_TEXT_STOPWORDS:
        return False
    return bool(re.match(r"^\d+F", normalized))


def infer_menu_text(provider_context: dict[str, Any]) -> str:
    ocr_result = provider_context.get("ocr_result")
    if not ocr_result:
        return ""
    menu_terms: list[str] = []
    for line in ocr_result.lines or []:
        normalized = line.strip()
        if normalized.startswith("•"):
            continue
        if is_menu_stall_line(normalized):
            continue
        if not is_menu_candidate_term(normalized):
            continue
        if normalized not in menu_terms:
            menu_terms.append(normalized)
    return "\n".join(menu_terms)


def expand_menu_candidate_terms(menu_terms: list[str]) -> list[str]:
    expanded: list[str] = []
    for term in menu_terms:
        parts = [segment.strip().lstrip("•").strip() for segment in re.split(r"[、，,/＋+]", term) if segment.strip()]
        for part in parts or [term]:
            if not is_menu_candidate_term(part):
                continue
            if part not in expanded:
                expanded.append(part)
    return expanded


def infer_menu_candidate_records(provider_context: dict[str, Any]) -> list[dict[str, str]]:
    ocr_result = provider_context.get("ocr_result")
    if not ocr_result:
        return []
    records: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    current_stall = ""
    for line in ocr_result.lines or []:
        normalized = line.strip()
        if not normalized or normalized.startswith("•"):
            continue
        if is_menu_stall_line(normalized):
            current_stall = normalized
            continue
        if not is_menu_candidate_term(normalized):
            continue
        for dish_name in expand_menu_candidate_terms([normalized]):
            key = (dish_name, current_stall)
            if key in seen:
                continue
            seen.add(key)
            records.append({"dish_name": dish_name, "stall_name": current_stall})
    return records


def find_menu_source(dish_name: str | None, records: list[dict[str, str]]) -> dict[str, str] | None:
    query = str(dish_name or "").strip()
    if not query:
        return None
    normalized_query, _, _ = normalize_dish(query)
    for record in records:
        if record["dish_name"] == query:
            return record
    for record in records:
        normalized_record, _, _ = normalize_dish(record["dish_name"])
        if normalized_record and normalized_record == normalized_query:
            return record
    return None


def attach_menu_source(result: dict[str, Any], dish_name: str | None, records: list[dict[str, str]]) -> dict[str, Any]:
    source = find_menu_source(dish_name or result.get("normalized_dish"), records)
    if not source or not source.get("stall_name"):
        return result
    result["stall_name"] = source["stall_name"]
    result["menu_source"] = {"dish_name": source["dish_name"], "stall_name": source["stall_name"]}
    if source["stall_name"] not in result.get("explanation", ""):
        explanation = result.get("explanation", "")
        if explanation and not explanation.endswith("。"):
            explanation += "。"
        result["explanation"] = f"{explanation}；档口：{source['stall_name']}。" if explanation else f"档口：{source['stall_name']}。"
    return result


def score_menu_candidate(name: str, profile: dict[str, Any]) -> int:
    score = 0
    normalized, confidence, _ = normalize_dish(name)
    if normalized in DISHES and confidence >= 0.8:
        score += 4
    if any(token in name for token in ["清炒", "白灼", "水煮", "清蒸", "西兰花", "青菜", "白菜", "冬瓜", "山药", "木耳", "南瓜", "菌菇", "虾"]):
        score += 3
    if any(token in name for token in ["包菜", "油菜", "莴笋"]):
        score += 2
    if any(token in name for token in ["麻辣", "红烧", "烤鸭", "猪脚", "肥牛", "鸡公煲", "烤鱼", "双拼", "寿喜锅", "卤肉", "排骨", "炸"]):
        score -= 3
    if any(token in name for token in ["饭", "面", "粿条", "米线", "粉", "饺", "包"]):
        score -= 1
    if "减脂" in profile.get("goals", []) and any(token in name for token in ["大虾", "鸡扒", "鸡腿", "鸡丝", "青菜", "西兰花", "南瓜", "冬瓜", "木耳"]):
        score += 2
    if "减脂" in profile.get("goals", []) and any(token in name for token in ["猪", "肥牛", "卤肉", "烤鸭", "排骨", "烤肉"]):
        score -= 2
    return score


def choose_menu_candidate(menu_terms: list[str], profile: dict[str, Any]) -> str | None:
    ranked = []
    for term in expand_menu_candidate_terms(menu_terms):
        ranked.append((score_menu_candidate(term, profile), term))
    ranked.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    if not ranked or ranked[0][0] <= 0:
        return None
    fallback_term = ranked[0][1]
    for _, term in ranked[:5]:
        normalized, confidence, _ = normalize_dish(term)
        if normalized in DISHES and confidence >= 0.8:
            return term
        online_candidate = fetch_online_recipe_candidate(term)
        if online_candidate:
            return online_candidate[0]
    return fallback_term


def infer_ingredients_from_name(name: str) -> list[str]:
    matched: list[str] = []
    ingredient_db = NUTRITION.get("ingredients", {})
    for ingredient in sorted(ingredient_db.keys(), key=len, reverse=True):
        token = str(ingredient).strip()
        if token and token in name and token not in matched:
            matched.append(token)
    return matched


def recommend(payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_request(payload)
    explicit_dish_name = bool(request.get("dish_name"))
    provider_context = build_provider_context(request)
    image_scene = image_scene_from_context(provider_context)
    if image_scene and request.get("image_path") and not explicit_dish_name:
        result = build_multi_dish_scene_result(request, provider_context, image_scene)
        return record_recommendation_input(payload, result)
    if not request.get("ocr_text") and provider_context.get("ocr_result") and provider_context["ocr_result"].text:
        useful_lines = [
            line.strip() for line in (provider_context["ocr_result"].lines or [])
            if line.strip() and not is_low_value_image_term(line.strip())
        ]
        if len(useful_lines) == 1 and len(useful_lines[0]) <= 20:
            request["ocr_text"] = useful_lines[0]
    inferred_menu_terms: list[str] = []
    menu_candidate_records: list[dict[str, str]] = []
    if request.get("image_path") and not explicit_dish_name:
        menu_candidate_records = infer_menu_candidate_records(provider_context)
        inferred_menu_terms = [record["dish_name"] for record in menu_candidate_records]
        inferred_menu_text = "\n".join(inferred_menu_terms) if inferred_menu_terms else infer_menu_text(provider_context)
        if inferred_menu_text:
            if not inferred_menu_terms:
                inferred_menu_terms = inferred_menu_text.splitlines()
            menu_choice = choose_menu_candidate(inferred_menu_terms, request["user_profile"])
            if menu_choice:
                request["dish_name"] = menu_choice
            elif not request.get("menu_text"):
                request["menu_text"] = inferred_menu_text
    raw_name = corrected_raw_name(request.get("dish_name") if explicit_dish_name else pick_raw_name(request))
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
            risk_tags=["缺少文本识别结果"],
            nutrition_evidence={},
            explanation="结论：需要确认。依据：当前输入只有图片引用，未直接接入视觉/OCR识别或未获得足够稳定的文本结果，请补充菜名、OCR 文本或主要食材。",
            need_confirm=["菜名", "OCR文本", "主要食材"],
            candidates=image_seed_candidates,
            degraded_input=degraded_input,
            output_mode=request["output_mode"],
        )
        result = attach_raw_image_result(result, provider_context)
        return record_recommendation_input(payload, result)

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
        result = attach_raw_image_result(result, provider_context)
        return record_recommendation_input(payload, result)

    info = DISHES.get(normalized) if normalized else None
    if not info and normalized and not request["ingredients"]:
        online_candidate = fetch_online_recipe_candidate(normalized)
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

    if not info and normalized and request.get("image_path"):
        inferred_ingredients = infer_ingredients_from_name(normalized)
        if inferred_ingredients:
            info = {
                "aliases": [],
                "ingredients": inferred_ingredients,
                "cooking_method": infer_method(normalized or ""),
                "risk_tags": infer_risk_tags(normalized or "自定义菜品", inferred_ingredients),
                "notes": "图片菜单项命中后，系统基于菜名关键词推断食材做参考判断。",
                "source": "image_menu_inferred",
                "ambiguity_level": "medium",
            }
            confidence = max(confidence, 0.52)

    if not info:
        result = build_result(
            normalized_dish=None if request.get("image_path") else normalized,
            recommendation="need_confirm",
            confidence=confidence if not request.get("image_path") else 0.0,
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
        result = attach_raw_image_result(result, provider_context)
        return record_recommendation_input(payload, result)

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
        reasons.append("菜品可能含添加糖、甜味调料、勾芡或精制碳水，控糖人群需关注总量和份量。")

    if contains_any(terms, ["减脂", "低脂"]) and contains_any(ingredients + risk_tags, RISK_KEYWORDS["减脂"]):
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append("菜品可能脂肪、用油或热量较高，减脂或低脂用户建议少量食用。")

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

    if request.get("image_path") and not explicit_dish_name and is_human_confirmed_image_label(provider_context):
        degraded_input.append("human_confirmed_image_label")
        reasons.append("当前菜名来自人工确认图片标签，优先级高于低置信度外部识图候选。")

    if request["ocr_text"] and not request["dish_name"]:
        if is_human_confirmed_image_label(provider_context):
            reasons.append("当前菜名来自人工确认图片标签，优先级高于低置信度外部识图候选。")
        else:
            degraded_input.append("ocr_text_inferred")
            reasons.append("当前菜名基于 OCR 文本推断，若菜单排版复杂请人工确认标准菜名。")

    inherent_reason = inherent_risk_reason(risk_tags)
    if recommendation == "recommend" and inherent_reason:
        recommendation = choose_recommendation(recommendation, "caution")
        reasons.append(inherent_reason)

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
    result = attach_menu_source(result, raw_name, menu_candidate_records)
    result = attach_raw_image_result(result, provider_context)
    quantified = quantized_profile_for_dish(result.get("normalized_dish") or "")
    if quantified:
        result["nutrition_quantitative"] = {k: quantified.get(k) for k in ["energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "sugars_g", "sodium_mg"] if quantified.get(k) is not None}
        result["nutrition_quantitative_display"] = quantitative_display(quantified)
        result["nutrition_basis"] = quantified.get("nutrition_basis")
        result["portion_basis"] = quantified.get("portion_basis")
        for optional_key in ["standard_ingredients", "energy_calculation", "source_refs", "confidence_note"]:
            if quantified.get(optional_key):
                result[optional_key] = quantified.get(optional_key)
    result = apply_feedback_bias(
        result,
        result.get("normalized_dish"),
        user_id=request.get("user_id", ""),
        context_tags=request.get("context_tags", []),
    )
    if request["output_mode"] == "human_readable_cn":
        result["human_readable_cn"] = render_human_readable_cn(result)
    return record_recommendation_input(payload, result)


def main() -> None:
    payload = load_input()
    print(json.dumps(recommend(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
