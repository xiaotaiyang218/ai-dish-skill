import importlib.util
import json
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
RECOMMEND_PATH = SKILL_DIR / 'scripts' / 'recommend.py'
DATA_PATH = SKILL_DIR / 'data' / 'quantified_recipes.json'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


RECOMMEND = load_module(RECOMMEND_PATH, 'dish_recommend_quant')


class QuantizationTests(unittest.TestCase):
    def test_quantified_recipe_file_exists(self):
        self.assertTrue(DATA_PATH.exists())

    def test_quantified_recipes_count(self):
        data = json.loads(DATA_PATH.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(data.get('recipes', [])), 10)

    def test_quant_fields_exist_for_standard_recipe(self):
        result = RECOMMEND.recommend({'dish_name': '番茄炒蛋'})
        self.assertIn('nutrition_quantitative', result)
        for key in ['energy_kcal', 'protein_g', 'fat_g', 'carbohydrate_g', 'sugars_g', 'sodium_mg']:
            self.assertIn(key, result['nutrition_quantitative'])
        self.assertIn('nutrition_basis', result)
        self.assertIn('portion_basis', result)
        self.assertIn('nutrition_quantitative_display', result)
        display_by_key = {item['key']: item for item in result['nutrition_quantitative_display']}
        self.assertEqual('热量', display_by_key['energy_kcal']['label_cn'])
        self.assertEqual('Energy', display_by_key['energy_kcal']['label_en'])
        self.assertEqual('kcal', display_by_key['energy_kcal']['unit'])
        self.assertIn('千卡', display_by_key['energy_kcal']['text_cn'])
        self.assertIn('kcal', display_by_key['energy_kcal']['text_en'])
        self.assertEqual('g', display_by_key['protein_g']['unit'])
        self.assertEqual('mg', display_by_key['sodium_mg']['unit'])

    def test_added_quantified_dishes(self):
        for dish_name in ['家常豆腐', '胡辣汤', '荠菜鲜肉小馄饨', '香辣鸡腿堡', '劲脆超霸堡']:
            result = RECOMMEND.recommend({'dish_name': dish_name})
            self.assertIn('nutrition_quantitative', result)
            self.assertIn('nutrition_basis', result)
            self.assertIn('portion_basis', result)

    def test_aliases_can_hit_standard_quantified_recipe(self):
        alias_map = {
            '老家豆腐': '家常豆腐',
            '鲜肉小馄饨': '荠菜鲜肉小馄饨',
            '轻食鸡胸西兰花': '西兰花炒鸡胸肉',
        }
        for alias, canonical in alias_map.items():
            result = RECOMMEND.recommend({'dish_name': alias})
            self.assertEqual(canonical, result['normalized_dish'])
            self.assertIn('nutrition_quantitative', result)

    def test_fastfood_standard_recipes_expose_quantitative_basis(self):
        for dish_name in ['香辣鸡腿堡', '劲脆超霸堡']:
            result = RECOMMEND.recommend({'dish_name': dish_name})
            self.assertIn('标准快餐', result.get('nutrition_basis', ''))
            self.assertGreater(result['nutrition_quantitative']['energy_kcal'], 400)

    def test_shanghai_classic_dishes_expose_quantitative_recipe_basis(self):
        expected = {
            '红烧肉': 540,
            '腌笃鲜': 360,
            '八宝鸭': 620,
            '油爆虾': 330,
            '水晶虾仁': 260,
            '草头圈子': 430,
            '响油鳝丝': 410,
            '蟹粉豆腐': 360,
        }
        for dish_name, expected_energy in expected.items():
            result = RECOMMEND.recommend({'dish_name': dish_name})
            self.assertIn('nutrition_quantitative', result)
            self.assertEqual(expected_energy, result['nutrition_quantitative']['energy_kcal'])
            self.assertIn('nutrition_quantitative_display', result)
            self.assertIn('nutrition_basis', result)
            self.assertIn('portion_basis', result)
            self.assertIn('standard_ingredients', result)
            self.assertGreaterEqual(len(result['standard_ingredients']), 3)
            self.assertIn('energy_calculation', result)
            calculation = result['energy_calculation']
            self.assertEqual(expected_energy, calculation['total_energy_kcal'])
            self.assertIn('formula', calculation)
            self.assertGreaterEqual(len(calculation['items']), 3)
            self.assertEqual(
                expected_energy,
                sum(item['energy_kcal'] for item in calculation['items']),
            )
            self.assertIn('confidence_note', result)

    def test_shanghai_quantified_aliases_hit_canonical_recipe(self):
        alias_map = {
            '上海八宝鸭': '八宝鸭',
            '响油鳝糊': '响油鳝丝',
            '蟹黄豆腐': '蟹粉豆腐',
        }
        for alias, canonical in alias_map.items():
            result = RECOMMEND.recommend({'dish_name': alias})
            self.assertEqual(canonical, result['normalized_dish'])
            self.assertIn('nutrition_quantitative', result)
            self.assertIn('standard_ingredients', result)
            self.assertIn('energy_calculation', result)

    def test_western_dessert_tiramisu_exposes_quantitative_recipe_basis(self):
        result = RECOMMEND.recommend({'dish_name': 'tiramisu', 'user_profile': {'goals': ['减脂'], 'conditions': ['控糖']}})
        self.assertEqual('提拉米苏', result['normalized_dish'])
        self.assertEqual('caution', result['recommendation'])
        self.assertIn('可能高糖', result['risk_tags'])
        self.assertIn('可能高脂', result['risk_tags'])
        self.assertIn('碳水来源', result['risk_tags'])
        self.assertEqual(390, result['nutrition_quantitative']['energy_kcal'])
        self.assertEqual(23, result['nutrition_quantitative']['sugars_g'])
        self.assertIn('标准份量估算', result['nutrition_basis'])
        self.assertIn('standard_ingredients', result)
        self.assertIn('energy_calculation', result)
        self.assertEqual(390, result['energy_calculation']['total_energy_kcal'])
        self.assertNotIn('红烧调味', result['explanation'])
        self.assertNotIn('肥肉', result['explanation'])
        self.assertEqual(
            390,
            sum(item['energy_kcal'] for item in result['energy_calculation']['items']),
        )

    def test_missing_standard_recipe_has_no_quant(self):
        result = RECOMMEND.recommend({'dish_name': '老板推荐'})
        self.assertNotIn('nutrition_quantitative', result)

    def test_ingredient_only_fallback_keeps_qualitative_boundary(self):
        result = RECOMMEND.recommend({'dish_name': '地方招牌', 'ingredients': ['豆腐', '辣椒', '生抽']})
        self.assertNotIn('nutrition_quantitative', result)
        self.assertIn(result['recommendation'], {'caution', 'need_confirm', 'recommend'})

    def test_new_local_ingredient_knowledge_still_does_not_create_quant(self):
        result = RECOMMEND.recommend({'dish_name': '地方招牌', 'ingredients': ['带皮五花肉', '料酒', '八角', '香叶']})
        self.assertNotIn('nutrition_quantitative', result)
        self.assertIn('带皮五花肉', result.get('nutrition_evidence', {}))
        self.assertIn('料酒', result.get('nutrition_evidence', {}))


if __name__ == '__main__':
    unittest.main()
