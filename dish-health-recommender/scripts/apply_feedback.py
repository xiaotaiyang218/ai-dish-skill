#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
FEEDBACK_PATH = SKILL_DIR / 'data' / 'feedback.json'
VALIDATION_DIR = SKILL_DIR / 'validation'
REPLAY_OUTPUT_PATH = VALIDATION_DIR / 'feedback-replay-report.json'


def empty_store() -> dict:
    return {
        'input_events': [],
        'events': [],
        'profiles': {'dish': {}, 'user_dish': {}},
        'corrections': {},
        'meta': {'last_feedback_at': ''},
    }


def empty_profile() -> dict:
    return {
        'accepts': 0,
        'rejects': 0,
        'favorites': 0,
        'last_feedback_at': '',
        'context_tags': [],
        'user_id': '',
        'dish_name': '',
    }


def normalize_store(data: dict | None) -> dict:
    store = empty_store()
    if isinstance(data, dict):
        store.update({k: v for k, v in data.items() if k in store or k == 'bias'})
    store['input_events'] = list(store.get('input_events') or [])
    store['events'] = list(store.get('events') or [])
    store['corrections'] = dict(store.get('corrections') or {})
    store['meta'] = dict(store.get('meta') or {})
    store['meta'].setdefault('last_feedback_at', '')
    profiles = dict(store.get('profiles') or {})
    if store.get('bias') and not profiles.get('dish'):
        profiles['dish'] = dict(store.get('bias') or {})
    profiles.setdefault('dish', {})
    profiles.setdefault('user_dish', {})
    for mode in ('dish', 'user_dish'):
        normalized_profiles = {}
        for key, value in dict(profiles.get(mode) or {}).items():
            profile = empty_profile()
            if isinstance(value, dict):
                profile.update(value)
            normalized_profiles[key] = profile
        profiles[mode] = normalized_profiles
    store['profiles'] = profiles
    store.pop('bias', None)
    return store


def load_store(path: Path | None = None) -> dict:
    target_path = path or FEEDBACK_PATH
    if not target_path.exists():
        return empty_store()
    try:
        data = json.loads(target_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return empty_store()
    return normalize_store(data)


def save_store(store: dict, path: Path | None = None) -> None:
    target_path = path or FEEDBACK_PATH
    target_path.write_text(json.dumps(normalize_store(store), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def dedupe_preserve_order(values: list[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        item = str(value).strip()
        if item and item not in unique:
            unique.append(item)
    return unique


def profile_key(profile_mode: str, event: dict) -> str:
    dish_name = str(event.get('normalized_dish') or event.get('input_payload', {}).get('dish_name') or '').strip()
    user_id = str(event.get('user_id') or '').strip()
    if profile_mode == 'user_dish':
        return f'{user_id}::{dish_name}' if user_id and dish_name else ''
    return dish_name


def profile_matches_window(event: dict, decay_window_days: int) -> bool:
    if decay_window_days <= 0:
        return True
    timestamp = str(event.get('timestamp') or '').strip()
    if not timestamp.isdigit():
        return True
    now = int(time.time())
    return int(timestamp) >= now - decay_window_days * 24 * 3600


def rebuild_profiles(events: list[dict], profile_mode: str, decay_window_days: int) -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    for event in events:
        if not profile_matches_window(event, decay_window_days):
            continue
        key = profile_key(profile_mode, event)
        if not key:
            continue
        profile = profiles.setdefault(key, empty_profile())
        dish_name = str(event.get('normalized_dish') or event.get('input_payload', {}).get('dish_name') or '').strip()
        user_id = str(event.get('user_id') or '').strip()
        profile['dish_name'] = dish_name
        profile['user_id'] = user_id
        profile['last_feedback_at'] = str(event.get('timestamp') or profile.get('last_feedback_at') or '')
        profile['context_tags'] = dedupe_preserve_order(profile.get('context_tags', []) + list(event.get('context_tags') or []))
        feedback_type = event.get('feedback_type')
        if feedback_type == 'accept':
            profile['accepts'] += 1
        elif feedback_type == 'reject':
            profile['rejects'] += 1
        elif feedback_type == 'favorite':
            profile['favorites'] += 1
    return profiles


def refresh_profiles(store: dict, decay_window_days: int = 30) -> dict:
    normalized = normalize_store(store)
    events = normalized.get('events', [])
    normalized['profiles']['dish'] = rebuild_profiles(events, 'dish', decay_window_days)
    normalized['profiles']['user_dish'] = rebuild_profiles(events, 'user_dish', decay_window_days)
    dish_bias = {}
    for dish_name, profile in normalized['profiles']['dish'].items():
        dish_bias[dish_name] = {
            'accepts': profile.get('accepts', 0),
            'rejects': profile.get('rejects', 0),
            'favorites': profile.get('favorites', 0),
        }
    normalized['bias'] = dish_bias
    latest = ''
    for event in events:
        timestamp = str(event.get('timestamp') or '').strip()
        if timestamp and timestamp > latest:
            latest = timestamp
    normalized['meta']['last_feedback_at'] = latest
    return normalized


def record_feedback(payload: dict) -> dict:
    store = load_store()
    event = {
        'event_id': payload.get('event_id') or f"fb-{int(time.time() * 1000)}",
        'timestamp': str(payload.get('timestamp') or int(time.time())),
        'input_payload': payload.get('input_payload', {}),
        'normalized_dish': payload.get('normalized_dish', ''),
        'recommendation': payload.get('recommendation', ''),
        'feedback_type': payload.get('feedback_type', ''),
        'corrected_dish_name': payload.get('corrected_dish_name', ''),
        'notes': payload.get('notes', ''),
        'user_id': str(payload.get('user_id') or ''),
        'context_tags': dedupe_preserve_order(list(payload.get('context_tags') or [])),
    }
    store['events'].append(event)
    if event['feedback_type'] == 'correct_dish_name' and event['corrected_dish_name']:
        raw = event['input_payload'].get('dish_name', '')
        if raw:
            store['corrections'][raw] = event['corrected_dish_name']
    store = refresh_profiles(store)
    save_store(store)
    return event


def summarize_bias() -> dict:
    store = refresh_profiles(load_store())
    save_store(store)
    return {
        'bias': store.get('bias', {}),
        'profiles': store.get('profiles', {}),
        'corrections': store.get('corrections', {}),
        'last_feedback_at': store.get('meta', {}).get('last_feedback_at', ''),
    }


def replay_feedback_profiles(payload: dict) -> dict:
    store_path = Path(payload.get('storePath') or FEEDBACK_PATH)
    profile_mode = str(payload.get('profileMode') or 'dish')
    decay_window_days = int(payload.get('decayWindowDays') or 30)
    store = load_store(store_path)
    profiles = rebuild_profiles(store.get('events', []), profile_mode, decay_window_days)
    store['profiles'][profile_mode] = profiles
    if store_path == FEEDBACK_PATH:
        store = refresh_profiles(store, decay_window_days=decay_window_days)
        save_store(store, store_path)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        'profileMode': profile_mode,
        'decayWindowDays': decay_window_days,
        'profileCount': len(profiles),
        'outputPath': str(REPLAY_OUTPUT_PATH),
        'profiles': profiles,
    }
    REPLAY_OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'profileCount': len(profiles),
        'outputPath': str(REPLAY_OUTPUT_PATH),
        'profileMode': profile_mode,
        'decayWindowDays': decay_window_days,
    }


def main() -> None:
    payload = json.load(sys.stdin) if len(sys.argv) == 1 else json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    action = payload.get('action')
    if action == 'summary':
        print(json.dumps(summarize_bias(), ensure_ascii=False, indent=2))
    elif action == 'replay':
        print(json.dumps(replay_feedback_profiles(payload), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(record_feedback(payload), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
