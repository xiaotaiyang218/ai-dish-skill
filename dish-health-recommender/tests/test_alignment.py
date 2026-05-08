import importlib.util
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / 'scripts' / 'report_alignment.py'


def load_module():
    spec = importlib.util.spec_from_file_location('report_alignment', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


class ReportAlignmentTests(unittest.TestCase):
    def test_status_enum_and_boundary_notes(self):
        payload = MODULE.default_items()
        summary = MODULE.validate_items(payload)
        self.assertTrue(summary['valid'])
        self.assertGreaterEqual(summary['implemented'], 3)
        for item in payload:
            self.assertIn(item['status'], MODULE.ALLOWED_STATUS)
            self.assertTrue(item['boundary_note'])

    def test_implemented_items_require_validation_refs(self):
        for item in MODULE.default_items():
            if item['status'] == 'implemented':
                self.assertTrue(item.get('implementation_refs'))
                self.assertTrue(item.get('test_refs'))
                self.assertTrue(item.get('validation_refs'))


if __name__ == '__main__':
    unittest.main()
