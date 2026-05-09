import importlib.util
import json
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
CHAT_PATH = SKILL_DIR / 'scripts' / 'chat_recommend.py'
STORE_PATH = SKILL_DIR / 'data' / 'feedback.json'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


CHAT = load_module(CHAT_PATH, 'chat_recommend')


def empty_store() -> dict:
    return {
        'events': [],
        'profiles': {'dish': {}, 'user_dish': {}},
        'corrections': {},
        'meta': {'last_feedback_at': ''},
    }


class NaturalLanguageE2ETests(unittest.TestCase):
    def setUp(self):
        STORE_PATH.write_text(json.dumps(empty_store(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_text_question(self):
        answer = CHAT.answer_user_query({'user_query': '我鸡蛋过敏，番茄炒蛋能吃吗？'})
        self.assertIn('不推荐', answer)
        self.assertIn('鸡蛋', answer)
        self.assertIn('热量约', answer)

    def test_menu_recommendation(self):
        answer = CHAT.answer_user_query({'user_query': '这张菜单里帮我挑3个更适合减脂和低盐的菜', 'image_path': 'pic/20260508-122944.jpg'})
        self.assertIn('更适合优先考虑', answer)
        self.assertTrue(any(x in answer for x in ['清炒小青菜', '清炒西兰花', '清炒冬瓜', '香烤鸡腿']))

    def test_variant_question(self):
        answer = CHAT.answer_user_query({'user_query': '豆腐脑适合控糖吗？'})
        self.assertIn('甜豆腐脑', answer)
        self.assertIn('咸豆腐脑', answer)
        self.assertIn('你吃的是甜的还是咸的', answer)

    def test_unrecognized_image_requests_clarification(self):
        answer = CHAT.answer_user_query({'user_query': '帮我看看这张图里哪个更适合减脂', 'image_reference': 'raw/0e329814-19c4-452d-9ecf-f3828b1a3417.jpg'})
        self.assertIn('不能可靠判断', answer)
        self.assertIn('这是菜单还是单道菜照片', answer)

    def test_feedback_natural_language_effect(self):
        feedback = load_module(SKILL_DIR / 'scripts' / 'apply_feedback.py', 'apply_feedback_mod')
        feedback.record_feedback({'input_payload': {'dish_name': '西兰花炒鸡胸肉'}, 'normalized_dish': '西兰花炒鸡胸肉', 'feedback_type': 'reject'})
        answer = CHAT.answer_user_query({'user_query': '西兰花炒鸡胸肉适合高蛋白吗？'})
        self.assertTrue('不太喜欢' in answer or '没有把它按最高优先级推荐' in answer or '谨慎' in answer)

    def test_multi_turn_user_feedback_is_reflected_in_answer(self):
        feedback = load_module(SKILL_DIR / 'scripts' / 'apply_feedback.py', 'apply_feedback_multiturn')
        feedback.record_feedback({
            'input_payload': {'dish_name': '西兰花炒鸡胸肉'},
            'normalized_dish': '西兰花炒鸡胸肉',
            'feedback_type': 'reject',
            'user_id': 'alice',
            'context_tags': ['高蛋白'],
        })
        feedback.record_feedback({
            'input_payload': {'dish_name': '西兰花炒鸡胸肉'},
            'normalized_dish': '西兰花炒鸡胸肉',
            'feedback_type': 'favorite',
            'user_id': 'alice',
            'context_tags': ['训练餐'],
        })
        answer = CHAT.answer_user_query({'user_query': '西兰花炒鸡胸肉适合高蛋白吗？', 'user_id': 'alice'})
        self.assertIn('个人反馈', answer)
        self.assertTrue('训练餐' in answer or '高蛋白' in answer)

    def test_nutrition_cn_output(self):
        answer = CHAT.answer_user_query({'user_query': '红烧肉大概营养怎么样？我在控糖。'})
        self.assertIn('热量约', answer)
        self.assertIn('蛋白质约', answer)
        self.assertIn('控糖', answer)


if __name__ == '__main__':
    unittest.main()
