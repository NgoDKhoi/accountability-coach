"""Tier 3 E2E Test Suite: Cross-Feature Pairwise Interactions.

Verifies interactions between subsystems (Snooze + Skip, Done + Status,
Unauthorized + Callbacks, Multi-Session combinations, Gemini Fallback + Storage).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict
import pytest
from zoneinfo import ZoneInfo

from src.config import AppConfig
from src.storage import AtomicJsonStore, SessionStatus
from tests.mock_services import (
    MockTelegramBot,
    MockGeminiClient,
    make_text_update,
    make_callback_update,
    make_inline_action_keyboard,
)


class TestTier3PairwiseInteractions:
    """Verifies pairwise cross-feature dynamics between distinct system modules."""

    @pytest.mark.asyncio
    async def test_t3_p1_snooze_then_skip_lifecycle(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 1: Snooze 15m followed by Skip with reason properly cleans up and transitions state."""
        sid = "pairwise_snooze_skip"

        # 1. User clicks Snooze
        cb_snooze = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot
        )
        await bot_application.process_update(cb_snooze)
        status = await atomic_store.get_session_status(sid)
        assert status["status"] == SessionStatus.SNOOZED
        assert status["snooze_count"] == 1

        # 2. Before snooze expires, user clicks Skip
        cb_skip = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"skip:{sid}", bot=bot_application.bot
        )
        resp_skip = await bot_application.process_update(cb_skip)
        assert "LÝ DO" in resp_skip["text"]

        data = await atomic_store.load_data()
        assert data.get("awaiting_reason") is not None
        assert data["awaiting_reason"]["session_id"] == sid

        # 3. User submits legitimate justification
        text_reason = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Gia đình có việc đột xuất phải vào bệnh viện",
            bot=bot_application.bot,
        )
        resp_reason = await bot_application.process_update(text_reason)
        assert "CHÍNH ĐÁNG" in resp_reason["text"] or "phục hồi" in resp_reason["text"].lower()

        # 4. Final state check
        final_status = await atomic_store.get_session_status(sid)
        assert final_status["status"] == SessionStatus.SKIPPED
        assert final_status["classification"] == "LEGITIMATE"

    @pytest.mark.asyncio
    async def test_t3_p2_done_streak_status_reporting(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 2: Marking Done immediately reflects in the /status command metrics."""
        sid = "pairwise_done_status"

        # 1. Check initial /status
        up_status1 = make_text_update(chat_id=app_config.allowed_chat_id, text="/status", bot=bot_application.bot)
        r1 = await bot_application.process_update(up_status1)
        assert "0" in r1["text"]

        # 2. Complete session via Done callback
        cb_done = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"done:{sid}", bot=bot_application.bot
        )
        await bot_application.process_update(cb_done)

        # 3. Query /status again
        up_status2 = make_text_update(chat_id=app_config.allowed_chat_id, text="/status", bot=bot_application.bot)
        r2 = await bot_application.process_update(up_status2)
        assert "1" in r2["text"]
        assert "Kỷ lục streak tốt nhất: *1*" in r2["text"] or "1" in r2["text"]

    @pytest.mark.asyncio
    async def test_t3_p3_unauthorized_user_button_tampering(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 3: Unauthorized user attacking inline buttons does not alter session state or streak."""
        sid = "pairwise_secure_sess"
        attacker_id = 777777777

        # Attacker tries to click 'done'
        cb = make_callback_update(chat_id=attacker_id, callback_data=f"done:{sid}", bot=bot_application.bot)
        await bot_application.process_update(cb)

        # State must remain non-existent / unmutated
        status = await atomic_store.get_session_status(sid)
        assert status is None

        streak = await atomic_store.get_streak()
        assert streak.current_streak == 0
        assert streak.total_completions == 0

    @pytest.mark.asyncio
    async def test_t3_p4_snooze_cap_reached_then_excuse_challenge(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 4: When snooze limit is hit (2/2) and user skips with excuse, micro-habit is enforced."""
        sid = "pairwise_cap_excuse"

        # Snooze 1
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot)
        )
        # Snooze 2
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot)
        )
        # Attempt Snooze 3 (Blocked)
        r_blocked = await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot)
        )
        assert "HẾT QUYỀN" in r_blocked["text"] or "GIỚI HẠN" in r_blocked["text"]

        # User gives up and clicks Skip
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"skip:{sid}", bot=bot_application.bot)
        )

        # User submits excuse
        r_eval = await bot_application.process_update(
            make_text_update(chat_id=app_config.allowed_chat_id, text="Buồn ngủ quá lười code tiếp", bot=bot_application.bot)
        )
        assert "MICRO-HABIT" in r_eval["text"] or "BAO BIỆN" in r_eval["text"]

    @pytest.mark.asyncio
    async def test_t3_p5_toeic_syllabus_rotation_with_active_session(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 5: TOEIC dynamic syllabus resolution integrates with active session reminder and done flow."""
        today_weekday = datetime.now(ZoneInfo(app_config.timezone)).weekday()
        expected_part = app_config.toeic.get_part_for_weekday(today_weekday)
        assert len(expected_part) > 0

        sid = f"toeic_day_{today_weekday}"
        # Complete TOEIC session
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"done:{sid}", bot=bot_application.bot)
        )

        status = await atomic_store.get_session_status(sid)
        assert status is not None
        assert status["status"] == SessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_t3_p6_storage_lock_concurrency_race(
        self, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 6: Concurrent record_completion, record_snooze, and record_skip operations serialize safely."""
        tasks = []
        for i in range(10):
            tasks.append(atomic_store.record_completion(f"race_comp_{i}", "gym", "2026-10-20"))
            tasks.append(atomic_store.record_snooze(f"race_snooze_{i}", 1))
            tasks.append(atomic_store.record_skip(f"race_skip_{i}", "busy", "EXCUSE", "2026-10-20T12:00:00"))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Ensure zero exceptions were raised
        for res in results:
            assert not isinstance(res, Exception)

        data = await atomic_store.load_data()
        assert len(data["sessions"]) == 30

    @pytest.mark.asyncio
    async def test_t3_p7_gemini_timeout_during_skip_reason_evaluation(
        self, app_config: AppConfig, atomic_store: AtomicJsonStore, scheduler_service: Any
    ) -> None:
        """Pairwise 7: Gemini API timeout during skip evaluation triggers fallback and completes recording."""
        from tests.mock_services import DefaultBotApplication, get_ai_coach_class
        error_client = MockGeminiClient(api_key="fake-key", error_mode="timeout")
        cls = get_ai_coach_class()
        offline_coach = cls(
            api_key=app_config.gemini_api_key,
            model_name=app_config.gemini_model,
            config={"fallbacks": app_config.fallbacks, "prompts": app_config.prompts},
            client=error_client,
        )

        app = DefaultBotApplication(
            config=app_config,
            storage=atomic_store,
            coach=offline_coach,
            scheduler=scheduler_service,
        )

        sid = "timeout_skip_sess"
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": sid, "session_type": "toeic"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Lười quá không muốn học",
            bot=app.bot,
        )
        resp = await app.process_update(update)
        assert resp is not None
        # Must return fallback and record session without crashing
        status = await atomic_store.get_session_status(sid)
        assert status is not None
        assert status["status"] == SessionStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_t3_p8_three_sessions_same_day_lifecycle(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Pairwise 8: Gym (Done) + TOEIC (Snoozed 1x, then Done) + Major (Skip legitimate) in single day."""
        today = "2026-10-25"

        # 1. Gym Done
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data="done:gym_25", bot=bot_application.bot)
        )

        # 2. TOEIC Snoozed then Done
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data="snooze:toeic_25", bot=bot_application.bot)
        )
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data="done:toeic_25", bot=bot_application.bot)
        )

        # 3. Major Skip Legitimate
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data="skip:major_25", bot=bot_application.bot)
        )
        await bot_application.process_update(
            make_text_update(chat_id=app_config.allowed_chat_id, text="Sốt cao phải đi cấp cứu bệnh viện", bot=bot_application.bot)
        )

        # Verify combined statuses
        s_gym = await atomic_store.get_session_status("gym_25")
        s_toeic = await atomic_store.get_session_status("toeic_25")
        s_major = await atomic_store.get_session_status("major_25")

        assert s_gym["status"] == SessionStatus.COMPLETED
        assert s_toeic["status"] == SessionStatus.COMPLETED
        assert s_major["status"] == SessionStatus.SKIPPED
        assert s_major["classification"] == "LEGITIMATE"

        # Verify streak maintained (at least 1 for today)
        streak = await atomic_store.get_streak()
        assert streak.current_streak >= 1
