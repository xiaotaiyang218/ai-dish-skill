import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
SCRIPT_PATH = SKILL_DIR / 'scripts' / 'recommend.py'
FIXTURES_DIR = TESTS_DIR / 'fixtures'
EXPECTED_DIR = TESTS_DIR / 'expected'
FEEDBACK_STORE = SKILL_DIR / 'data' / 'feedback.json'
LOCAL_DISHES_PATH = SKILL_DIR / 'data' / 'dishes.json'


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_recommend_module():
    spec = importlib.util.spec_from_file_location('dish_recommend', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


MODULE = load_recommend_module()


def run_recommend(payload: dict) -> dict:
    return MODULE.recommend(payload)


class RecommendFixtureTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        FEEDBACK_STORE.write_text(json.dumps({'events': [], 'bias': {}, 'corrections': {}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.spoonacular_patcher = mock.patch.object(MODULE, 'spoonacular_api_key', return_value='')
        self.spoonacular_patcher.start()

    def tearDown(self):
        self.spoonacular_patcher.stop()

    def test_fixture_directory_exists(self):
        self.assertTrue(FIXTURES_DIR.exists())
        self.assertTrue(EXPECTED_DIR.exists())

    def test_core_use_case_standard_dishes_exist_in_local_database(self):
        local_dishes = load_json(LOCAL_DISHES_PATH)
        for dish_name in ['番茄炒蛋', '鱼香肉丝']:
            self.assertIn(dish_name, local_dishes)
            self.assertGreaterEqual(len(local_dishes[dish_name].get('ingredients', [])), 3)
            self.assertIn('risk_tags', local_dishes[dish_name])

    def test_fixture_cases_match_expected(self):
        fixture_files = sorted(FIXTURES_DIR.glob('*.json'))
        self.assertGreaterEqual(len(fixture_files), 20)
        for fixture_path in fixture_files:
            expected_path = EXPECTED_DIR / fixture_path.name
            self.assertTrue(expected_path.exists(), expected_path.name)
            payload = load_json(fixture_path)
            expectation = load_json(expected_path)
            result = run_recommend(payload)
            self.assertEqual(expectation['expected_recommendation'], result['recommendation'], fixture_path.name)
            if expectation.get('expected_normalized_dish'):
                self.assertEqual(expectation['expected_normalized_dish'], result.get('normalized_dish'), fixture_path.name)
            for tag in expectation.get('expected_risk_tags', []):
                self.assertIn(tag, result.get('risk_tags', []), fixture_path.name)
            for item in expectation.get('expected_need_confirm', []):
                self.assertIn(item, result.get('need_confirm', []), fixture_path.name)
            for snippet in expectation.get('assert_explanation_contains', []):
                self.assertIn(snippet, result.get('explanation', ''), fixture_path.name)
            if expectation.get('expect_human_field') is True:
                self.assertIn('human_readable_cn', result, fixture_path.name)
                for snippet in expectation.get('human_contains', []):
                    self.assertIn(snippet, result.get('human_readable_cn', ''), fixture_path.name)
            elif expectation.get('expect_human_field') is False:
                self.assertNotIn('human_readable_cn', result, fixture_path.name)

    def test_offline_fallback_is_stable(self):
        original_candidate = MODULE.fetch_online_recipe_candidate
        original_usda = MODULE.fetch_usda_nutrition
        try:
            MODULE.fetch_online_recipe_candidate = lambda query: None
            MODULE.fetch_usda_nutrition = lambda query: None
            result = run_recommend({'dish_name': '招牌小炒', 'user_profile': {'conditions': ['低盐']}})
            self.assertEqual('need_confirm', result['recommendation'])
            self.assertIn('主要食材', result['need_confirm'])
        finally:
            MODULE.fetch_online_recipe_candidate = original_candidate
            MODULE.fetch_usda_nutrition = original_usda

    def test_spoonacular_candidate_is_optional_and_not_called_for_local_hit(self):
        with mock.patch.object(MODULE, 'fetch_spoonacular_candidate', side_effect=AssertionError('should not call spoonacular')):
            result = run_recommend({'dish_name': '番茄炒蛋', 'user_profile': {'allergies': ['鸡蛋']}})
        self.assertEqual('番茄炒蛋', result['normalized_dish'])
        self.assertEqual('avoid', result['recommendation'])

    def test_shanghai_classic_dishes_have_descriptive_notes(self):
        expected_note_snippets = {
            '红烧肉': '浓油赤酱',
            '腌笃鲜': '春笋',
            '八宝鸭': '宴席',
            '油爆虾': '火候',
            '水晶虾仁': '晶莹',
            '草头圈子': '猪大肠',
            '响油鳝丝': '热油',
            '蟹粉豆腐': '蟹粉',
        }
        for dish_name, snippet in expected_note_snippets.items():
            self.assertIn(snippet, MODULE.DISHES[dish_name]['notes'], dish_name)

    def test_xiachufang_candidate_parses_search_result(self):
        html = '''
        <div class="recipe recipe-215-horizontal pure-g image-link display-block">
            <a href="/recipe/100124682/" target="_blank"></a>
            <div class="info pure-u">
                <p class="name">
                    <a href="/recipe/100124682/" target="_blank">不焯水不放油的家常红烧肉</a>
                </p>
                <p class="ing ellipsis">
                    <a href="/category/5308/" target="_blank">带皮五花肉</a>、<a href="/category/1820/" target="_blank">冰糖</a>、<a href="/category/1563/" target="_blank">姜片</a>
                </p>
            </div>
        </div>
        '''
        with mock.patch.object(MODULE, 'online_recipe_request', return_value=html):
            candidate = MODULE.fetch_xiachufang_candidate('红烧肉')
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual('不焯水不放油的家常红烧肉', candidate[0])
        self.assertIn('带皮五花肉', candidate[1]['ingredients'])
        self.assertEqual('xiachufang search', candidate[1]['source'])

    def test_douguo_candidate_parses_search_result(self):
        html = '''
        <li class="menu-content">
            <a href="/cookbook/3331354.html?f=www" class="cooka flex">
                <div class="feed-content flex-1">
                    <div class="recipe-wrap mb10">
                       <h2 class="recipe-name text-clamp">红烧肉</h2>
                       <div class="recipe-cai text-lips">五花肉 葱 姜 八角 桂皮 香叶 冰糖 生抽 老抽 料酒 盐</div>
                    </div>
                </div>
            </a>
        </li>
        '''
        with mock.patch.object(MODULE, 'online_recipe_request', return_value=html):
            candidate = MODULE.fetch_douguo_candidate('红烧肉')
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual('红烧肉', candidate[0])
        self.assertIn('五花肉', candidate[1]['ingredients'])
        self.assertEqual('douguo search', candidate[1]['source'])

    def test_xiangha_candidate_parses_search_result(self):
        html = '''
        <li><a class="pic videoIcon_160" title="红烧肉" href="https://www.xiangha.com/caipu/100249267.html" target="_blank"></a>
        <div class="ins"><p class="name kw"><a title="红烧肉" href="https://www.xiangha.com/caipu/100249267.html" target="_blank">红烧肉</a></p>
        <p class="info">用料：冰糖,姜,辣椒,大葱,花椒,大蒜,八角,五花肉块,盐,生抽,食用油,温开水,料酒</p></div></li>
        '''
        with mock.patch.object(MODULE, 'online_recipe_request', return_value=html):
            candidate = MODULE.fetch_xiangha_candidate('红烧肉')
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual('红烧肉', candidate[0])
        self.assertIn('五花肉块', candidate[1]['ingredients'])
        self.assertEqual('xiangha search', candidate[1]['source'])

    def test_online_recipe_candidate_uses_chinese_site_before_spoonacular_after_cookbook_kg_miss(self):
        original_cookbook = MODULE.fetch_cookbook_kg_candidate
        original_xiachufang = MODULE.fetch_xiachufang_candidate
        original_douguo = MODULE.fetch_douguo_candidate
        original_xiangha = MODULE.fetch_xiangha_candidate
        original_spoonacular = MODULE.fetch_spoonacular_candidate
        try:
            MODULE.fetch_cookbook_kg_candidate = lambda query: None
            MODULE.fetch_xiachufang_candidate = lambda query: ('家常红烧肉', {
                'aliases': [],
                'ingredients': ['五花肉', '冰糖'],
                'cooking_method': '红烧',
                'risk_tags': ['可能高脂'],
                'notes': 'xiachufang',
                'source': 'xiachufang search',
                'ambiguity_level': 'medium',
            })
            MODULE.fetch_douguo_candidate = lambda query: (_ for _ in ()).throw(AssertionError('should not call douguo'))
            MODULE.fetch_xiangha_candidate = lambda query: (_ for _ in ()).throw(AssertionError('should not call xiangha'))
            MODULE.fetch_spoonacular_candidate = lambda query: (_ for _ in ()).throw(AssertionError('should not call spoonacular'))
            candidate = MODULE.fetch_online_recipe_candidate('任意测试菜')
        finally:
            MODULE.fetch_cookbook_kg_candidate = original_cookbook
            MODULE.fetch_xiachufang_candidate = original_xiachufang
            MODULE.fetch_douguo_candidate = original_douguo
            MODULE.fetch_xiangha_candidate = original_xiangha
            MODULE.fetch_spoonacular_candidate = original_spoonacular
        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual('家常红烧肉', candidate[0])
        self.assertIn('五花肉', candidate[1]['ingredients'])
        self.assertEqual('xiachufang search', candidate[1]['source'])

    def test_online_recipe_candidate_uses_spoonacular_after_other_sites_miss(self):
        original_cookbook = MODULE.fetch_cookbook_kg_candidate
        original_xiachufang = MODULE.fetch_xiachufang_candidate
        original_douguo = MODULE.fetch_douguo_candidate
        original_xiangha = MODULE.fetch_xiangha_candidate
        original_spoonacular = MODULE.fetch_spoonacular_candidate
        try:
            MODULE.fetch_cookbook_kg_candidate = lambda query: None
            MODULE.fetch_xiachufang_candidate = lambda query: None
            MODULE.fetch_douguo_candidate = lambda query: None
            MODULE.fetch_xiangha_candidate = lambda query: None
            MODULE.fetch_spoonacular_candidate = lambda query: ('Tomato Soup', {
                'aliases': [],
                'ingredients': ['tomato', 'onion'],
                'cooking_method': '煮',
                'risk_tags': [],
                'notes': 'spoonacular',
                'source': 'Spoonacular search',
                'ambiguity_level': 'medium',
            })
            result = run_recommend({'dish_name': 'Tomato Soup', 'user_profile': {'goals': ['减脂']}})
        finally:
            MODULE.fetch_cookbook_kg_candidate = original_cookbook
            MODULE.fetch_xiachufang_candidate = original_xiachufang
            MODULE.fetch_douguo_candidate = original_douguo
            MODULE.fetch_xiangha_candidate = original_xiangha
            MODULE.fetch_spoonacular_candidate = original_spoonacular
        self.assertEqual('Tomato Soup', result['normalized_dish'])
        self.assertIn('tomato', result['ingredients'])
        self.assertNotEqual('need_confirm', result['recommendation'])

    def test_regression_guard_for_core_cases(self):
        core_cases = {
            '番茄炒蛋': 'avoid',
            '红烧肉': 'caution',
            '招牌小炒': 'need_confirm',
        }
        for dish_name, expected in core_cases.items():
            payload = {'dish_name': dish_name, 'user_profile': {'allergies': ['鸡蛋'], 'goals': ['减脂'], 'conditions': ['低盐', '控糖']}}
            if dish_name == '红烧肉':
                payload = {'dish_name': dish_name, 'user_profile': {'goals': ['减脂'], 'conditions': ['控糖']}}
            if dish_name == '招牌小炒':
                payload = {'dish_name': dish_name, 'user_profile': {'conditions': ['低盐']}}
            result = run_recommend(payload)
            self.assertEqual(expected, result['recommendation'], dish_name)


    def test_alias_and_candidate_normalization(self):
        result = run_recommend({'dish_name': '可乐鸡中翅', 'user_profile': {'conditions': ['控糖']}})
        self.assertEqual('可乐鸡翅', result['normalized_dish'])
        self.assertTrue(result.get('candidates'))
        self.assertEqual('可乐鸡翅', result['candidates'][0]['canonical_name'])

    def test_regional_dish_alias_hits_standard_dish(self):
        result = run_recommend({'dish_name': '老家豆腐', 'user_profile': {'conditions': ['低盐']}})
        self.assertEqual('家常豆腐', result['normalized_dish'])
        self.assertIn('可能高盐', result['risk_tags'])

    def test_fastfood_dishes_keep_qualitative_and_quantitative_boundary(self):
        result = run_recommend({'dish_name': '香辣鸡腿堡', 'user_profile': {'goals': ['减脂'], 'conditions': ['低盐']}})
        self.assertEqual('香辣鸡腿堡', result['normalized_dish'])
        self.assertIn('nutrition_quantitative', result)
        self.assertIn('可能高盐', result['risk_tags'])
        self.assertIn(result['recommendation'], {'caution', 'avoid'})

    def test_qualitative_only_fallback_does_not_forge_quantitative_fields(self):
        result = run_recommend({'dish_name': '地方招牌菜', 'ingredients': ['豆腐', '青椒', '生抽'], 'user_profile': {'conditions': ['低盐']}})
        self.assertNotIn('nutrition_quantitative', result)
        self.assertIn('可能高盐', result['risk_tags'])

    def test_high_frequency_seasonings_use_local_nutrition_knowledge(self):
        original_candidate = MODULE.fetch_cookbook_kg_candidate
        original_usda = MODULE.fetch_usda_nutrition
        try:
            MODULE.fetch_cookbook_kg_candidate = lambda query: None
            MODULE.fetch_usda_nutrition = lambda query: (_ for _ in ()).throw(AssertionError('should not call usda'))
            result = run_recommend({
                'dish_name': '地方招牌菜',
                'ingredients': ['带皮五花肉', '料酒', '八角', '香叶'],
                'user_profile': {'goals': ['减脂']},
            })
        finally:
            MODULE.fetch_cookbook_kg_candidate = original_candidate
            MODULE.fetch_usda_nutrition = original_usda
        self.assertNotIn('nutrition_quantitative', result)
        self.assertIn('可能高脂', result['risk_tags'])
        self.assertIn('带皮五花肉', result['nutrition_evidence'])
        self.assertIn('料酒', result['nutrition_evidence'])
        self.assertIn('八角', result['nutrition_evidence'])
        self.assertIn('香叶', result['nutrition_evidence'])
        self.assertIn('调味品', result['nutrition_tags'])

    def test_local_variant_ingredients_match_without_online_fallback(self):
        original_candidate = MODULE.fetch_cookbook_kg_candidate
        original_usda = MODULE.fetch_usda_nutrition
        try:
            MODULE.fetch_cookbook_kg_candidate = lambda query: None
            MODULE.fetch_usda_nutrition = lambda query: (_ for _ in ()).throw(AssertionError('should not call usda'))
            result = run_recommend({
                'dish_name': '地方招牌菜',
                'ingredients': ['葱段', '姜片', '大蒜'],
                'user_profile': {'conditions': ['低盐']},
            })
        finally:
            MODULE.fetch_cookbook_kg_candidate = original_candidate
            MODULE.fetch_usda_nutrition = original_usda
        self.assertNotIn('nutrition_quantitative', result)
        self.assertIn('葱段', result['nutrition_evidence'])
        self.assertIn('姜片', result['nutrition_evidence'])
        self.assertIn('大蒜', result['nutrition_evidence'])
        self.assertIn('调味辅料', result['nutrition_tags'])


    def test_rule_priority_and_reason_limit(self):
        result = run_recommend({'dish_name': '麻辣小龙虾', 'user_profile': {'allergies': ['海鲜'], 'conditions': ['痛风'], 'goals': ['减脂']}})
        self.assertEqual('avoid', result['recommendation'])
        self.assertIn('含海鲜/鱼类', result['risk_tags'])
        reasons = result['explanation'].split('依据：', 1)[1].split('；')
        self.assertLessEqual(len([r for r in reasons if r]), 4)


    def test_output_modes(self):
        json_result = run_recommend({'dish_name': '番茄炒蛋', 'output_mode': 'json'})
        human_result = run_recommend({'dish_name': '番茄炒蛋', 'user_profile': {'allergies': ['鸡蛋']}, 'output_mode': 'human_readable_cn'})
        self.assertNotIn('human_readable_cn', json_result)
        self.assertIn('human_readable_cn', human_result)
        self.assertIn('结论：不推荐', human_result['human_readable_cn'])
        self.assertLess(
            human_result['human_readable_cn'].index('客观信息：'),
            human_result['human_readable_cn'].index('结论：不推荐'),
        )

    def test_inherent_high_risk_dish_is_not_recommended_without_user_constraints(self):
        result = run_recommend({'dish_name': '草头圈子'})
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('动物内脏', result['risk_tags'])
        self.assertIn('可能高脂', result['risk_tags'])
        self.assertIn('风险标签', result['explanation'])

    def test_human_readable_answer_includes_objective_analysis_before_advice(self):
        result = run_recommend({'dish_name': '草头圈子', 'output_mode': 'human_readable_cn'})
        answer = result['human_readable_cn']
        self.assertLess(answer.index('客观信息：'), answer.index('结论：谨慎'))
        self.assertLess(answer.index('结论：谨慎'), answer.index('建议：'))
        self.assertIn('识别菜品：草头圈子', answer)
        self.assertIn('风险标签：', answer)
        self.assertIn('营养估算：', answer)
        self.assertIn('千卡', answer)
        self.assertIn('热量 430 千卡；蛋白质 18 克', answer)
        self.assertNotIn("[{'key':", answer)


def test_fallback_output_shape(self):
    original_candidate = MODULE.fetch_cookbook_kg_candidate
    original_usda = MODULE.fetch_usda_nutrition
    try:
        MODULE.fetch_cookbook_kg_candidate = lambda query: None
        MODULE.fetch_usda_nutrition = lambda query: None
        result = run_recommend({'dish_name': '未知料理', 'ingredients': ['chocolate'], 'user_profile': {'conditions': ['控糖']}})
        self.assertIn(result['recommendation'], {'caution', 'need_confirm'})
        self.assertIn('explanation', result)
    finally:
        MODULE.fetch_cookbook_kg_candidate = original_candidate
        MODULE.fetch_usda_nutrition = original_usda


if __name__ == '__main__':
    unittest.main()
