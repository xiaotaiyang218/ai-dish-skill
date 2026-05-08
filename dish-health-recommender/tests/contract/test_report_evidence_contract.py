import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CONTRACT_PATH = ROOT / 'specs' / '20260508-dish-multi-verify' / 'contracts' / 'openapi.yaml'


class ReportEvidenceContractTests(unittest.TestCase):
    def test_report_evidence_contract_exists(self):
        text = CONTRACT_PATH.read_text(encoding='utf-8')
        self.assertIn('/v2/report/evidence', text)
        self.assertIn('InnovationEvidenceItem', text)


if __name__ == '__main__':
    unittest.main()
