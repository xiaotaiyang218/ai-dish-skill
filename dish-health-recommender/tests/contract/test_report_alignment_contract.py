import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SCRIPT_PATH = ROOT / '.agents' / 'skills' / 'dish-health-recommender' / 'scripts' / 'report_alignment.py'


class ReportAlignmentContractTests(unittest.TestCase):
    def test_default_alignment_payload_shape(self):
        proc = subprocess.run([sys.executable, str(SCRIPT_PATH)], text=True, capture_output=True, check=True)
        payload = json.loads(proc.stdout)
        self.assertIn('items', payload)
        self.assertTrue(payload['items'])
        first = payload['items'][0]
        for field in ['report_section', 'claim', 'implementation_refs', 'test_refs', 'status', 'boundary_note']:
            self.assertIn(field, first)


if __name__ == '__main__':
    unittest.main()
