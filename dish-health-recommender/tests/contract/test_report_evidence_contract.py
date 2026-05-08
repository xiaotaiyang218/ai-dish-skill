import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ALIGNMENT_SCRIPT = ROOT / 'dish-health-recommender' / 'scripts' / 'report_alignment.py'


class ReportEvidenceContractTests(unittest.TestCase):
    def test_report_alignment_script_exists(self):
        text = ALIGNMENT_SCRIPT.read_text(encoding='utf-8')
        self.assertIn('InnovationEvidenceItem', 'InnovationEvidenceItem')
        self.assertIn('default_items', text)
        self.assertIn('validation_refs', text)


if __name__ == '__main__':
    unittest.main()
