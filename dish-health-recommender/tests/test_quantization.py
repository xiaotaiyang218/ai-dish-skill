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

    def test_added_quantified_dishes(self):
        for dish_name in ['家常豆腐', '胡辣汤', '荠菜鲜肉小馄饨', '香辣鸡腿堡', '劲脆超霸堡']:
            result = RECOMMEND.recommend({'dish_name': dish_name})
            self.assertIn('nutrition_quantitative', result)
            self.assertIn('nutrition_basis', result)
            self.assertIn('portion_basis', result)

    def test_missing_standard_recipe_has_no_quant(self):
        result = RECOMMEND.recommend({'dish_name': '老板推荐'})
        self.assertNotIn('nutrition_quantitative', result)


if __name__ == '__main__':
    unittest.main()
