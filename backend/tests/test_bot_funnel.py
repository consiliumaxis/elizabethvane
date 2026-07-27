import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

from bot_funnel import (
    CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    CHANNEL_SUBSCRIBE_EVENT,
    DEFAULT_CHANNEL_ID,
    DEFAULT_CHANNEL_URL,
    DEFAULT_FINAL_MESSAGE_CONFIG,
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
    normalize_final_message_config,
    normalize_quiz_answer,
    normalize_quiz_config,
    validate_final_message_config,
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

    def test_final_message_config_preserves_button_order_and_types(self):
        config = validate_final_message_config(
            {
                "enabled": True,
                "trigger_button_text": "Continue",
                "message_text": "Choose the next step",
                "buttons": [
                    {
                        "id": "register",
                        "type": "url",
                        "text": "Register",
                        "url": "t.me/example",
                    },
                    {
                        "id": "menu",
                        "type": "menu",
                        "text": "Open menu",
                    },
                    {
                        "id": "app",
                        "type": "web_app",
                        "text": "Open app",
                    },
                ],
            }
        )

        self.assertEqual(config["trigger_button_text"], "Continue")
        self.assertEqual([button["id"] for button in config["buttons"]], ["register", "menu", "app"])
        self.assertEqual(config["buttons"][0]["url"], "https://t.me/example")
        self.assertEqual(config["buttons"][1]["type"], "menu")
        self.assertEqual(config["buttons"][2]["type"], "web_app")

    def test_final_message_config_rejects_unsafe_or_ambiguous_buttons(self):
        with self.assertRaisesRegex(ValueError, "полную HTTP"):
            validate_final_message_config(
                {
                    "enabled": True,
                    "trigger_button_text": "Continue",
                    "message_text": "Done",
                    "buttons": [{"type": "url", "text": "Bad", "url": "javascript:alert(1)"}],
                }
            )
        with self.assertRaisesRegex(ValueError, "только одну"):
            validate_final_message_config(
                {
                    "enabled": True,
                    "trigger_button_text": "Continue",
                    "message_text": "Done",
                    "buttons": [
                        {"type": "menu", "text": "App 1"},
                        {"type": "menu", "text": "App 2"},
                    ],
                }
            )
        with self.assertRaisesRegex(ValueError, "мини-приложения"):
            validate_final_message_config(
                {
                    "enabled": True,
                    "trigger_button_text": "Continue",
                    "message_text": "Done",
                    "buttons": [
                        {"type": "web_app", "text": "App 1"},
                        {"type": "web_app", "text": "App 2"},
                    ],
                }
            )

    def test_final_message_config_has_backward_compatible_default(self):
        config = normalize_final_message_config(None)

        self.assertEqual(config["message_text"], DEFAULT_FINAL_MESSAGE_CONFIG["message_text"])
        self.assertEqual(config["buttons"][0]["type"], "menu")

    def test_detects_active_channel_memberships_and_events(self):
        for status in ("member", "administrator", "creator"):
            self.assertTrue(is_active_channel_member(status))
        self.assertTrue(is_active_channel_member("restricted", is_member=True))
        self.assertFalse(is_active_channel_member("restricted", is_member=False))
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

    def test_go_to_trading_shows_configured_final_message_with_menu_fallback(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        callback_handler = source.split("async def handle_funnel_continue", 1)[1].split(
            "@dp.callback_query", 1
        )[0]
        self.assertIn("row = await get_onboarding_row(user_id)", callback_handler)
        self.assertIn("await is_user_channel_member", callback_handler)
        self.assertIn("await complete_channel_subscription", callback_handler)
        self.assertIn("await show_funnel_final_message(callback)", callback_handler)
        self.assertIn("await send_main_menu", callback_handler)
        self.assertNotIn("await start_ai_chatter_from_callback(callback)", callback_handler)

        self.assertIn("def build_funnel_final_keyboard", source)
        self.assertIn('callback_data=FUNNEL_OPEN_MENU_CALLBACK', source)
        self.assertIn('web_app=WebAppInfo(url=web_app_url)', source)
        self.assertIn("await callback.message.edit_text", source)
        self.assertIn("async def handle_funnel_open_menu", source)
        self.assertIn("await send_main_menu(callback.message.chat.id", source)

    def test_quiz_callback_acknowledges_choice_before_sending_next_step(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        handler = source.split("async def handle_quiz_answer_callback", 1)[1].split(
            "@dp.callback_query", 1
        )[0]
        self.assertIn('await callback.answer("Saved")', handler)
        self.assertIn("await callback.message.edit_reply_markup(reply_markup=None)", handler)

        saver = source.split("async def save_quiz_answer", 1)[1].split(
            "async def finish_quiz_and_show_channel", 1
        )[0]
        self.assertIn("asyncio.create_task(deliver_quiz_aio_fields", saver)
        self.assertIn("async def deliver_quiz_aio_fields", saver)

    def test_bot_ai_manager_can_be_disabled_per_runtime(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn('os.getenv("BOT_AI_MANAGER_ENABLED")', source)
        gateway = source.split("async def post_to_ai_chatter", 1)[1].split(
            "async def forward_message_to_ai_chatter", 1
        )[0]
        self.assertIn("not BOT_AI_MANAGER_ENABLED", gateway)

    def test_open_channel_redirect_sends_subscription_event_and_starts_ai(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn('channel_button_url = build_channel_click_url', source)
        self.assertIn('InlineKeyboardButton(text="Open channel", url=channel_button_url)', source)
        self.assertIn('@app.get("/api/bot/channel/open")', source)
        self.assertIn("build_channel_click_signature", source)
        click_handler = source.split("async def process_channel_open_click", 1)[1].split(
            '@app.get("/api/bot/channel/open")', 1
        )[0]
        self.assertIn("channel_subscribed_at = NOW()", click_handler)
        self.assertIn("await send_aio_postback_event(user_id, CHANNEL_SUBSCRIBE_EVENT)", click_handler)
        self.assertIn("await post_to_ai_chatter", click_handler)
        self.assertLess(
            click_handler.index("await send_aio_postback_event"),
            click_handler.index("await post_to_ai_chatter"),
        )

    def test_telegram_join_request_mode_approves_before_starting_ai(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn("creates_join_request=True", source)
        self.assertIn("@dp.chat_join_request()", source)
        handler = source.split("async def handle_channel_join_request", 1)[1].split(
            "async def map_quiz_answer_with_ai", 1
        )[0]
        self.assertIn("await bot.approve_chat_join_request", handler)
        self.assertIn("await complete_channel_subscription", handler)
        self.assertLess(
            handler.index("await bot.approve_chat_join_request"),
            handler.index("await complete_channel_subscription"),
        )

    def test_confirmed_subscription_immediately_unlocks_ai_messages(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        confirmation = source.split("async def complete_channel_subscription", 1)[1].split(
            '@app.get("/api/bot/channel/open")', 1
        )[0]
        self.assertIn("channel_gate_completed_at = COALESCE(channel_gate_completed_at, NOW())", confirmation)

        message_handler = source.split("async def handle_onboarding_answer", 1)[1].split(
            "@dp.callback_query", 1
        )[0]
        self.assertIn('if row.get("channel_subscribed_at"):', message_handler)
        self.assertIn("await forward_message_to_ai_chatter(message)", message_handler)

    def test_aio_funnel_events_are_deduplicated_per_telegram_user(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        self.assertIn('default_unique_key = f"{normalized_event_slug}:{user_id}"', source)
        self.assertIn("unique_key=normalized_unique_key", source)


if __name__ == "__main__":
    unittest.main()
