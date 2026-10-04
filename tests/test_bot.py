"""Unit test suite for Milestone 4: Telegram Bot Core & Interactive Inline Actions.

Validates security whitelist authorization, command handlers, inline action state transitions,
snooze limit enforcement, skip justification evaluation, reactive coaching chat,
proactive push reminders, and application lifecycle.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict
import pytest
from zoneinfo import ZoneInfo

from src.config import AppConfig
from src.storage import AtomicJsonStore, SessionStatus, StreakData
from src.bot import BotApplication, build_application, make_inline_action_keyboard
from src.main import create_system, run_async, format_proactive_message
from tests.mock_services import (
    MockTelegramBot,
    MockGeminiClient,
    make_text_update,
    make_callback_update,
)


class TestBotSecurityWhitelist:
    """Feature 1 & 36: Security whitelist authorization gate tests."""

    @pytest.mark.asyncio
    async def test_whitelist_authorized_chat_accepted(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Authorized user message is processed successfully."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/start")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Chào mừng" in resp["text"] or "Kỷ Luật" in resp["text"]

    @pytest.mark.asyncio
    async def test_whitelist_unauthorized_chat_rejected_without_coach_call(
        self, bot_application: Any, app_config: AppConfig, coach_service: Any
    ) -> None:
        """Unauthorized message is rejected without invoking AI coach or altering data."""
        bad_id = 999888777
        assert bad_id != app_config.allowed_chat_id

        update = make_text_update(chat_id=bad_id, text="Tôi muốn bỏ phiên tập hôm nay.")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert any(kw in resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])

    @pytest.mark.asyncio
    async def test_whitelist_unauthorized_callback_rejected(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Unauthorized callback click is rejected with alert; state remains untouched."""
        bad_id = 111222333
        update = make_callback_update(
            chat_id=bad_id,
            callback_data="done:unauthorized_sess",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert any(kw in resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])

        # Confirm storage wasn't altered
        status = await atomic_store.get_session_status("unauthorized_sess")
        assert status is None

    @pytest.mark.asyncio
    async def test_whitelist_boundary_chat_ids(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Boundary and adversarial chat IDs are strictly rejected."""
        adversarial_ids = [
            0,
            -1,
            -1001234567890,
            app_config.allowed_chat_id + 1,
            app_config.allowed_chat_id - 1,
            999999999999,
        ]
        for bad_id in adversarial_ids:
            update = make_text_update(chat_id=bad_id, text="/start", bot=bot_application.bot)
            resp = await bot_application.process_update(update)
            assert resp is not None
            assert any(kw in resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])


class TestBotCommandHandlers:
    """Features 4, 5, 6: Command handlers (/start, /help, /status)."""

    @pytest.mark.asyncio
    async def test_start_command_greeting_and_commands(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 4: /start greets authorized user and lists commands."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/start")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "/status" in resp["text"]
        assert "/help" in resp["text"]

    @pytest.mark.asyncio
    async def test_help_command_explains_mechanics(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 5: /help explains the 3 action buttons and snooze limits."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/help")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Đã hoàn thành" in resp["text"]
        assert "Xin lùi 15 phút" in resp["text"]
        assert "Hôm nay nghỉ" in resp["text"]

    @pytest.mark.asyncio
    async def test_status_command_zero_streak(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 6: /status on fresh data displays 0 streak."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/status")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "BÁO CÁO KỶ LUẬT" in resp["text"] or "streak" in resp["text"].lower()
        assert "0" in resp["text"]

    @pytest.mark.asyncio
    async def test_status_command_active_streak(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 6: /status reflects active streak completed today."""
        today_str = datetime.now(ZoneInfo(app_config.timezone)).strftime("%Y-%m-%d")
        await atomic_store.record_completion("s_status_active", "gym", today_str)

        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/status")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "1" in resp["text"]

    @pytest.mark.asyncio
    async def test_schedule_command_today_agenda(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature: /schedule returns full daily schedule and countdown."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/schedule")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "LỊCH TRÌNH HÔM NAY" in resp["text"]
        assert "TOEIC" in resp["text"]
        assert "Major" in resp["text"] or "Chuyên ngành" in resp["text"]
        assert "Phiên tiếp theo" in resp["text"]


class TestBotCallbackDone:
    """Feature 14: Done button completion workflow."""

    @pytest.mark.asyncio
    async def test_done_callback_records_completion(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Done callback increments streak and updates storage."""
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data="done:gym_done_test",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "HOÀN THÀNH" in resp["text"] or "kỷ luật" in resp["text"].lower()

        streak = await atomic_store.get_streak()
        assert streak.current_streak >= 1

    @pytest.mark.asyncio
    async def test_done_callback_idempotent_duplicate_click(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Clicking Done repeatedly does not multiply streak."""
        sid = "gym_double_click"
        for _ in range(3):
            update = make_callback_update(
                chat_id=app_config.allowed_chat_id,
                callback_data=f"done:{sid}",
                bot=bot_application.bot,
            )
            await bot_application.process_update(update)

        streak = await atomic_store.get_streak()
        assert streak.current_streak == 1
        assert streak.total_completions == 1

    @pytest.mark.asyncio
    async def test_done_callback_offline_coach_fallback(
        self, app_config: AppConfig, atomic_store: AtomicJsonStore, scheduler_service: Any
    ) -> None:
        """Done callback works cleanly even when coach is offline."""
        from tests.mock_services import get_ai_coach_class
        error_client = MockGeminiClient(api_key="key", error_mode="timeout")
        cls = get_ai_coach_class()
        offline_coach = cls(
            api_key="key",
            model_name="gemini-2.5-flash",
            client=error_client,
        )

        app = build_application(app_config, atomic_store, offline_coach, scheduler_service)
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data="done:fallback_done",
            bot=app.bot,
        )
        resp = await app.process_update(update)
        assert resp is not None
        assert "HOÀN THÀNH" in resp["text"]


class TestBotCallbackSnooze:
    """Features 15, 16, 17: Snooze workflow and limits."""

    @pytest.mark.asyncio
    async def test_snooze_1st_attempt(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """First snooze increments count to 1 and attaches buttons."""
        sid = "snooze_test_1"
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{sid}",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Lần 1/2" in resp["text"] or "15 PHÚT" in resp["text"]

        status = await atomic_store.get_session_status(sid)
        assert status["snooze_count"] == 1

    @pytest.mark.asyncio
    async def test_snooze_2nd_attempt(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Second snooze increments count to 2 with escalating warning."""
        sid = "snooze_test_2"
        await atomic_store.record_snooze(sid, 1)

        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{sid}",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Lần 2/2" in resp["text"]

        status = await atomic_store.get_session_status(sid)
        assert status["snooze_count"] == 2

    @pytest.mark.asyncio
    async def test_snooze_3rd_attempt_blocked(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Third snooze attempt is blocked firmly and count remains capped at 2."""
        sid = "snooze_test_3"
        await atomic_store.record_snooze(sid, 2)

        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{sid}",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "GIỚI HẠN" in resp["text"] or "HẾT QUYỀN" in resp["text"]

        status = await atomic_store.get_session_status(sid)
        assert status["snooze_count"] == 2

    @pytest.mark.asyncio
    async def test_snooze_job_callback_execution(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Scheduler snooze job callback delivers push message."""
        await bot_application._snooze_job_callback("sess_snooze_job", "gym", 1)
        assert len(bot_application.bot.sent_messages) > 0
        last_msg = bot_application.bot.sent_messages[-1]
        assert "15 PHÚT" in last_msg["text"]


class TestBotCallbackSkipAndReason:
    """Features 18, 19, 20, 21: Skip with reason state machine."""

    @pytest.mark.asyncio
    async def test_skip_callback_triggers_awaiting_reason(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Clicking skip prompts for justification and sets awaiting_reason."""
        sid = "skip_trigger_sess"
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"skip:{sid}",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "LÝ DO" in resp["text"]

        data = await atomic_store.load_data()
        assert data.get("awaiting_reason") is not None
        assert data["awaiting_reason"]["session_id"] == sid

    @pytest.mark.asyncio
    async def test_skip_reason_excuse_enforces_micro_habit(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Excuse reason triggers 2-minute micro-habit challenge."""
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": "excuse_sess", "session_type": "gym"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Hôm nay em lười quá, không muốn tập gym",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "BAO BIỆN" in resp["text"] or "MICRO-HABIT" in resp["text"] or "2 PHÚT" in resp["text"]

    @pytest.mark.asyncio
    async def test_skip_reason_legitimate_approved(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Legitimate obstacle approves skip without streak penalty."""
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": "legit_sess", "session_type": "gym"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Em bị sốt cao 39 độ phải nằm viện cấp cứu",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "CHÍNH ĐÁNG" in resp["text"] or "phục hồi" in resp["text"].lower()

        status = await atomic_store.get_session_status("legit_sess")
        assert status["status"] == SessionStatus.SKIPPED
        assert status["classification"] == "LEGITIMATE"

    @pytest.mark.asyncio
    async def test_skip_reason_empty_or_whitespace_handled_safely(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Whitespace-only justification is treated safely as excuse."""
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": "whitespace_sess", "session_type": "gym"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="   \n   \t  ",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "BAO BIỆN" in resp["text"] or "MICRO-HABIT" in resp["text"] or "2 PHÚT" in resp["text"]


class TestBotFreeFormChat:
    """Features 23, 24, 25, 26: Reactive free-form coaching chat."""

    @pytest.mark.asyncio
    async def test_free_form_chat_invokes_coach(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """User message outside reminders triggers AI coach."""
        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Coach có lời khuyên gì để tối ưu thời gian học không?",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Coach" in resp["text"]

    @pytest.mark.asyncio
    async def test_free_form_chat_context_window(
        self, bot_application: Any, app_config: AppConfig, coach_service: Any
    ) -> None:
        """Conversation history maintains sliding context window."""
        coach_service.clear_context()
        for i in range(5):
            update = make_text_update(
                chat_id=app_config.allowed_chat_id,
                text=f"Câu hỏi số {i}",
                bot=bot_application.bot,
            )
            await bot_application.process_update(update)

        assert len(coach_service.context_window) <= 10

    @pytest.mark.asyncio
    async def test_free_form_chat_offline_fallback(
        self, app_config: AppConfig, atomic_store: AtomicJsonStore, scheduler_service: Any
    ) -> None:
        """Timeout/network errors yield graceful offline coach reply."""
        from tests.mock_services import get_ai_coach_class
        error_client = MockGeminiClient(api_key="key", error_mode="timeout")
        cls = get_ai_coach_class()
        offline_coach = cls(
            api_key="key",
            model_name="gemini-2.5-flash",
            client=error_client,
        )

        app = build_application(app_config, atomic_store, offline_coach, scheduler_service)
        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Hello coach",
            bot=app.bot,
        )
        resp = await app.process_update(update)
        assert resp is not None
        assert "Coach" in resp["text"]


class TestBotProactivePush:
    """Features 8–13: Proactive scheduled notifications & keyboard generator."""

    def test_inline_action_keyboard_structure(self) -> None:
        """Feature 13: Keyboard has exactly 3 buttons with expected callback_data."""
        keyboard = make_inline_action_keyboard("session_test_99")
        assert len(keyboard.inline_keyboard) == 3
        assert keyboard.inline_keyboard[0][0].callback_data == "done:session_test_99"
        assert keyboard.inline_keyboard[1][0].callback_data == "snooze:session_test_99"
        assert keyboard.inline_keyboard[2][0].callback_data == "skip:session_test_99"

    @pytest.mark.asyncio
    async def test_send_session_reminder_gym(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Gym reminder formats message and sends with inline keyboard."""
        resp = await bot_application.send_session_reminder("gym", "Gym Workout")
        assert resp is not None
        assert "GYM" in resp["text"]

    @pytest.mark.asyncio
    async def test_send_session_reminder_toeic(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """TOEIC reminder formats message with day's rotation topic."""
        resp = await bot_application.send_session_reminder("toeic", "TOEIC Study Session")
        assert resp is not None
        assert "TOEIC" in resp["text"]

    @pytest.mark.asyncio
    async def test_send_session_reminder_major(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Major study reminder formats message and delivers to allowed chat."""
        resp = await bot_application.send_session_reminder("major", "Major Study & Game Dev")
        assert resp is not None
        assert ("CHUYÊN NGÀNH" in resp["text"] or "GAME" in resp["text"] or "20:45" in resp["text"])


class TestMainLifecycle:
    """Lifecycle orchestration and composition root tests."""

    def test_create_system_composition_wiring(
        self, app_config: AppConfig, atomic_store: AtomicJsonStore, coach_service: Any, scheduler_service: Any, mock_bot: MockTelegramBot
    ) -> None:
        """create_system connects all 5 subsystems cleanly."""
        bot_app, scheduler, cfg = create_system(
            config=app_config,
            storage=atomic_store,
            coach=coach_service,
            scheduler=scheduler_service,
            bot=mock_bot,
        )
        assert bot_app.config is app_config
        assert bot_app.storage is atomic_store
        assert bot_app.coach is coach_service
        assert bot_app.scheduler is scheduler_service

    @pytest.mark.asyncio
    async def test_run_async_graceful_shutdown(
        self, app_config: AppConfig, atomic_store: AtomicJsonStore, coach_service: Any, scheduler_service: Any, mock_bot: MockTelegramBot
    ) -> None:
        """run_async boots scheduler and shuts down cleanly upon stop_event."""
        stop_event = asyncio.Event()

        # Signal stop immediately after start
        async def _trigger_stop():
            await asyncio.sleep(0.05)
            stop_event.set()

        asyncio.create_task(_trigger_stop())
        await run_async(config=app_config, stop_event=stop_event)
        # Should complete cleanly without uncaught exceptions


class TestAuthenticPTBArchitecture:
    """Verifies Milestone 4 authentic python-telegram-bot Application architecture."""

    def test_authentic_application_instance_and_updater(self, bot_application: Any) -> None:
        """BotApplication is a genuine PTB Application with initialized Updater and Queue."""
        from telegram.ext import Application, Updater
        assert isinstance(bot_application, Application)
        assert hasattr(bot_application, "updater")
        assert isinstance(bot_application.updater, Updater)
        assert hasattr(bot_application, "update_queue")
        assert isinstance(bot_application.update_queue, asyncio.Queue)

    def test_registered_authentic_ptb_handlers(self, bot_application: Any) -> None:
        """Authentic PTB handlers are registered in group 0."""
        from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler
        handlers = bot_application.handlers.get(0, [])
        assert len(handlers) in (5, 6)

        cmd_handlers = [h for h in handlers if isinstance(h, CommandHandler)]
        assert len(cmd_handlers) in (3, 4)
        all_registered = set()
        for h in cmd_handlers:
            all_registered.update(h.commands)
        assert {"start", "help", "status", "schedule"}.issubset(all_registered)

        cb_handlers = [h for h in handlers if isinstance(h, CallbackQueryHandler)]
        assert len(cb_handlers) == 1

        msg_handlers = [h for h in handlers if isinstance(h, MessageHandler)]
        assert len(msg_handlers) == 1

    def test_zero_imports_from_tests_in_src(self) -> None:
        """Source code in src/ has zero imports from tests/."""
        import inspect
        import src.bot
        import src.main

        src_bot_source = inspect.getsource(src.bot)
        src_main_source = inspect.getsource(src.main)

        assert "from tests" not in src_bot_source
        assert "import tests" not in src_bot_source
        assert "from tests" not in src_main_source
        assert "import tests" not in src_main_source

    def test_bot_property_and_setter(
        self,
        app_config: AppConfig,
        atomic_store: AtomicJsonStore,
        coach_service: Any,
        scheduler_service: Any,
    ) -> None:
        """app.bot defaults to super().bot (telegram.Bot) and allows test mock setter."""
        from telegram import Bot
        app = build_application(app_config, atomic_store, coach_service, scheduler_service)
        assert isinstance(app.bot, Bot)

        # Injected mock
        mock = MockTelegramBot()
        app.bot = mock
        assert app.bot is mock

        # Reset back
        app.bot = None
        assert isinstance(app.bot, Bot)

    @pytest.mark.asyncio
    async def test_snooze_3rd_rejection_attaches_action_keyboard(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """3rd snooze rejection preserves action keyboard markup for Done / Skip."""
        sid = "snooze_keyboard_test_3"
        await atomic_store.record_snooze(sid, 2)

        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{sid}",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "GIỚI HẠN" in resp["text"] or "HẾT QUYỀN" in resp["text"]
        assert "reply_markup" in resp
        assert resp["reply_markup"] is not None
        assert len(resp["reply_markup"].inline_keyboard) == 3

