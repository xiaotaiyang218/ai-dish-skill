#!/usr/bin/env python3
"""Fetch a compact local recipe library from CookBook-KG.

Source: https://github.com/ngl567/CookBook-KG
The script downloads the mini visualization graph and converts recipe ingredient
edges into the local dishes.json shape consumed by recommend.py.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_URL = (
    "https://raw.githubusercontent.com/ngl567/CookBook-KG/master/"
    "visualization/vizdata.json"
)
SKILL_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = SKILL_DIR / "data"
DISHES_PATH = DATA_DIR / "dishes.json"
MANIFEST_PATH = DATA_DIR / "source_manifest.json"


COOKING_METHOD_HINTS = {
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
}


def strip_index(name: str) -> str:
    return re.sub(r"^\s*\d+[.、]\s*", "", name).strip()


def risk_tags(name: str, ingredients: list[str]) -> list[str]:
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
    if any(word in text for word in ["油炸", "炸"]):
        tags.append("油炸")
    return sorted(set(tags))


def infer_method(name: str) -> str | None:
    for hint, method in COOKING_METHOD_HINTS.items():
        if hint in name:
            return method
    return None


def fetch_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def build_dishes(raw: dict[str, Any], limit: int) -> dict[str, Any]:
    ingredients_by_dish: dict[str, list[str]] = defaultdict(list)
    for link in raw.get("links", []):
        if link.get("relation") != "选材":
            continue
        source = strip_index(str(link.get("source", "")))
        target = strip_index(str(link.get("target", "")))
        if not source or not target:
            continue
        if target not in ingredients_by_dish[source]:
            ingredients_by_dish[source].append(target)

    dishes: dict[str, Any] = {}
    for name in sorted(ingredients_by_dish)[:limit]:
        ingredients = ingredients_by_dish[name]
        dishes[name] = {
            "aliases": [],
            "ingredients": ingredients,
            "cooking_method": infer_method(name),
            "risk_tags": risk_tags(name, ingredients),
            "notes": "来自 CookBook-KG mini 图谱的菜谱选材关系，适合作为候选菜谱和风险标签参考。",
            "source": "CookBook-KG",
        }
    return dishes


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw = fetch_json(SOURCE_URL)
    dishes = build_dishes(raw, limit=120)
    DISHES_PATH.write_text(json.dumps(dishes, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "CookBook-KG",
                        "url": SOURCE_URL,
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "records": len(dishes),
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(dishes)} dishes to {DISHES_PATH}")


if __name__ == "__main__":
    main()
