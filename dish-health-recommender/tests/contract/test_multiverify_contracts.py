import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = ROOT / 'dish-health-recommender'


class MultiVerifyContractTests(unittest.TestCase):
    def test_multiverify_assets_exist(self):
        for path in [
            SKILL_DIR / 'tests' / 'test_multimodal.py',
            SKILL_DIR / 'tests' / 'test_feedback.py',
            SKILL_DIR / 'tests' / 'test_quantization.py',
            SKILL_DIR / 'scripts' / 'report_alignment.py',
        ]:
            self.assertTrue(path.exists())

    def test_expected_entity_names_exist_in_local_sources(self):
        joined = '\n'.join([
            (SKILL_DIR / 'scripts' / 'recommend.py').read_text(encoding='utf-8'),
            (SKILL_DIR / 'providers' / 'nutrition_provider.py').read_text(encoding='utf-8'),
            (SKILL_DIR / 'data' / 'image_test_cases.json').read_text(encoding='utf-8'),
        ])
        for schema in ['ApiValidationRecord', 'nutrition_quantitative', 'image_id']:
            self.assertIn(schema, joined)


if __name__ == '__main__':
    unittest.main()
