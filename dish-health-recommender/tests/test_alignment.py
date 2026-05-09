import importlib.util
import json
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

    def test_metrics_artifact_is_referenced_by_alignment_items(self):
        metric_refs = []
        for item in MODULE.default_items():
            metric_refs.extend(item.get('validation_refs', []))
            if item.get('metric_summary'):
                self.assertTrue(item['metric_summary'])
        self.assertIn('dish-health-recommender/validation/image-validation-report.json', metric_refs)

    def test_degradable_or_pending_items_keep_boundary_language(self):
        for item in MODULE.default_items():
            if item['status'] in {'degradable', 'pending_validation'}:
                self.assertTrue(any(token in item['boundary_note'] for token in ['待验证', '降级', '未承诺', '仍需', '边界']))

    def test_optional_sources_are_documented_as_offline_import_only(self):
        payload = MODULE.default_items()
        evidence_text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn('运行时强依赖', evidence_text)
        self.assertNotIn('在线必需', evidence_text)


if __name__ == '__main__':
    unittest.main()
