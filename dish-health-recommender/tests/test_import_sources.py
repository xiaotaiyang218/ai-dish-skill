import importlib.util
import json
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPT_PATH = SKILL_DIR / 'scripts' / 'import_sources.py'
MANIFEST_PATH = SKILL_DIR / 'data' / 'source_manifest.json'
DATA_SOURCES_PATH = SKILL_DIR / 'references' / 'data-sources.md'


def load_module():
    spec = importlib.util.spec_from_file_location('import_sources', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class ImportSourcesTests(unittest.TestCase):
    def test_manifest_has_required_metadata_fields(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding='utf-8'))
        self.assertIn('sources', manifest)
        self.assertGreaterEqual(len(manifest['sources']), 1)
        for source in manifest['sources']:
            self.assertIn('source_type', source)
            self.assertIn('import_mode', source)
            self.assertIn('license_status', source)
            self.assertIn('target_files', source)
            self.assertIn('enabled_for_runtime', source)
            self.assertIn('records_imported', source)
            self.assertIn('last_import_report', source)

    def test_import_script_returns_contract_fields(self):
        result = MODULE.import_source({
            'sourceName': 'CookBook-KG',
            'sourceType': 'recipe',
            'importMode': 'offline_snapshot',
            'sourceLocation': 'https://raw.githubusercontent.com/ngl567/CookBook-KG/master/visualization/vizdata.json',
            'targetFiles': ['dish-health-recommender/data/dishes.json'],
            'enableForRuntime': True,
        })
        self.assertEqual('CookBook-KG', result['sourceName'])
        self.assertIn('recordsImported', result)
        self.assertIn('manifestPath', result)
        self.assertIn('updatedFiles', result)

    def test_data_sources_doc_keeps_offline_import_boundary(self):
        content = DATA_SOURCES_PATH.read_text(encoding='utf-8')
        self.assertIn('offline', content.lower())
        self.assertIn('本地', content)
        self.assertTrue('可选增强' in content or 'optional' in content.lower())


if __name__ == '__main__':
    unittest.main()
