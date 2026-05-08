import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SKILL_DIR = ROOT / '.agents' / 'skills' / 'dish-health-recommender'
sys.path.insert(0, str(SKILL_DIR))

from providers import nutrition_provider as MODULE  # noqa: E402


class ApiValidationContractTests(unittest.TestCase):
    def test_api_validation_record_fields(self):
        records = MODULE.validate_all_providers()
        self.assertGreaterEqual(len(records), 2)
        required = {'provider_name', 'provider_type', 'status', 'request_sample', 'response_sample', 'credential_hint', 'degrade_strategy'}
        allowed_types = {'fallback', 'vision', 'nutrition', 'reference'}
        for item in records:
            self.assertTrue(required.issubset(item.keys()))
            self.assertIn(item['status'], {'validated', 'needs_credentials', 'unavailable', 'degraded'})
            self.assertIn(item['provider_type'], allowed_types)


if __name__ == '__main__':
    unittest.main()
