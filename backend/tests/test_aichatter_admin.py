import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AichatterAdminTest(unittest.TestCase):
    def test_router_exposes_complete_admin_surface(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        for route in (
            '@router.get("/overview")',
            '@router.put("/settings")',
            '@router.get("/users")',
            '@router.get("/users/{telegram_id}/messages")',
            '@router.delete("/users/{telegram_id}/messages")',
            '@router.patch("/users/{telegram_id}")',
            '@router.put("/triggers")',
            '@router.post("/admins")',
            '@router.get("/postbacks")',
            '@router.get("/statistics")',
            '@router.put("/statistics/manual-commission")',
            '@router.get("/funnel")',
            '@router.put("/funnel")',
            '@router.put("/funnel/{media_key}/media")',
        ):
            self.assertIn(route, source)
        self.assertIn('prefix="/api/admin/aichatter"', source)
        self.assertIn("Depends(admin_dependency)", source)

    def test_clear_history_removes_messages_and_ai_memory(self):
        backend = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")
        frontend = (PROJECT_ROOT / "frontend/src/admin/pages/AIChatterPage.jsx").read_text(encoding="utf-8")

        self.assertIn("DELETE FROM messages WHERE tg_user_id", backend)
        self.assertIn("DELETE FROM conversation_memory WHERE tg_user_id", backend)
        self.assertIn("window.confirm", frontend)
        self.assertIn("Очистить историю", frontend)

    def test_database_config_is_isolated_from_elizabeth_database(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        for variable in (
            "AICHAT_DB_HOST",
            "AICHAT_DB_PORT",
            "AICHAT_DB_NAME",
            "AICHAT_DB_USER",
            "AICHAT_DB_PASSWORD",
        ):
            self.assertIn(variable, source)

    def test_trigger_normalization_removes_blanks_and_duplicates(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        self.assertIn("def _split_phrases", source)
        self.assertIn("item.split()", source)
        self.assertIn("phrase.casefold()", source)

    def test_bot_refreshes_database_settings_at_runtime(self):
        source = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")

        self.assertIn("runtime_settings_refresh_worker", source)
        self.assertIn("asyncio.create_task(runtime_settings_refresh_worker())", source)
        self.assertIn("SELECT work_start, work_end, is_enabled FROM settings", source)
        self.assertIn("SELECT system_prompt, enabled, model, openai_api_key FROM ai_settings", source)

    def test_admin_uses_a_model_picker(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/AIChatterPage.jsx").read_text(encoding="utf-8")

        self.assertIn("AI_MODEL_OPTIONS", source)
        self.assertIn("gpt-4.1-mini", source)
        self.assertIn("gpt-4.1-nano", source)
        self.assertIn("gpt-5.6-sol", source)
        self.assertIn("gpt-5.6-terra", source)
        self.assertIn("gpt-5.6-luna", source)
        self.assertIn("<label>Модель OpenAI<select", source)

    def test_openai_key_is_managed_without_returning_the_secret(self):
        backend = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")
        frontend = (PROJECT_ROOT / "frontend/src/admin/pages/AIChatterPage.jsx").read_text(encoding="utf-8")
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")

        self.assertIn("openai_api_key: Optional[str]", backend)
        self.assertIn('"openai_api_key": ""', backend)
        self.assertIn('"openai_key_configured"', backend)
        self.assertIn('type="password"', frontend)
        self.assertIn("OpenAI client reconfigured from admin settings", bot)

    def test_funnel_media_uses_video_notes_in_both_delivery_modes_and_prevents_repeats(self):
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")
        db = (PROJECT_ROOT / "services/evanechat_bot/db.py").read_text(encoding="utf-8")

        self.assertIn("split_funnel_reply", bot)
        self.assertIn("send_ai_reply_with_funnel_media", bot)
        self.assertIn("get_funnel_routing_prompt", bot)
        self.assertIn("ORDER BY sort_order, id", bot)
        self.assertIn("bot.send_video_note", bot)
        self.assertIn("business_connection_kwargs(business_id)", bot)
        self.assertIn("prepare_square_video_note", bot)
        self.assertIn('"-c:v", "libx264"', bot)
        self.assertIn('"-t", "59"', bot)
        self.assertIn("funnel_media_sent", bot)
        self.assertIn("CREATE TABLE IF NOT EXISTS funnel_media", db)
        self.assertIn("CREATE TABLE IF NOT EXISTS funnel_media_sent", db)

    def test_direct_bot_messages_use_the_shared_ai_funnel(self):
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")
        context = (PROJECT_ROOT / "services/evanechat_bot/service/telegram_context.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('@router.message(Command("start"), F.chat.type == "private")', bot)
        self.assertIn('@router.message(F.voice, F.chat.type == "private")', bot)
        self.assertIn('@router.message(F.text, ~F.text.startswith("/"), F.chat.type == "private")', bot)
        self.assertGreaterEqual(bot.count("send_business_ai_reply(msg.chat.id, None"), 3)
        self.assertIn('return {"business_connection_id": business_id} if business_id else {}', context)
        self.assertLess(bot.index("dp.include_router(admin_router)"), bot.index("dp.include_router(router)"))

    def test_main_elizabeth_bot_uses_the_internal_ai_gateway(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")
        db = (PROJECT_ROOT / "services/evanechat_bot/db.py").read_text(encoding="utf-8")

        self.assertIn("forward_message_to_ai_chatter", backend)
        self.assertIn('headers={"X-AI-Chatter-Secret": AI_CHATTER_GATEWAY_SECRET}', backend)
        self.assertIn('text_override="Hello", is_start=True', backend)
        self.assertIn('gateway_app.router.add_post("/incoming", incoming)', bot)
        self.assertIn('delivery_scope = "elizabeth_bot"', bot)
        self.assertIn("send_intro_funnel_media_if_needed", bot)
        self.assertIn("delivery_scope VARCHAR(32) NOT NULL", db)
        gateway_handler = bot.split("async def process_gateway_message", 1)[1].split(
            "def gateway_task_done", 1
        )[0]
        self.assertNotIn("is_bot_active_now()", gateway_handler)

    def test_business_messages_are_marked_read(self):
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")

        self.assertIn("class ReadBusinessMessage", bot)
        self.assertIn('__api_method__ = "readBusinessMessage"', bot)
        self.assertIn("await mark_business_message_read(msg, bot)", bot)

    def test_cold_stage_has_deterministic_media_fallback(self):
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")

        self.assertIn("get_next_unsent_funnel_media_key", bot)
        self.assertIn('get_next_unsent_funnel_media_key(tg_user_id, "A", delivery_scope)', bot)
        self.assertIn("inserted required cold-stage media", bot)

    def test_ai_reply_is_forced_to_english(self):
        bot = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")

        self.assertIn("FINAL OUTPUT LANGUAGE RULE", bot)
        self.assertIn("ensure_english_reply", bot)
        self.assertIn("translated non-English AI reply to English", bot)

    def test_funnel_default_order_is_semantic_not_alphabetical(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")
        expected = [
            '"a1"', '"a5"', '"w1"', '"w2"', '"w2.5"', '"w2.6"', '"w3"',
            '"w6"', '"e1"', '"e5"', '"e5.2"', '"e5.3"', '"e5.4"',
            '"r1"', '"r3"', '"r3.2"', '"r4"', '"r6"', '"c1"', '"c4"', '"c6"',
        ]
        positions = [source.index(value) for value in expected]
        self.assertEqual(positions, sorted(positions))

    def test_admin_contains_funnel_management_section(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/AIChatterPage.jsx").read_text(encoding="utf-8")

        self.assertIn("{ id: 'funnel', label: 'Воронка' }", source)
        self.assertIn("saveFunnel", source)
        self.assertIn("uploadFunnelMedia", source)
        self.assertIn("Кружки и порядок", source)


if __name__ == "__main__":
    unittest.main()
