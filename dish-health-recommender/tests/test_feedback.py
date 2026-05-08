import json
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
STORE_PATH = SKILL_DIR / 'data' / 'feedback.json'
sys.path.insert(0, str(SKILL_DIR))

from scripts import apply_feedback as FEEDBACK  # noqa: E402
import scripts.recommend as RECOMMEND  # noqa: E402


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        STORE_PATH.write_text(json.dumps({'events': [], 'bias': {}, 'corrections': {}}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_feedback_file_exists(self):
        self.assertTrue(STORE_PATH.exists())

    def test_accept_reject_favorite_and_correction_recording(self):
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄炒蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'accept'})
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄炒蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'reject'})
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄炒蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'favorite'})
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄鸡蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'correct_dish_name', 'corrected_dish_name': '番茄炒蛋'})
        summary = FEEDBACK.summarize_bias()
        self.assertEqual(summary['bias']['番茄炒蛋']['accepts'], 1)
        self.assertEqual(summary['bias']['番茄炒蛋']['rejects'], 1)
        self.assertEqual(summary['bias']['番茄炒蛋']['favorites'], 1)
        self.assertEqual(summary['corrections']['番茄鸡蛋'], '番茄炒蛋')

    def test_favorite_boosts_confidence(self):
        base = RECOMMEND.recommend({'dish_name': '番茄炒蛋'})
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄炒蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'favorite'})
        boosted = RECOMMEND.recommend({'dish_name': '番茄炒蛋'})
        self.assertGreaterEqual(boosted['confidence'], base['confidence'])

    def test_reject_downgrades_recommendation(self):
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '西兰花炒鸡胸肉'}, 'normalized_dish': '西兰花炒鸡胸肉', 'feedback_type': 'reject'})
        result = RECOMMEND.recommend({'dish_name': '西兰花炒鸡胸肉', 'user_profile': {'goals': ['高蛋白']}})
        self.assertIn(result['recommendation'], {'caution', 'avoid'})

    def test_correct_dish_name_affects_next_lookup(self):
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄鸡蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'correct_dish_name', 'corrected_dish_name': '番茄炒蛋'})
        result = RECOMMEND.recommend({'dish_name': '番茄鸡蛋'})
        self.assertEqual('番茄炒蛋', result['normalized_dish'])


if __name__ == '__main__':
    unittest.main()
