import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CONTRACT_PATH = ROOT / 'specs' / '20260508-dish-multi-verify' / 'contracts' / 'openapi.yaml'


class QuantizationContractTests(unittest.TestCase):
    def test_quantify_contract_exists(self):
        text = CONTRACT_PATH.read_text(encoding='utf-8')
        self.assertIn('/v2/nutrition/quantify', text)
        self.assertIn('QuantifiedNutritionProfile', text)


if __name__ == '__main__':
    unittest.main()
