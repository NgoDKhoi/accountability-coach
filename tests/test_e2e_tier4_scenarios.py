"""Tier 4 E2E Test Suite: Real-World Multi-Step End-to-End Scenarios.

Verifies end-to-end user journeys:
1. 7-Day Workout Streak + TOEIC 7-Day Syllabus Rotation Progression
2. Excuse Challenge & 2-Minute Micro-Habit Recovery Workflow
3. Full Daily 3-Session Timeline (Gym Snooze/Done + TOEIC Done + Major Legitimate Skip)
4. Bot Restart & Crash Recovery with Persistent State Preservation
5. Escalating Snooze Limit Workflow (Warning 1 -> Warning 2 -> Rejection -> Done)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict
import pytest
from zoneinfo import ZoneInfo

from src.config import AppConfig
from src.storage import AtomicJsonStore, SessionStatus
from tests.mock_services import (
    MockTelegramBot,
    DefaultBotApplication,
    make_text_update,
    make_callback_update,
    make_inline_action_keyboard,
    get_build_application_fn,
)


class TestTier4RealWorldScenarios:
    """Verifies complex multi-step real-world workflows from the user's perspective."""

    @pytest.mark.asyncio
    async def test_s1_seven_day_progression_streak_and_toeic_rotation(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Scenario 1: 7-day progression from Mon to Sun validating streak growth and TOEIC rotation."""
        days = [
            ("2026-10-05", 0, "Part 1"),  # Monday
            ("2026-10-06", 1, "Part 2"),  # Tuesday
            ("2026-10-07", 2, "Part 3"),  # Wednesday
            ("2026-10-08", 3, "Part 4"),  # Thursday
            ("2026-10-09", 4, "Part 5"),  # Friday
            ("2026-10-10", 5, "Part 6"),  # Saturday
            ("2026-10-11", 6, "Part 7"),  # Sunday
        ]

        for day_str, weekday, expected_part in days:
            # 1. Verify TOEIC syllabus matches weekday
            resolved_part = app_config.toeic.get_part_for_weekday(weekday)
            assert expected_part in resolved_part

            # 2. Complete daily TOEIC session
            sid = f"toeic_{day_str}"
            cb = make_callback_update(
                chat_id=app_config.allowed_chat_id,
                callback_data=f"done:{sid}",
                bot=bot_application.bot,
            )
            # Patch today's date in storage record
            await atomic_store.record_completion(sid, "toeic", day_str)

        # 3. Verify streak accumulated to 7 consecutive days
        streak_data = await atomic_store.get_streak()
        assert streak_data.current_streak == 7
        assert streak_data.best_streak == 7
        assert streak_data.total_completions == 7
        assert streak_data.last_completed_date == "2026-10-11"

    @pytest.mark.asyncio
    async def test_s2_excuse_challenge_and_micro_habit_recovery(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Scenario 2: User tries to skip with excuse, gets challenged with 2m micro-habit, then finishes."""
        sid = "scenario2_session"

        # Step 1: Reminder was sent, user clicks Skip
        cb_skip = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"skip:{sid}",
            bot=bot_application.bot,
        )
        r_skip = await bot_application.process_update(cb_skip)
        assert "LÝ DO" in r_skip["text"]

        # Step 2: User sends procrastination excuse
        msg_excuse = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="Hôm nay em lười quá, mệt mỏi muốn nằm lướt TikTok",
            bot=bot_application.bot,
        )
        r_excuse = await bot_application.process_update(msg_excuse)
        # AI Coach deconstructs excuse and enforces 2-minute micro-habit
        assert "BAO BIỆN" in r_excuse["text"] or "MICRO-HABIT" in r_excuse["text"]

        # Step 3: User complies with micro-habit and marks session Done
        cb_done = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"done:{sid}",
            bot=bot_application.bot,
        )
        r_done = await bot_application.process_update(cb_done)
        assert "HOÀN THÀNH" in r_done["text"]

        # Step 4: Verify streak was preserved and incremented
        streak = await atomic_store.get_streak()
        assert streak.current_streak >= 1

    @pytest.mark.asyncio
    async def test_s3_full_daily_three_session_timeline(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore, scheduler_service: Any
    ) -> None:
        """Scenario 3: Gym (Snooze 1x -> Job fires -> Done) -> TOEIC (Done) -> Major (Legitimate Skip)."""
        # Session 1: Gym at 17:15
        gym_sid = "daily_gym"
        # User clicks Snooze 15m
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{gym_sid}", bot=bot_application.bot)
        )
        # Snooze job fires at 17:30
        job_id = f"snooze_{gym_sid}_1"
        assert job_id in scheduler_service.snooze_jobs
        await scheduler_service.trigger_job(job_id)
        # User marks Done
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"done:{gym_sid}", bot=bot_application.bot)
        )

        # Session 2: TOEIC at 19:25
        toeic_sid = "daily_toeic"
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"done:{toeic_sid}", bot=bot_application.bot)
        )

        # Session 3: Major Subject at 20:40
        major_sid = "daily_major"
        await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"skip:{major_sid}", bot=bot_application.bot)
        )
        await bot_application.process_update(
            make_text_update(chat_id=app_config.allowed_chat_id, text="Cấp cứu bệnh viện ngộ độc thực phẩm", bot=bot_application.bot)
        )

        # Final Daily Status Check via /status command
        r_status = await bot_application.process_update(
            make_text_update(chat_id=app_config.allowed_chat_id, text="/status", bot=bot_application.bot)
        )
        assert r_status is not None
        assert "BÁO CÁO KỶ LUẬT" in r_status["text"] or "streak" in r_status["text"].lower()

        # Check records
        g_st = await atomic_store.get_session_status(gym_sid)
        t_st = await atomic_store.get_session_status(toeic_sid)
        m_st = await atomic_store.get_session_status(major_sid)

        assert g_st["status"] == SessionStatus.COMPLETED
        assert t_st["status"] == SessionStatus.COMPLETED
        assert m_st["status"] == SessionStatus.SKIPPED
        assert m_st["classification"] == "LEGITIMATE"

    @pytest.mark.asyncio
    async def test_s4_bot_restart_and_crash_recovery(
        self, app_config: AppConfig, atomic_store: AtomicJsonStore, coach_service: Any, scheduler_service: Any
    ) -> None:
        """Scenario 4: Bot process restarts; loaded storage maintains streak and pending state."""
        # 1. Establish initial 3-day streak before restart
        await atomic_store.record_completion("old1", "gym", "2026-10-10")
        await atomic_store.record_completion("old2", "gym", "2026-10-11")
        await atomic_store.record_completion("old3", "gym", "2026-10-12")
        await atomic_store.record_snooze("pending_sess", 1)

        # 2. Simulate bot crash and reboot with fresh Application instance
        build_fn = get_build_application_fn()
        new_bot_app = build_fn(app_config, atomic_store, coach_service, scheduler_service)

        # 3. New instance checks /status
        r_status = await new_bot_app.process_update(
            make_text_update(chat_id=app_config.allowed_chat_id, text="/status", bot=new_bot_app.bot)
        )
        assert "3" in r_status["text"]  # Streak of 3 preserved

        # 4. Pending session is completed on new instance
        await new_bot_app.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data="done:pending_sess", bot=new_bot_app.bot)
        )
        status = await atomic_store.get_session_status("pending_sess")
        assert status["status"] == SessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_s5_escalating_snooze_limit_to_completion(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore, scheduler_service: Any
    ) -> None:
        """Scenario 5: Reminder -> Snooze 1 (Warning 1) -> Snooze 2 (Warning 2) -> Snooze 3 (Blocked) -> Done."""
        sid = "s5_escalation"

        # 1. First Snooze: Warning 1
        r1 = await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot)
        )
        assert "Lần 1/2" in r1["text"]

        # 2. Second Snooze: Warning 2
        r2 = await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot)
        )
        assert "Lần 2/2" in r2["text"]

        # 3. Third Snooze Attempt: Strictly Blocked
        r3 = await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot)
        )
        assert "HẾT QUYỀN" in r3["text"] or "GIỚI HẠN" in r3["text"]

        # 4. User accepts command and completes session
        r4 = await bot_application.process_update(
            make_callback_update(chat_id=app_config.allowed_chat_id, callback_data=f"done:{sid}", bot=bot_application.bot)
        )
        assert "HOÀN THÀNH" in r4["text"]

        # 5. Verify final status is COMPLETED with snooze_count=2
        status = await atomic_store.get_session_status(sid)
        assert status["status"] == SessionStatus.COMPLETED
        assert status["snooze_count"] == 2
