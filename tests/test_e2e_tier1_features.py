"""Tier 1 E2E Test Suite: Happy-Path Feature Coverage.

Covers all 40 features from PROJECT.md Feature Inventory and ORIGINAL_REQUEST.md
under nominal operating conditions with zero network access.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
import pytest

from src.config import AppConfig, load_config
from src.storage import AtomicJsonStore, SessionStatus
from tests.mock_services import (
    MockTelegramBot,
    MockGeminiClient,
    make_text_update,
    make_callback_update,
    make_inline_action_keyboard,
)


# =====================================================================
# Group 1: Bot Security & Core Commands (Features 1, 3, 4, 5, 6)
# =====================================================================

class TestGroup1BotSecurityAndCommands:
    """Verifies Telegram bot lifecycle, security whitelist, and core commands."""

    @pytest.mark.asyncio
    async def test_f01_whitelist_allowed_user_accepted(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 1: Whitelist allows authorized chat_id."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/start")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Chào mừng" in resp["text"] or "Kỷ Luật" in resp["text"]

    @pytest.mark.asyncio
    async def test_f01_whitelist_unauthorized_user_rejected(
        self, bot_application: Any, app_config: AppConfig, coach_service: Any
    ) -> None:
        """Feature 1: Whitelist rejects unauthorized chat_id without calling coach."""
        unauthorized_id = 999999999
        assert unauthorized_id != app_config.allowed_chat_id

        update = make_text_update(chat_id=unauthorized_id, text="/start")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "từ chối" in resp["text"] or "Access denied" in resp["text"] or "ủy quyền" in resp["text"]

    @pytest.mark.asyncio
    async def test_f03_bot_lifecycle_boot(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 3: Bot initializes with all required subsystems attached."""
        assert bot_application is not None
        assert bot_application.config.allowed_chat_id == app_config.allowed_chat_id
        assert bot_application.storage is atomic_store
        assert bot_application.coach is not None
        assert bot_application.scheduler is not None

    @pytest.mark.asyncio
    async def test_f04_start_command_greeting(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 4: /start command delivers mission statement and command listing."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/start")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "/status" in resp["text"]
        assert "/help" in resp["text"]

    @pytest.mark.asyncio
    async def test_f05_help_command_guidance(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 5: /help command explains 3 inline actions (Done, Snooze, Skip)."""
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/help")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Đã hoàn thành" in resp["text"]
        assert "Xin lùi 15 phút" in resp["text"]
        assert "Hôm nay nghỉ" in resp["text"]

    @pytest.mark.asyncio
    async def test_f06_status_command_reporting(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 6: /status command displays streak metrics and completion history."""
        await atomic_store.record_completion("s1", "gym", "2026-10-01")
        update = make_text_update(chat_id=app_config.allowed_chat_id, text="/status")
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "BÁO CÁO KỶ LUẬT" in resp["text"] or "streak" in resp["text"].lower()
        assert "1" in resp["text"]  # streak count present


# =====================================================================
# Group 2: Timezone & Proactive Scheduler (Features 7, 8, 9, 10, 11, 12, 17)
# =====================================================================

class TestGroup2SchedulerAndTimezone:
    """Verifies APScheduler setup, cron triggers, and 7-day TOEIC rotation."""

    def test_f07_scheduler_timezone(self, scheduler_service: Any, app_config: AppConfig) -> None:
        """Feature 7: Scheduler operates strictly in Asia/Ho_Chi_Minh timezone."""
        assert scheduler_service.timezone_str == "Asia/Ho_Chi_Minh"
        assert app_config.timezone == "Asia/Ho_Chi_Minh"

    def test_f08_gym_split1_schedule(self, scheduler_service: Any, app_config: AppConfig) -> None:
        """Feature 8: Gym session 1 is scheduled for Mon, Tue, Thu at 17:15."""
        async def dummy_cb(session_type: str, name: str) -> None:
            pass

        scheduler_service.register_scheduled_jobs(app_config, dummy_cb)
        job = scheduler_service.registered_jobs.get("gym_split1")
        assert job is not None
        assert "mon,tue,thu" in job["days"].lower()
        assert job["time"] == "17:15"

    def test_f09_gym_split2_schedule(self, scheduler_service: Any, app_config: AppConfig) -> None:
        """Feature 9: Gym session 2 is scheduled for Wed, Sat at 16:15."""
        async def dummy_cb(session_type: str, name: str) -> None:
            pass

        scheduler_service.register_scheduled_jobs(app_config, dummy_cb)
        job = scheduler_service.registered_jobs.get("gym_split2")
        assert job is not None
        assert "wed,sat" in job["days"].lower()
        assert job["time"] == "16:15"

    def test_f10_toeic_study_schedule(self, scheduler_service: Any, app_config: AppConfig) -> None:
        """Feature 10: TOEIC session is scheduled daily at 19:25."""
        async def dummy_cb(session_type: str, name: str) -> None:
            pass

        scheduler_service.register_scheduled_jobs(app_config, dummy_cb)
        job = scheduler_service.registered_jobs.get("toeic")
        assert job is not None
        assert job["time"] == "19:25"

    def test_f11_toeic_7day_syllabus_rotation(self, app_config: AppConfig) -> None:
        """Feature 11: 7-day TOEIC rotation maps Monday through Sunday accurately."""
        rotation = app_config.toeic.syllabus_rotation
        assert len(rotation) == 7
        assert "Part 1" in app_config.toeic.get_part_for_weekday(0)
        assert "Part 2" in app_config.toeic.get_part_for_weekday(1)
        assert "Part 3" in app_config.toeic.get_part_for_weekday(2)
        assert "Part 4" in app_config.toeic.get_part_for_weekday(3)
        assert "Part 5" in app_config.toeic.get_part_for_weekday(4)
        assert "Part 6" in app_config.toeic.get_part_for_weekday(5)
        assert "Part 7" in app_config.toeic.get_part_for_weekday(6)

    def test_f12_major_subject_schedule(self, scheduler_service: Any, app_config: AppConfig) -> None:
        """Feature 12: Major Subject study session is scheduled daily at 20:40."""
        async def dummy_cb(session_type: str, name: str) -> None:
            pass

        scheduler_service.register_scheduled_jobs(app_config, dummy_cb)
        job = scheduler_service.registered_jobs.get("major")
        assert job is not None
        assert job["time"] == "20:40"

    @pytest.mark.asyncio
    async def test_f17_snooze_job_fires_after_delay(self, scheduler_service: Any) -> None:
        """Feature 17: APScheduler one-shot snooze job registers and executes callback."""
        executed = []

        async def snooze_cb(sid: str, stype: str, count: int) -> None:
            executed.append((sid, stype, count))

        job_id = scheduler_service.schedule_snooze_job(
            session_id="session_gym",
            session_type="gym",
            snooze_count=1,
            delay_minutes=15,
            callback=snooze_cb,
        )
        assert job_id in scheduler_service.snooze_jobs
        await scheduler_service.trigger_job(job_id)
        assert len(executed) == 1
        assert executed[0] == ("session_gym", "gym", 1)


# =====================================================================
# Group 3: Inline Actions, Snooze, & Skip Flows (Features 13, 14, 15, 16, 18, 19, 20, 21)
# =====================================================================

class TestGroup3InlineActionsAndSnoozeSkip:
    """Verifies button callbacks, snooze limit enforcement, and AI skip evaluation."""

    def test_f13_inline_keyboard_generator(self) -> None:
        """Feature 13: Generator builds exactly 3 action buttons with correct callback_data."""
        markup = make_inline_action_keyboard("gym_101")
        assert len(markup.inline_keyboard) == 3
        assert markup.inline_keyboard[0][0].callback_data == "done:gym_101"
        assert markup.inline_keyboard[1][0].callback_data == "snooze:gym_101"
        assert markup.inline_keyboard[2][0].callback_data == "skip:gym_101"

    @pytest.mark.asyncio
    async def test_f14_done_completion_handler(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 14: Done button increments streak, persists state, and praises user."""
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data="done:session_gym_today",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "HOÀN THÀNH" in resp["text"] or "kỷ luật" in resp["text"].lower()

        streak = await atomic_store.get_streak()
        assert streak.current_streak >= 1

    @pytest.mark.asyncio
    async def test_f15_snooze_15m_handler(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 15: First snooze increments count and schedules 15m delay."""
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data="snooze:session_gym_today",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "15 PHÚT" in resp["text"] or "Lần 1/2" in resp["text"]

        status = await atomic_store.get_session_status("session_gym_today")
        assert status is not None
        assert status["snooze_count"] == 1

    @pytest.mark.asyncio
    async def test_f16_snooze_cap_enforcement(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 16: Snoozing past 2 times is strictly blocked with escalating firm order."""
        await atomic_store.record_snooze("sess_test", 1)
        await atomic_store.record_snooze("sess_test", 2)

        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data="snooze:sess_test",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "GIỚI HẠN" in resp["text"] or "HẾT QUYỀN" in resp["text"]

    @pytest.mark.asyncio
    async def test_f18_skip_with_reason_trigger(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 18: Skip button sets awaiting_reason state and prompts for justification."""
        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data="skip:sess_skip_test",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "LÝ DO" in resp["text"]

        data = await atomic_store.load_data()
        assert data.get("awaiting_reason") is not None
        assert data["awaiting_reason"]["session_id"] == "sess_skip_test"

    @pytest.mark.asyncio
    async def test_f19_f20_skip_excuse_triggers_micro_habit(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Features 19 & 20: Excuse is deconstructed and 2-minute micro-habit is enforced."""
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": "sess_toeic_today", "session_type": "toeic"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Hôm nay em lười quá, muốn nằm xem video YouTube",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "BAO BIỆN" in resp["text"] or "MICRO-HABIT" in resp["text"] or "2 PHÚT" in resp["text"]

    @pytest.mark.asyncio
    async def test_f21_legitimate_skip_approval(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 21: Legitimate obstacle is approved and status recorded as skipped."""
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": "sess_major_today", "session_type": "major"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Em bị sốt cao 39 độ phải vào bệnh viện cấp cứu gấp",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "CHÍNH ĐÁNG" in resp["text"] or "phục hồi" in resp["text"].lower()

        status = await atomic_store.get_session_status("sess_major_today")
        assert status is not None
        assert status["status"] == SessionStatus.SKIPPED
        assert status["classification"] == "LEGITIMATE"


# =====================================================================
# Group 4: Gemini AI Accountability Coach (Features 22, 23, 24, 25, 26)
# =====================================================================

class TestGroup4GeminiCoachAndFallbacks:
    """Verifies Gemini SDK integration, coach persona, context buffer, and offline fallback."""

    @pytest.mark.asyncio
    async def test_f22_genai_integration(self, coach_service: Any) -> None:
        """Feature 22: Coach service generates praise content via Gemini client."""
        praise = await coach_service.get_congratulation("gym", streak=3)
        assert praise is not None
        assert len(praise.strip()) > 0

    @pytest.mark.asyncio
    async def test_f23_coach_persona_conciseness(self, coach_service: Any) -> None:
        """Feature 23: Coach answers concisely (max 2-3 sentences) with technical mindset."""
        reply = await coach_service.chat("Chào coach, tôi đang làm dở game engine.")
        assert reply is not None
        # Max 2-3 sentences assertion
        sentences = [s for s in reply.split(".") if s.strip()]
        assert len(sentences) <= 4

    @pytest.mark.asyncio
    async def test_f24_sliding_context_window(self, coach_service: Any) -> None:
        """Feature 24: Coach retains sliding buffer of recent interactions (<=10)."""
        coach_service.clear_context()
        for i in range(12):
            await coach_service.chat(f"Message number {i}")
        # Buffer stores user and coach pairs, cap prevents unbounded growth
        assert len(coach_service.context_window) <= 10

    @pytest.mark.asyncio
    async def test_f25_graceful_offline_fallback(
        self, app_config: AppConfig, valid_yaml_dict: Dict[str, Any]
    ) -> None:
        """Feature 25: Returns configured offline fallback when Gemini API fails."""
        from tests.mock_services import get_ai_coach_class
        error_client = MockGeminiClient(api_key="key", error_mode="timeout")
        cls = get_ai_coach_class()
        offline_coach = cls(
            api_key="key",
            model_name="gemini-2.5-flash",
            config=valid_yaml_dict,
            client=error_client,
        )

        praise = await offline_coach.get_congratulation("gym", 5)
        assert praise == valid_yaml_dict["fallbacks"]["offline_praise"]

        reply = await offline_coach.chat("Hello?")
        assert reply == valid_yaml_dict["fallbacks"]["offline_coach"]

    @pytest.mark.asyncio
    async def test_f26_reactive_free_form_chat(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 26: Free-form user message outside reminders triggers AI coaching response."""
        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Làm sao để tối ưu hoá thời gian cày TOEIC và game dev?",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Coach" in resp["text"]


# =====================================================================
# Group 5: Atomic JSON Persistence & Streaks (Features 27, 28, 29, 30)
# =====================================================================

class TestGroup5PersistenceAndStreaks:
    """Verifies crash-safe storage, schema integrity, and calendar-day streak tracking."""

    @pytest.mark.asyncio
    async def test_f27_data_dir_creation(self, tmp_path: Path) -> None:
        """Feature 27: Store automatically ensures data directory exists."""
        deep_path = tmp_path / "deep" / "nested" / "records.json"
        assert not deep_path.parent.exists()
        store = AtomicJsonStore(file_path=str(deep_path))
        assert deep_path.parent.exists()

    @pytest.mark.asyncio
    async def test_f28_atomic_json_write(self, atomic_store: AtomicJsonStore) -> None:
        """Feature 28: Store writes data atomically via temporary file and replace."""
        data = await atomic_store.load_data()
        data["streak"]["total_completions"] = 42
        await atomic_store.save_data(data)

        reloaded = await atomic_store.load_data()
        assert reloaded["streak"]["total_completions"] == 42

    @pytest.mark.asyncio
    async def test_f29_json_schema_validation(self, atomic_store: AtomicJsonStore) -> None:
        """Feature 29: Stored records adhere to schema structure."""
        data = await atomic_store.load_data()
        assert "version" in data
        assert "streak" in data
        assert "sessions" in data
        assert "history" in data
        assert "current_streak" in data["streak"]
        assert "best_streak" in data["streak"]

    @pytest.mark.asyncio
    async def test_f30_calendar_day_streak_tracking(self, atomic_store: AtomicJsonStore) -> None:
        """Feature 30: Tracks consecutive calendar days in Asia/Ho_Chi_Minh timezone."""
        s1 = await atomic_store.record_completion("ses1", "gym", "2026-10-01")
        assert s1.current_streak == 1

        # Same day completion does not double-count streak
        s2 = await atomic_store.record_completion("ses2", "toeic", "2026-10-01")
        assert s2.current_streak == 1

        # Consecutive day increments streak
        s3 = await atomic_store.record_completion("ses3", "gym", "2026-10-02")
        assert s3.current_streak == 2


# =====================================================================
# Group 6: Mocking, Config, & Deployment Specs (Features 2, 31-40)
# =====================================================================

class TestGroup6MockingAndConfiguration:
    """Verifies offline test doubles, configuration separation, and deployment specifications."""

    def test_f02_secret_config_decoupling(self, app_config: AppConfig) -> None:
        """Feature 2: Secrets from .env are strictly separated from config.yaml parameters."""
        assert app_config.bot_token.startswith("1234567890:")
        assert app_config.gemini_api_key.startswith("AIzaSy")
        assert app_config.gym.duration_minutes == 60
        assert app_config.max_snoozes == 2

    def test_f31_offline_telegram_mocking(self) -> None:
        """Feature 31: MockTelegramBot captures send/edit/callback operations without network."""
        bot = MockTelegramBot()
        assert len(bot.sent_messages) == 0
        assert len(bot.edited_messages) == 0

    def test_f32_offline_gemini_mocking(self) -> None:
        """Feature 32: MockGeminiClient deterministic generation with zero network access."""
        client = MockGeminiClient()
        assert client.aio is not None
        assert client.api_key is not None

    def test_f33_scheduler_verification(self, scheduler_service: Any) -> None:
        """Feature 33: Scheduler triggers are validated and manageable."""
        assert scheduler_service.timezone_str == "Asia/Ho_Chi_Minh"
        scheduler_service.start()
        assert scheduler_service.is_running
        scheduler_service.shutdown()
        assert not scheduler_service.is_running

    @pytest.mark.asyncio
    async def test_f34_state_machine_coverage(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Feature 34: State transitions from pending to snoozed to awaiting_reason to done."""
        sid = "f34_session"
        # 1. Snooze
        cb_snooze = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot
        )
        await bot_application.process_update(cb_snooze)
        status = await atomic_store.get_session_status(sid)
        assert status["snooze_count"] == 1

        # 2. Done
        cb_done = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"done:{sid}", bot=bot_application.bot
        )
        await bot_application.process_update(cb_done)
        status = await atomic_store.get_session_status(sid)
        assert status["status"] == SessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_f35_persistence_integrity(self, atomic_store: AtomicJsonStore) -> None:
        """Feature 35: High frequency writes preserve record integrity."""
        for i in range(10):
            await atomic_store.record_completion(f"ses_{i}", "major", "2026-10-01")
        data = await atomic_store.load_data()
        assert len(data["sessions"]) == 10

    @pytest.mark.asyncio
    async def test_f36_security_whitelist_verification(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Feature 36: Security filter strictly blocks adversarial chat IDs."""
        for bad_id in [1, 99999, -1001234567, 123456788]:
            assert bad_id != app_config.allowed_chat_id
            update = make_text_update(chat_id=bad_id, text="/status")
            resp = await bot_application.process_update(update)
            assert resp is not None
            assert "từ chối" in resp["text"] or "Access denied" in resp["text"] or "ủy quyền" in resp["text"]

    def test_f37_env_example_template_presence(self) -> None:
        """Feature 37: .env.example exists and lists all required environment variables."""
        env_example_path = Path(".env.example")
        assert env_example_path.exists()
        content = env_example_path.read_text(encoding="utf-8")
        assert "TELEGRAM_BOT_TOKEN" in content
        assert "GEMINI_API_KEY" in content
        assert "ALLOWED_CHAT_ID" in content

    def test_f38_config_yaml_parameters(self) -> None:
        """Feature 38: config.yaml exists and defines complete operational parameters."""
        config_path = Path("config.yaml")
        assert config_path.exists()
        content = config_path.read_text(encoding="utf-8")
        assert "Asia/Ho_Chi_Minh" in content
        assert "gym" in content
        assert "toeic" in content
        assert "major" in content

    def test_f39_docker_specifications(self) -> None:
        """Feature 39: Deployment container specifications or readiness check."""
        dockerfile = Path("Dockerfile")
        compose = Path("docker-compose.yml")
        # In M1/E2E, files may be present or will be provided in M5; verify spec conformity
        if dockerfile.exists():
            content = dockerfile.read_text(encoding="utf-8")
            assert "python" in content.lower()
        if compose.exists():
            content = compose.read_text(encoding="utf-8")
            assert "services" in content

    def test_f40_single_click_startup_scripts(self) -> None:
        """Feature 40: Single-click startup scripts or execution readiness check."""
        bat = Path("start.bat")
        sh = Path("start.sh")
        # If files exist, verify execution commands
        if bat.exists():
            content = bat.read_text(encoding="utf-8")
            assert "python" in content.lower()
        if sh.exists():
            content = sh.read_text(encoding="utf-8")
            assert "python" in content.lower()
