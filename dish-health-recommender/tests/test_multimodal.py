import importlib.util
import json
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
REPO_ROOT = SKILL_DIR.parents[2]
SCRIPT_PATH = SKILL_DIR / 'scripts' / 'recommend.py'
IMAGE_CASES_PATH = SKILL_DIR / 'data' / 'image_test_cases.json'


def load_recommend_module():
    spec = importlib.util.spec_from_file_location('dish_recommend', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MODULE = load_recommend_module()


def run_recommend(payload: dict) -> dict:
    return MODULE.recommend(payload)


class MultimodalTests(unittest.TestCase):
    def test_image_seed_file_exists(self):
        self.assertTrue(IMAGE_CASES_PATH.exists())

    def test_menu_ocr_images(self):
        targets = {
            '20260508-122944': ['泰式柠檬虾', '香烤鸡腿'],
            '20260508-123005': ['主荤', '半荤'],
            '20260508-123023': ['劲脆超霸堡', '香辣鸡腿堡'],
        }
        cases = {item['image_id']: item for item in json.loads(IMAGE_CASES_PATH.read_text(encoding='utf-8'))}
        for image_id, expected in targets.items():
            payload = {'image_path': str(REPO_ROOT / cases[image_id]['image_path'])}
            result = run_recommend(payload)
            raw = json.dumps(result.get('raw_image_result', {}), ensure_ascii=False)
            for dish in expected:
                self.assertIn(dish, raw)

    def test_dish_candidate_images(self):
        targets = {
            '20260508-123058': ['胡辣汤', '豆腐脑'],
            '20260508-123047': ['荠菜鲜肉小馄饨'],
            '20260508-123050': ['鸡蛋红肠粉'],
        }
        cases = {item['image_id']: item for item in json.loads(IMAGE_CASES_PATH.read_text(encoding='utf-8'))}
        for image_id, expected in targets.items():
            payload = {'image_path': str(REPO_ROOT / cases[image_id]['image_path'])}
            result = run_recommend(payload)
            raw = json.dumps(result.get('raw_image_result', {}), ensure_ascii=False)
            for dish in expected:
                self.assertIn(dish, raw)

    def test_need_confirm_on_noisy_unknown_image(self):
        result = run_recommend({'image_reference': 'raw/0e329814-19c4-452d-9ecf-f3828b1a3417.jpg'})
        self.assertEqual('need_confirm', result['recommendation'])
        self.assertIn('缺少文本识别结果', result['risk_tags'])


def test_menu_image_records_ocr_status(self):
    result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-122944.jpg')})
    self.assertIn('raw_image_result', result)
    self.assertIn(result['raw_image_result']['ocr']['status'], {'validated', 'degraded', 'needs_credentials', 'unavailable'})


if __name__ == '__main__':
    unittest.main()
