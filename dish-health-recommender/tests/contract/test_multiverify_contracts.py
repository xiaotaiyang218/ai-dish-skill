import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CONTRACT_PATH = ROOT / 'specs' / '20260508-dish-multi-verify' / 'contracts' / 'openapi.yaml'


class MultiVerifyContractTests(unittest.TestCase):
    def test_v2_endpoints_exist(self):
        text = CONTRACT_PATH.read_text(encoding='utf-8')
        for endpoint in ['/v2/recommendations/multimodal', '/v2/validation/images', '/v2/validation/apis', '/v2/feedback', '/v2/nutrition/quantify', '/v2/report/evidence']:
            self.assertIn(endpoint, text)

    def test_v2_schema_names_exist(self):
        text = CONTRACT_PATH.read_text(encoding='utf-8')
        for schema in ['MultimodalRequest', 'MultimodalRecommendationResult', 'ImageTestCase', 'ImageValidationReport', 'ApiValidationRecord', 'FeedbackEvent', 'QuantifiedNutritionProfile', 'InnovationEvidenceItem']:
            self.assertIn(schema, text)


if __name__ == '__main__':
    unittest.main()
