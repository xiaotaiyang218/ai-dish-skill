import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
REPO_ROOT = SKILL_DIR.parent
SCRIPT_PATH = SKILL_DIR / 'scripts' / 'recommend.py'
IMAGE_CASES_PATH = SKILL_DIR / 'data' / 'image_test_cases.json'
if str(SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_DIR))


def load_recommend_module():
    spec = importlib.util.spec_from_file_location('dish_recommend', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MODULE = load_recommend_module()
from providers import vision_provider as VISION_MODULE


def run_recommend(payload: dict) -> dict:
    return MODULE.recommend(payload)


def case_map() -> dict[str, dict]:
    return {item['image_id']: item for item in json.loads(IMAGE_CASES_PATH.read_text(encoding='utf-8'))}


class MultimodalTests(unittest.TestCase):
    def setUp(self):
        self.spoonacular_patcher = mock.patch.object(MODULE, 'spoonacular_api_key', return_value='')
        self.spoonacular_patcher.start()

    def tearDown(self):
        self.spoonacular_patcher.stop()

    def test_image_seed_file_exists(self):
        self.assertTrue(IMAGE_CASES_PATH.exists())

    def test_menu_ocr_images(self):
        targets = {
            '20260508-122944': ['泰式柠檬虾', '香烤鸡腿'],
            '20260508-123005': ['主荤', '半荤'],
            '20260508-123023': ['劲脆超霸堡', '香辣鸡腿堡'],
        }
        cases = case_map()
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
        cases = case_map()
        for image_id, expected in targets.items():
            payload = {'image_path': str(REPO_ROOT / cases[image_id]['image_path'])}
            result = run_recommend(payload)
            raw = json.dumps(result.get('raw_image_result', {}), ensure_ascii=False)
            for dish in expected:
                self.assertIn(dish, raw)

    def test_image_only_path_uses_provider_candidates_when_available(self):
        result = run_recommend({'image_reference': 'pic/20260508-123047.jpg'})
        self.assertEqual('荠菜鲜肉小馄饨', result['normalized_dish'])
        self.assertNotEqual('need_confirm', result['recommendation'])
        self.assertIn('raw_image_result', result)

    def test_existing_non_pic_image_path_still_runs_image_providers(self):
        source = REPO_ROOT / 'pic/20260508-123047.jpg'
        upload_like_path = REPO_ROOT / 'tmp-upload-20260508-123047.jpg'
        upload_like_path.write_bytes(source.read_bytes())
        self.addCleanup(lambda: upload_like_path.unlink(missing_ok=True))
        result = run_recommend({'image_path': str(upload_like_path)})
        self.assertEqual('荠菜鲜肉小馄饨', result['normalized_dish'])
        self.assertIn('raw_image_result', result)
        self.assertTrue(result['raw_image_result']['ocr'])
        self.assertTrue(result['raw_image_result']['vision'])

    def test_uploaded_menu_image_uses_inferred_menu_text(self):
        result = run_recommend({
            'image_path': '/Users/bytedance/.vibelet/data/uploads/1778294482228_a4e2938a20c3be8d.png',
            'user_profile': {'goals': ['减脂']},
        })
        self.assertNotEqual('need_confirm', result['recommendation'])
        self.assertTrue(result.get('normalized_dish'))
        self.assertIn('raw_image_result', result)

    def test_menu_candidate_prefers_online_match_before_ingredient_fallback(self):
        original_fetch = MODULE.fetch_online_recipe_candidate
        original_infer = MODULE.infer_ingredients_from_name
        try:
            MODULE.fetch_online_recipe_candidate = lambda query: ('线上命中菜品', {
                'aliases': [],
                'ingredients': ['鸡肉'],
                'cooking_method': '炒',
                'risk_tags': [],
                'notes': 'online',
                'source': 'CookBook-KG online',
                'ambiguity_level': 'medium',
            })
            MODULE.infer_ingredients_from_name = lambda name: ['木耳']
            result = run_recommend({
                'image_path': '/Users/bytedance/.vibelet/data/uploads/1778294482228_a4e2938a20c3be8d.png',
                'user_profile': {'goals': ['减脂']},
            })
        finally:
            MODULE.fetch_online_recipe_candidate = original_fetch
            MODULE.infer_ingredients_from_name = original_infer
        self.assertEqual('线上命中菜品', result['normalized_dish'])
        self.assertIn('鸡肉', result['ingredients'])
        self.assertNotEqual('need_confirm', result['recommendation'])

    def test_blurry_dish_image_degrades_to_need_confirm(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-123014.jpg')})
        self.assertEqual('need_confirm', result['recommendation'])
        self.assertIsNone(result['normalized_dish'])
        self.assertIn('raw_image_result', result)
        self.assertIn(result['raw_image_result']['ocr']['status'], {'validated', 'degraded', 'needs_credentials', 'unavailable'})

    def test_multi_dish_scene_degrades_to_manual_confirmation(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-123043.jpg')})

        self.assertEqual('need_confirm', result['recommendation'])
        self.assertIsNone(result['normalized_dish'])
        self.assertEqual('multi_dish', result['image_scene']['type'])
        self.assertIn('多菜同屏', result['risk_tags'])
        self.assertIn('人工确认菜品区域', result['need_confirm'])
        self.assertIn('多菜同屏', result['explanation'])
        self.assertIn('visual_category_hints', result['image_scene'])

    def test_conflicting_candidate_image_does_not_use_garbage_seed(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-123019.jpg')})
        self.assertEqual('need_confirm', result['recommendation'])
        self.assertIn(result.get('normalized_dish'), {None, '未知菜品'})
        self.assertTrue(all('肯德基' not in item.get('canonical_name', '') for item in result.get('candidates', []) if isinstance(item, dict)))

    def test_provider_degradation_falls_back_to_local_ocr_candidates(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-123047.jpg')})
        raw = result['raw_image_result']
        self.assertEqual('荠菜鲜肉小馄饨', result['normalized_dish'])
        self.assertEqual('ocr_assisted_vision', raw['vision']['provider_name'])
        self.assertEqual('validated', raw['vision']['status'])
        self.assertEqual('validated', raw['ocr']['status'])

    def test_annotated_shanghai_dish_image_uses_human_confirmed_label(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/2.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('腌笃鲜', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认', json.dumps(result.get('raw_image_result', {}), ensure_ascii=False))
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('可能高盐', result['risk_tags'])

    def test_annotated_babao_duck_image_uses_human_confirmed_label(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/3.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('八宝鸭', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('可能高脂', result['risk_tags'])
        self.assertIn('碳水来源', result['risk_tags'])

    def test_annotated_youbao_shrimp_image_uses_human_confirmed_label(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/4.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('油爆虾', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('含海鲜/鱼类', result['risk_tags'])
        self.assertIn('可能高油', result['risk_tags'])

    def test_annotated_crystal_shrimp_image_uses_human_confirmed_label(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/5.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('水晶虾仁', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('含海鲜/鱼类', result['risk_tags'])
        self.assertIn('碳水来源', result['risk_tags'])

    def test_annotated_caotou_quanzi_image_overrides_baidu_pig_trotter(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/6.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('草头圈子', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('动物内脏', result['risk_tags'])
        self.assertIn('可能高脂', result['risk_tags'])

    def test_annotated_eel_slices_image_uses_human_confirmed_label(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/7.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('响油鳝丝', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('含海鲜/鱼类', result['risk_tags'])
        self.assertIn('可能高油', result['risk_tags'])

    def test_annotated_crab_tofu_image_uses_human_confirmed_label(self):
        result = run_recommend({
            'image_path': str(REPO_ROOT / 'pic/shanghai/8.jpeg'),
            'user_profile': {'goals': ['减脂']},
        })

        self.assertEqual('蟹粉豆腐', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('人工确认图片标签', result['explanation'])
        self.assertIn('含海鲜/鱼类', result['risk_tags'])
        self.assertIn('碳水来源', result['risk_tags'])

    def test_unknown_menu_image_returns_provider_backed_result(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-123010.jpg')})
        self.assertNotEqual('need_confirm', result['recommendation'])
        self.assertTrue(result['normalized_dish'])
        self.assertIn('raw_image_result', result)

    def test_menu_image_records_ocr_status(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-122944.jpg')})
        self.assertIn('raw_image_result', result)
        self.assertIn(result['raw_image_result']['ocr']['status'], {'validated', 'degraded', 'needs_credentials', 'unavailable'})

    def test_fixture_menu_ocr_preserves_full_historical_text(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-122944.jpg')})
        ocr = result['raw_image_result']['ocr']

        self.assertGreater(len(ocr.get('lines', [])), 40)
        self.assertIn('鱼香肉丝', ocr.get('text', ''))
        self.assertIn('红豆汤', ocr.get('text', ''))

    def test_menu_recommendation_includes_stall_name(self):
        result = run_recommend({'image_path': str(REPO_ROOT / 'pic/20260508-122944.jpg')})

        self.assertEqual('鱼香肉丝', result['normalized_dish'])
        self.assertEqual('5F川湘一品•擂饭', result['stall_name'])
        self.assertEqual({'dish_name': '鱼香肉丝', 'stall_name': '5F川湘一品•擂饭'}, result['menu_source'])
        self.assertIn('5F川湘一品•擂饭', result['explanation'])

    def test_vision_filter_keeps_short_valid_dish_names(self):
        self.assertFalse(VISION_MODULE._is_low_value_candidate('馄饨'))
        self.assertFalse(VISION_MODULE._is_low_value_candidate('猪蹄'))
        self.assertFalse(VISION_MODULE._is_low_value_candidate('猪蹄煲'))
        self.assertTrue(VISION_MODULE._is_low_value_candidate('非菜'))

    def test_image_case_labels_support_metrics_statistics(self):
        cases = case_map()
        for image_id in ['20260508-122944', '20260508-123023', '20260508-123047', '20260508-123010']:
            case = cases[image_id]
            self.assertIn('expected_dishes', case)
            self.assertIn('ocr_expectation', case)
            self.assertIn('need_confirm_allowed', case)
            self.assertIn('notes', case)


if __name__ == '__main__':
    unittest.main()
