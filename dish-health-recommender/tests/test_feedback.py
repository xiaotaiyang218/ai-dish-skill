import json
import sys
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
STORE_PATH = SKILL_DIR / 'data' / 'feedback.json'
sys.path.insert(0, str(SKILL_DIR))

from scripts import apply_feedback as FEEDBACK  # noqa: E402
import scripts.recommend as RECOMMEND  # noqa: E402


def empty_store() -> dict:
    return {
        'input_events': [],
        'events': [],
        'profiles': {'dish': {}, 'user_dish': {}},
        'user_profiles': {},
        'corrections': {},
        'meta': {'last_feedback_at': ''},
    }


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        STORE_PATH.write_text(json.dumps(empty_store(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_feedback_file_exists(self):
        self.assertTrue(STORE_PATH.exists())

    def test_load_store_recovers_from_invalid_json(self):
        STORE_PATH.write_text('', encoding='utf-8')
        store = FEEDBACK.load_store()
        self.assertEqual(empty_store(), store)

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
        self.assertIn('番茄炒蛋', summary['profiles']['dish'])

    def test_user_id_context_tags_and_last_feedback_at_are_persisted(self):
        timestamp = str(int(time.time()))
        event = FEEDBACK.record_feedback({
            'input_payload': {'dish_name': '西兰花炒鸡胸肉'},
            'normalized_dish': '西兰花炒鸡胸肉',
            'feedback_type': 'favorite',
            'user_id': 'alice',
            'context_tags': ['减脂', '午餐'],
            'timestamp': timestamp,
        })
        self.assertEqual('alice', event['user_id'])
        self.assertEqual(['减脂', '午餐'], event['context_tags'])
        store = FEEDBACK.load_store()
        profile = store['profiles']['user_dish']['alice::西兰花炒鸡胸肉']
        self.assertEqual(timestamp, profile['last_feedback_at'])
        self.assertIn('减脂', profile['context_tags'])
        self.assertEqual(timestamp, store['meta']['last_feedback_at'])

    def test_replay_profiles_applies_decay_window(self):
        now = int(time.time())
        old_ts = str(now - 45 * 24 * 3600)
        recent_ts = str(now - 2 * 24 * 3600)
        FEEDBACK.record_feedback({
            'input_payload': {'dish_name': '番茄炒蛋'},
            'normalized_dish': '番茄炒蛋',
            'feedback_type': 'reject',
            'user_id': 'alice',
            'timestamp': old_ts,
        })
        FEEDBACK.record_feedback({
            'input_payload': {'dish_name': '番茄炒蛋'},
            'normalized_dish': '番茄炒蛋',
            'feedback_type': 'favorite',
            'user_id': 'alice',
            'context_tags': ['减脂'],
            'timestamp': recent_ts,
        })
        replay = FEEDBACK.replay_feedback_profiles({
            'storePath': str(STORE_PATH),
            'profileMode': 'user_dish',
            'decayWindowDays': 30,
        })
        self.assertEqual(1, replay['profileCount'])
        replay_payload = json.loads(Path(replay['outputPath']).read_text(encoding='utf-8'))
        profile = replay_payload['profiles']['alice::番茄炒蛋']
        self.assertEqual(0, profile['rejects'])
        self.assertEqual(1, profile['favorites'])
        self.assertIn('减脂', profile['context_tags'])

    def test_favorite_boosts_confidence(self):
        base = RECOMMEND.recommend({'dish_name': '番茄炒蛋'})
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄炒蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'favorite'})
        boosted = RECOMMEND.recommend({'dish_name': '番茄炒蛋'})
        self.assertGreaterEqual(boosted['confidence'], base['confidence'])
        self.assertIn('历史收藏 1 次', boosted['explanation'])

    def test_accept_boosts_confidence_and_explanation(self):
        base = RECOMMEND.recommend({'dish_name': '西兰花炒鸡胸肉'})
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '西兰花炒鸡胸肉'}, 'normalized_dish': '西兰花炒鸡胸肉', 'feedback_type': 'accept'})
        boosted = RECOMMEND.recommend({'dish_name': '西兰花炒鸡胸肉'})
        self.assertGreaterEqual(boosted['confidence'], base['confidence'])
        self.assertIn('历史接受 1 次', boosted['explanation'])

    def test_reject_downgrades_recommendation(self):
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '西兰花炒鸡胸肉'}, 'normalized_dish': '西兰花炒鸡胸肉', 'feedback_type': 'reject'})
        result = RECOMMEND.recommend({'dish_name': '西兰花炒鸡胸肉', 'user_profile': {'goals': ['高蛋白']}})
        self.assertIn(result['recommendation'], {'caution', 'avoid'})
        self.assertIn('历史拒绝 1 次', result['explanation'])
        self.assertIn('近期反馈偏好', result['need_confirm'])
        self.assertTrue(result['explanation'].startswith('结论：谨慎。依据：') or result['explanation'].startswith('结论：不推荐。依据：'))

    def test_user_specific_profile_changes_recommendation_and_mentions_source(self):
        FEEDBACK.record_feedback({
            'input_payload': {'dish_name': '西兰花炒鸡胸肉'},
            'normalized_dish': '西兰花炒鸡胸肉',
            'feedback_type': 'reject',
            'user_id': 'alice',
            'context_tags': ['高蛋白'],
        })
        FEEDBACK.record_feedback({
            'input_payload': {'dish_name': '西兰花炒鸡胸肉'},
            'normalized_dish': '西兰花炒鸡胸肉',
            'feedback_type': 'reject',
            'user_id': 'alice',
            'context_tags': ['晚餐'],
        })
        alice = RECOMMEND.recommend({'dish_name': '西兰花炒鸡胸肉', 'user_id': 'alice', 'user_profile': {'goals': ['高蛋白']}})
        bob = RECOMMEND.recommend({'dish_name': '西兰花炒鸡胸肉', 'user_id': 'bob', 'user_profile': {'goals': ['高蛋白']}})
        self.assertIn(alice['recommendation'], {'caution', 'avoid'})
        self.assertIn('个人反馈', alice['explanation'])
        self.assertNotIn('个人反馈', bob['explanation'])

    def test_correct_dish_name_affects_next_lookup(self):
        FEEDBACK.record_feedback({'input_payload': {'dish_name': '番茄鸡蛋'}, 'normalized_dish': '番茄炒蛋', 'feedback_type': 'correct_dish_name', 'corrected_dish_name': '番茄炒蛋'})
        result = RECOMMEND.recommend({'dish_name': '番茄鸡蛋'})
        self.assertEqual('番茄炒蛋', result['normalized_dish'])

    def test_recommendation_input_is_recorded_locally(self):
        result = RECOMMEND.recommend({
            'dish_name': '西兰花炒鸡胸肉',
            'user_id': 'alice',
            'user_profile': {'goals': ['减脂']},
            'context_tags': ['午餐'],
        })
        store = FEEDBACK.load_store()
        event = store['input_events'][-1]

        self.assertEqual('recommendation_input', event['event_type'])
        self.assertEqual('alice', event['user_id'])
        self.assertEqual('西兰花炒鸡胸肉', event['input_payload']['dish_name'])
        self.assertEqual('西兰花炒鸡胸肉', event['normalized_dish'])
        self.assertEqual(result['recommendation'], event['recommendation'])
        self.assertIn('午餐', event['context_tags'])

    def test_recommendation_result_distinguishes_analysis_input_from_feedback(self):
        result = RECOMMEND.recommend({'dish_name': '番茄炒蛋', 'user_id': 'alice'})

        self.assertTrue(result['execution_status']['skill_executed'])
        self.assertEqual('scripts/recommend.py', result['execution_status']['engine'])
        self.assertTrue(result['feedback_status']['analysis_input_recorded'])
        self.assertFalse(result['feedback_status']['preference_feedback_recorded'])
        self.assertTrue(result['feedback_status']['requires_user_confirmation'])
        self.assertIn('accept', result['feedback_status']['supported_feedback_types'])
        self.assertIn('correct_dish_name', result['feedback_status']['supported_feedback_types'])

    def test_explicit_feedback_event_marks_preference_feedback_recorded(self):
        event = FEEDBACK.record_feedback({
            'input_payload': {'dish_name': '番茄鸡蛋'},
            'normalized_dish': '番茄炒蛋',
            'feedback_type': 'correct_dish_name',
            'corrected_dish_name': '番茄炒蛋',
            'user_id': 'alice',
        })

        self.assertTrue(event['feedback_status']['preference_feedback_recorded'])
        self.assertFalse(event['feedback_status']['requires_user_confirmation'])
        self.assertEqual('correct_dish_name', event['feedback_status']['recorded_feedback_type'])

    def test_user_profile_separates_persistent_constraints_from_temporary_goals(self):
        event = FEEDBACK.record_user_profile({
            'user_id': 'alice',
            'persistent_constraints': {
                'allergies': ['海鲜', '海鲜'],
                'conditions': ['高血压'],
            },
            'temporary_goals': {
                'goals': ['减脂'],
                'conditions': ['低盐'],
            },
        })

        store = FEEDBACK.load_store()
        profile = store['user_profiles']['alice']
        self.assertEqual(['海鲜'], profile['persistent_constraints']['allergies'])
        self.assertEqual(['高血压'], profile['persistent_constraints']['conditions'])
        self.assertEqual(['减脂'], profile['temporary_goals']['goals'])
        self.assertEqual(['低盐'], profile['temporary_goals']['conditions'])
        self.assertTrue(event['feedback_status']['preference_feedback_recorded'])
        self.assertEqual('set_user_profile', event['feedback_status']['recorded_feedback_type'])

    def test_stored_user_profile_is_applied_to_recommendation(self):
        FEEDBACK.record_user_profile({
            'user_id': 'alice',
            'persistent_constraints': {'allergies': ['海鲜']},
            'temporary_goals': {'goals': ['减脂'], 'conditions': ['低盐']},
        })

        result = RECOMMEND.recommend({
            'dish_name': '油爆虾',
            'user_id': 'alice',
            'output_mode': 'human_readable_cn',
        })

        self.assertEqual('avoid', result['recommendation'])
        self.assertIn('海鲜', result['applied_user_profile']['persistent_constraints']['allergies'])
        self.assertIn('减脂', result['applied_user_profile']['temporary_goals']['goals'])
        self.assertIn('用户画像', result['explanation'])
        self.assertIn('海鲜/鱼类相关限制', result['explanation'])
        self.assertIn('用户画像', result['human_readable_cn'])


if __name__ == '__main__':
    unittest.main()
