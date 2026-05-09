import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[4]
FEATURE_DIR = CODE_ROOT / 'chuang' / 'specs' / '20260508-dish-skill-report'
CONTRACT_PATH = FEATURE_DIR / 'contracts' / 'openapi.yaml'
SCRIPT_PATH = CODE_ROOT / 'ai-dish-skill' / 'dish-health-recommender' / 'scripts' / 'recommend.py'


def load_recommend_module():
    spec = importlib.util.spec_from_file_location('dish_recommend', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def run_recommend(payload: dict) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload, ensure_ascii=False),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


class ContractShapeTests(unittest.TestCase):
    def test_openapi_mentions_result_fields(self):
        text = CONTRACT_PATH.read_text(encoding='utf-8')
        for field in ['normalized_dish', 'recommendation', 'confidence', 'ingredients', 'cooking_method', 'nutrition_tags', 'risk_tags', 'nutrition_evidence', 'explanation', 'need_confirm']:
            self.assertIn(field, text)

    def test_result_shape_matches_contract_core_fields(self):
        result = run_recommend({'dish_name': '番茄炒蛋', 'user_profile': {'allergies': ['鸡蛋']}})
        required = {'normalized_dish', 'recommendation', 'confidence', 'ingredients', 'cooking_method', 'nutrition_tags', 'risk_tags', 'nutrition_evidence', 'explanation', 'need_confirm'}
        self.assertTrue(required.issubset(result.keys()))

    def test_recommend_module_exports_core_entrypoints(self):
        module = load_recommend_module()
        for name in ['parse_request', 'recommend', 'render_human_readable_cn', 'build_result']:
            self.assertTrue(hasattr(module, name), name)


if __name__ == '__main__':
    unittest.main()
