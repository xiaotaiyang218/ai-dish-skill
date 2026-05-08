#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
FEEDBACK_PATH = SKILL_DIR / 'data' / 'feedback.json'


def load_store() -> dict:
    if not FEEDBACK_PATH.exists():
        return {'events': [], 'bias': {}, 'corrections': {}}
    data = json.loads(FEEDBACK_PATH.read_text(encoding='utf-8'))
    data.setdefault('events', [])
    data.setdefault('bias', {})
    data.setdefault('corrections', {})
    return data


def save_store(store: dict) -> None:
    FEEDBACK_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record_feedback(payload: dict) -> dict:
    store = load_store()
    event = {
        'event_id': payload.get('event_id') or f"fb-{int(time.time() * 1000)}",
        'timestamp': payload.get('timestamp') or str(int(time.time())),
        'input_payload': payload.get('input_payload', {}),
        'normalized_dish': payload.get('normalized_dish', ''),
        'recommendation': payload.get('recommendation', ''),
        'feedback_type': payload.get('feedback_type', ''),
        'corrected_dish_name': payload.get('corrected_dish_name', ''),
        'notes': payload.get('notes', ''),
    }
    store['events'].append(event)
    dish = event['normalized_dish'] or event['input_payload'].get('dish_name', '')
    if dish:
        bias = store['bias'].setdefault(dish, {'accepts': 0, 'rejects': 0, 'favorites': 0})
        if event['feedback_type'] == 'accept':
            bias['accepts'] += 1
        elif event['feedback_type'] == 'reject':
            bias['rejects'] += 1
        elif event['feedback_type'] == 'favorite':
            bias['favorites'] += 1
    if event['feedback_type'] == 'correct_dish_name' and event['corrected_dish_name']:
        raw = event['input_payload'].get('dish_name', '')
        if raw:
            store['corrections'][raw] = event['corrected_dish_name']
    save_store(store)
    return event


def summarize_bias() -> dict:
    store = load_store()
    return {'bias': store.get('bias', {}), 'corrections': store.get('corrections', {})}


def main() -> None:
    payload = json.load(sys.stdin) if len(sys.argv) == 1 else json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    if payload.get('action') == 'summary':
        print(json.dumps(summarize_bias(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(record_feedback(payload), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
