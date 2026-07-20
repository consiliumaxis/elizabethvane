import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from bot_funnel import (
    CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    CHANNEL_SUBSCRIBE_EVENT,
    DEFAULT_CHANNEL_ID,
    DEFAULT_CHANNEL_URL,
    QUIZ_COMPLETE_EVENT,
    get_aio_question_field,
    get_quiz_options,
    get_quiz_question,
    get_quiz_steps_to_complete,
    is_active_channel_member,
    is_skip_answer,
    is_valid_quiz_step,
    map_quiz_answer_locally,
    normalize_channel_settings,
    normalize_quiz_answer,
    normalize_quiz_config,
)


class BotFunnelTest(unittest.TestCase):
    def test_quiz_config_can_override_questions_and_options(self):
        config = normalize_quiz_config(
            {
                "experience": {
                    "question": "Custom question?",
                    "options": ["One", "Two", "Two", ""],
                }
            }
        )

        self.assertEqual(get_quiz_question("experience", config), "Custom question?")
        self.assertEqual(get_quiz_options("experience", config), ("One", "Two"))
        self.assertEqual(get_quiz_question("capital", config), get_quiz_question("capital"))

    def test_maps_steps_to_aio_question_fields(self):
        self.assertEqual(get_aio_question_field("experience"), "tg_question1")
        self.assertEqual(get_aio_question_field("broker_experience"), "tg_question2")
        self.assertEqual(get_aio_question_field("capital"), "tg_question3")

    def test_skip_completes_current_and_remaining_quiz_steps(self):
        self.assertEqual(
            get_quiz_steps_to_complete("experience", skip_flow=True),
            ("experience", "broker_experience", "capital"),
        )
        self.assertEqual(get_quiz_steps_to_complete("capital", skip_flow=True), ("capital",))

    def test_normalizes_quiz_answers_and_free_text(self):
        self.assertEqual(normalize_quiz_answer("experience", "  Less than 1 year  "), "Less than 1 year")
        self.assertEqual(map_quiz_answer_locally("experience", "I am a total beginner"), "I have no experience")
        self.assertEqual(map_quiz_answer_locally("capital", "500 dollars"), "$100-$1,000")
        self.assertTrue(is_skip_answer("just send the link"))
        self.assertTrue(is_valid_quiz_step("capital"))
        self.assertFalse(is_valid_quiz_step("bad_step"))

    def test_normalizes_channel_settings(self):
        defaults = normalize_channel_settings({})
        self.assertEqual(defaults["channel_id"], DEFAULT_CHANNEL_ID)
        self.assertEqual(defaults["channel_url"], DEFAULT_CHANNEL_URL)
        self.assertEqual(defaults["check_subscription_enabled"], 1)

        custom = normalize_channel_settings(
            {
                "channel_id": "-1001",
                "channel_url": " @test_channel ",
                "check_subscription_enabled": "0",
                "support_url": " t.me/support ",
            }
        )
        self.assertEqual(custom["channel_id"], -1001)
        self.assertEqual(custom["channel_url"], "https://t.me/test_channel")
        self.assertEqual(custom["check_subscription_enabled"], 0)
        self.assertEqual(custom["support_url"], "https://t.me/support")

    def test_detects_active_channel_memberships_and_events(self):
        for status in ("member", "administrator", "creator"):
            self.assertTrue(is_active_channel_member(status))
        for status in ("left", "kicked", "", None):
            self.assertFalse(is_active_channel_member(status))

        self.assertEqual(QUIZ_COMPLETE_EVENT, "quiz_complete")
        self.assertEqual(CHANNEL_SUBSCRIBE_EVENT, "channel_subscribe")
        self.assertEqual(CHATTERFY_CHANNEL_SUBSCRIBE_EVENT, CHANNEL_SUBSCRIBE_EVENT)

    def test_start_flow_sends_video_note_before_first_quiz_question(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn("START_VIDEO_NOTE_PATH", source)
        self.assertIn("send_start_video_note", source)
        self.assertIn("send_video_note", source)
        self.assertIn("FSInputFile", source)
        self.assertIn("await send_start_video_note(message.chat.id)", source)
        self.assertLess(
            source.index("await send_start_video_note(message.chat.id)"),
            source.index("await send_quiz_welcome(message.chat.id)"),
        )
        self.assertTrue((PROJECT_ROOT / "backend" / "assets" / "elizabeth_start_video_note.mp4").exists())

    def test_go_to_trading_starts_the_ai_circle_funnel(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn("async def start_ai_chatter_from_callback", source)
        self.assertIn('"is_start": True', source)
        callback_handler = source.split("async def handle_funnel_continue", 1)[1].split(
            "@dp.callback_query", 1
        )[0]
        self.assertIn("await send_main_menu", callback_handler)
        self.assertIn("await start_ai_chatter_from_callback(callback)", callback_handler)

    def test_subscription_confirmation_sends_event_before_trading(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn('text="I’ve subscribed — go to trading"', source)
        self.assertIn("callback_data=FUNNEL_CHECK_CHANNEL_CALLBACK", source)
        subscription_handler = source.split("async def handle_funnel_check_channel", 1)[1].split(
            "class AIChatRequest", 1
        )[0]
        self.assertIn("channel_subscribed_at = COALESCE(channel_subscribed_at, NOW())", subscription_handler)
        self.assertIn("await send_aio_postback_event(user_id, CHANNEL_SUBSCRIBE_EVENT)", subscription_handler)
        self.assertLess(
            subscription_handler.index("await send_aio_postback_event"),
            subscription_handler.index("await handle_funnel_continue"),
        )

    def test_aio_funnel_events_are_deduplicated_per_telegram_user(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn('default_unique_key = f"{normalized_event_slug}:{user_id}"', source)
        self.assertIn("unique_key=normalized_unique_key", source)


if __name__ == "__main__":
    unittest.main()
