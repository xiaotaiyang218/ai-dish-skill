#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = SKILL_DIR / 'data' / 'source_manifest.json'
VALIDATION_DIR = SKILL_DIR / 'validation'
IMPORT_REPORT_PATH = VALIDATION_DIR / 'source-import-report.json'
REPO_ROOT = SKILL_DIR.parent


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {'sources': []}
    return json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def count_records(target_files: list[str]) -> int:
    records = 0
    for rel_path in target_files:
        path = REPO_ROOT / rel_path
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            if 'recipes' in data and isinstance(data['recipes'], list):
                records += len(data['recipes'])
            else:
                records += len(data)
        elif isinstance(data, list):
            records += len(data)
    return records


def import_source(payload: dict) -> dict:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    source_name = payload['sourceName']
    target_files = list(payload.get('targetFiles') or [])
    records_imported = count_records(target_files)
    report = {
        'sourceName': source_name,
        'sourceType': payload['sourceType'],
        'importMode': payload['importMode'],
        'sourceLocation': payload.get('sourceLocation', ''),
        'recordsImported': records_imported,
        'updatedFiles': target_files,
        'manifestPath': str(MANIFEST_PATH),
    }
    IMPORT_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sources = manifest.setdefault('sources', [])
    updated = False
    for source in sources:
        if source.get('name') != source_name:
            continue
        source['source_type'] = payload['sourceType']
        source['import_mode'] = payload['importMode']
        source['url_or_origin'] = payload.get('sourceLocation', source.get('url_or_origin', ''))
        source['target_files'] = target_files
        source['enabled_for_runtime'] = bool(payload.get('enableForRuntime', False))
        source['records_imported'] = records_imported
        source['last_import_report'] = str(IMPORT_REPORT_PATH)
        updated = True
        break
    if not updated:
        sources.append({
            'name': source_name,
            'source_type': payload['sourceType'],
            'url_or_origin': payload.get('sourceLocation', ''),
            'license_status': 'pending_review',
            'import_mode': payload['importMode'],
            'target_files': target_files,
            'enabled_for_runtime': bool(payload.get('enableForRuntime', False)),
            'records_imported': records_imported,
            'last_import_report': str(IMPORT_REPORT_PATH),
        })
    save_manifest(manifest)
    return report


def main() -> None:
    payload = json.load(sys.stdin) if len(sys.argv) == 1 else json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    print(json.dumps(import_source(payload), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
