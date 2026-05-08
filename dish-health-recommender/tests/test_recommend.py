import importlib.util
import json
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPT_PATH = SKILL_DIR / 'scripts' / 'recommend.py'
FIXTURES_DIR = TESTS_DIR / 'fixtures'
EXPECTED_DIR = TESTS_DIR / 'expected'
FEEDBACK_STORE = SKILL_DIR / 'data' / 'feedback.json'


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_recommend_module():
    spec = importlib.util.spec_from_file_location('dish_recommend', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MODULE = load_recommend_module()


def run_recommend(payload: dict) -> dict:
    return MODULE.recommend(payload)


class RecommendFixtureTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        FEEDBACK_STORE.write_text(json.dumps({'events': [], 'bias': {}, 'corrections': {}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_fixture_directory_exists(self):
        self.assertTrue(FIXTURES_DIR.exists())
        self.assertTrue(EXPECTED_DIR.exists())

    def test_fixture_cases_match_expected(self):
        fixture_files = sorted(FIXTURES_DIR.glob('*.json'))
        self.assertGreaterEqual(len(fixture_files), 20)
        for fixture_path in fixture_files:
            expected_path = EXPECTED_DIR / fixture_path.name
            self.assertTrue(expected_path.exists(), expected_path.name)
            payload = load_json(fixture_path)
            expectation = load_json(expected_path)
            result = run_recommend(payload)
            self.assertEqual(expectation['expected_recommendation'], result['recommendation'], fixture_path.name)
            if expectation.get('expected_normalized_dish'):
                self.assertEqual(expectation['expected_normalized_dish'], result.get('normalized_dish'), fixture_path.name)
            for tag in expectation.get('expected_risk_tags', []):
                self.assertIn(tag, result.get('risk_tags', []), fixture_path.name)
            for item in expectation.get('expected_need_confirm', []):
                self.assertIn(item, result.get('need_confirm', []), fixture_path.name)
            for snippet in expectation.get('assert_explanation_contains', []):
                self.assertIn(snippet, result.get('explanation', ''), fixture_path.name)
            if expectation.get('expect_human_field') is True:
                self.assertIn('human_readable_cn', result, fixture_path.name)
                for snippet in expectation.get('human_contains', []):
                    self.assertIn(snippet, result.get('human_readable_cn', ''), fixture_path.name)
            elif expectation.get('expect_human_field') is False:
                self.assertNotIn('human_readable_cn', result, fixture_path.name)

    def test_offline_fallback_is_stable(self):
        original_candidate = MODULE.fetch_cookbook_kg_candidate
        original_usda = MODULE.fetch_usda_nutrition
        try:
            MODULE.fetch_cookbook_kg_candidate = lambda query: None
            MODULE.fetch_usda_nutrition = lambda query: None
            result = run_recommend({'dish_name': '招牌小炒', 'user_profile': {'conditions': ['低盐']}})
            self.assertEqual('need_confirm', result['recommendation'])
            self.assertIn('主要食材', result['need_confirm'])
        finally:
            MODULE.fetch_cookbook_kg_candidate = original_candidate
            MODULE.fetch_usda_nutrition = original_usda

    def test_regression_guard_for_core_cases(self):
        core_cases = {
            '番茄炒蛋': 'avoid',
            '红烧肉': 'caution',
            '招牌小炒': 'need_confirm',
        }
        for dish_name, expected in core_cases.items():
            payload = {'dish_name': dish_name, 'user_profile': {'allergies': ['鸡蛋'], 'goals': ['减脂'], 'conditions': ['低盐', '控糖']}}
            if dish_name == '红烧肉':
                payload = {'dish_name': dish_name, 'user_profile': {'goals': ['减脂'], 'conditions': ['控糖']}}
            if dish_name == '招牌小炒':
                payload = {'dish_name': dish_name, 'user_profile': {'conditions': ['低盐']}}
            result = run_recommend(payload)
            self.assertEqual(expected, result['recommendation'], dish_name)


    def test_alias_and_candidate_normalization(self):
        result = run_recommend({'dish_name': '可乐鸡中翅', 'user_profile': {'conditions': ['控糖']}})
        self.assertEqual('可乐鸡翅', result['normalized_dish'])
        self.assertTrue(result.get('candidates'))
        self.assertEqual('可乐鸡翅', result['candidates'][0]['canonical_name'])


    def test_rule_priority_and_reason_limit(self):
        result = run_recommend({'dish_name': '麻辣小龙虾', 'user_profile': {'allergies': ['海鲜'], 'conditions': ['痛风'], 'goals': ['减脂']}})
        self.assertEqual('avoid', result['recommendation'])
        self.assertIn('含海鲜/鱼类', result['risk_tags'])
        reasons = result['explanation'].split('依据：', 1)[1].split('；')
        self.assertLessEqual(len([r for r in reasons if r]), 4)


    def test_output_modes(self):
        json_result = run_recommend({'dish_name': '番茄炒蛋', 'output_mode': 'json'})
        human_result = run_recommend({'dish_name': '番茄炒蛋', 'user_profile': {'allergies': ['鸡蛋']}, 'output_mode': 'human_readable_cn'})
        self.assertNotIn('human_readable_cn', json_result)
        self.assertIn('human_readable_cn', human_result)
        self.assertIn('结论：不推荐', human_result['human_readable_cn'])


def test_fallback_output_shape(self):
    original_candidate = MODULE.fetch_cookbook_kg_candidate
    original_usda = MODULE.fetch_usda_nutrition
    try:
        MODULE.fetch_cookbook_kg_candidate = lambda query: None
        MODULE.fetch_usda_nutrition = lambda query: None
        result = run_recommend({'dish_name': '未知料理', 'ingredients': ['chocolate'], 'user_profile': {'conditions': ['控糖']}})
        self.assertIn(result['recommendation'], {'caution', 'need_confirm'})
        self.assertIn('explanation', result)
    finally:
        MODULE.fetch_cookbook_kg_candidate = original_candidate
        MODULE.fetch_usda_nutrition = original_usda


if __name__ == '__main__':
    unittest.main()
