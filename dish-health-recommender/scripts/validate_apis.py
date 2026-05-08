#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))

from providers.nutrition_provider import validate_all_providers  # noqa: E402

OUTPUT_JSON = SKILL_DIR.parents[2] / 'specs' / '20260508-dish-multi-verify' / 'validation' / 'api-validation-report.json'
OUTPUT_MD = SKILL_DIR.parents[2] / 'specs' / '20260508-dish-multi-verify' / 'validation' / 'api-validation.md'


def main() -> None:
    records = validate_all_providers()
    report = {'records': records}
    OUTPUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [
        '# API Validation Matrix',
        '',
        '| Provider | Type | Status | Credential Requirement | Notes |',
        '| --- | --- | --- | --- | --- |',
    ]
    for item in records:
        cred = item.get('credential_hint') or 'none'
        notes = item.get('error_message') or item.get('degrade_strategy') or ''
        lines.append(f"| {item['provider_name']} | {item['provider_type']} | {item['status']} | {cred} | {notes} |")
    OUTPUT_MD.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
