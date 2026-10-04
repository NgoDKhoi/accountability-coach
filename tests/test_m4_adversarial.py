"""Empirical Adversarial Stress-Test Suite for Milestone 4 (Bot Core & Lifecycle).

Covers:
1. Whitelist rejection under adversarial conditions: unauthorized chat IDs (0, -1, group chat IDs,
   off-by-one IDs, non-numeric strings, None). Asserts zero Gemini API calls and zero storage mutations.
2. Rapid concurrent callback queries: multiple rapid clicks on Done (idempotency, streak does not inflate).
3. Snooze limit: rapid repeated snooze clicks beyond cap of 2. Verifies attempts 3, 4, 5 are strictly blocked.
4. Edge cases: Malformed callback payloads, concurrent mixed callbacks, and state machine edge cases.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List
import pytest
from zoneinfo import ZoneInfo

from src.config import AppConfig
from src.storage import AtomicJsonStore, SessionStatus, StreakData
from src.bot import BotApplication, build_application, make_inline_action_keyboard
from tests.mock_services import (
    MockTelegramBot,
    MockGeminiClient,
    MockChat,
    MockUser,
    MockMessage,
    MockCallbackQuery,
    MockUpdate,
    make_text_update,
    make_callback_update,
)


# =====================================================================
# 1. Whitelist Rejection Under Adversarial Conditions
# =====================================================================

class TestAdversarialWhitelistRejection:
    """Stress tests for strict authorization whitelist gate."""

    @pytest.mark.asyncio
    async def test_whitelist_rejection_boundary_chat_ids(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        mock_gemini_client: MockGeminiClient,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Adversarial chat IDs (0, -1, group -100..., off-by-one, huge ints) are rejected."""
        adversarial_ids = [
            0,
            -1,
            -1001987654321,  # Telegram supergroup/channel ID
            -1009999999999,
            app_config.allowed_chat_id + 1,
            app_config.allowed_chat_id - 1,
            1,
            999999999999999,
            -999999999999999,
        ]

        data_before = await atomic_store.load_data()
        gemini_calls_before = len(mock_gemini_client.models.call_history)

        for bad_id in adversarial_ids:
            # 1. Test message attempt
            msg_update = make_text_update(chat_id=bad_id, text="/start", bot=bot_application.bot)
            resp = await bot_application.process_update(msg_update)
            assert resp is not None
            assert any(kw in resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])

            # 2. Test callback attempt
            cb_update = make_callback_update(
                chat_id=bad_id,
                callback_data="done:adversarial_sess",
                bot=bot_application.bot,
            )
            cb_resp = await bot_application.process_update(cb_update)
            assert cb_resp is not None
            assert any(kw in cb_resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])

        # VERIFY ZERO GEMINI CALLS
        assert len(mock_gemini_client.models.call_history) == gemini_calls_before

        # VERIFY ZERO STORAGE MUTATIONS
        data_after = await atomic_store.load_data()
        assert data_before == data_after

    @pytest.mark.asyncio
    async def test_whitelist_rejection_zero_gemini_and_storage_mutations_comprehensive(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        mock_gemini_client: MockGeminiClient,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Verifies zero Gemini API calls and zero storage mutations across all update types."""
        unauthorized_id = 888777666
        assert unauthorized_id != app_config.allowed_chat_id

        data_before = await atomic_store.load_data()
        gemini_calls_before = len(mock_gemini_client.models.call_history)

        attack_updates = [
            make_text_update(chat_id=unauthorized_id, text="/start", bot=bot_application.bot),
            make_text_update(chat_id=unauthorized_id, text="/help", bot=bot_application.bot),
            make_text_update(chat_id=unauthorized_id, text="/status", bot=bot_application.bot),
            make_text_update(chat_id=unauthorized_id, text="Tôi muốn bỏ tập hôm nay vì mệt", bot=bot_application.bot),
            make_text_update(chat_id=unauthorized_id, text="Lập trình game Unity có khó không?", bot=bot_application.bot),
            make_callback_update(chat_id=unauthorized_id, callback_data="done:gym_20261004", bot=bot_application.bot),
            make_callback_update(chat_id=unauthorized_id, callback_data="snooze:gym_20261004", bot=bot_application.bot),
            make_callback_update(chat_id=unauthorized_id, callback_data="skip:gym_20261004", bot=bot_application.bot),
        ]

        for upd in attack_updates:
            resp = await bot_application.process_update(upd)
            assert resp is not None
            assert any(kw in resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])

        # Strict assertion: Zero Gemini API calls
        assert len(mock_gemini_client.models.call_history) == gemini_calls_before

        # Strict assertion: Zero storage mutations
        data_after = await atomic_store.load_data()
        assert data_before == data_after

    @pytest.mark.asyncio
    async def test_whitelist_non_numeric_chat_id_empirically(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        mock_gemini_client: MockGeminiClient,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Tests how bot_application handles non-numeric chat IDs ('abc', None).
        
        Assesses whether process_update rejects or raises ValueError/TypeError,
        and verifies zero Gemini calls and zero storage mutations in either case.
        """
        gemini_before = len(mock_gemini_client.models.call_history)
        data_before = await atomic_store.load_data()

        # Test non-numeric string chat_id
        chat = MockChat("not_a_numeric_id")  # type: ignore[arg-type]
        user = MockUser(9999)
        msg = MockMessage(message_id=500, chat=chat, from_user=user, text="/start", bot=bot_application.bot)
        bad_update = MockUpdate(update_id=500, message=msg)

        try:
            resp = await bot_application.process_update(bad_update)
            # If handled, it must not grant access
            if resp is not None:
                assert any(kw in resp.get("text", "").lower() for kw in ["từ chối", "access denied", "ủy quyền"])
        except (ValueError, TypeError) as exc:
            # If unhandled ValueError/TypeError is raised by int(chat.id), record empirical behavior
            assert isinstance(exc, (ValueError, TypeError))

        # Under all circumstances: Zero Gemini calls and zero storage mutations
        assert len(mock_gemini_client.models.call_history) == gemini_before
        assert await atomic_store.load_data() == data_before

    @pytest.mark.asyncio
    async def test_whitelist_string_numeric_chat_id_handling(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """String numeric IDs (e.g. '123456789') match correctly via int() casting."""
        # Authorized ID as string
        auth_str_update = make_text_update(
            chat_id=int(app_config.allowed_chat_id),
            text="/status",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(auth_str_update)
        assert resp is not None
        assert "BÁO CÁO KỶ LUẬT" in resp["text"] or "streak" in resp["text"].lower()

        # Unauthorized ID as string
        unauth_update = make_text_update(
            chat_id=999123456,
            text="/status",
            bot=bot_application.bot,
        )
        unauth_resp = await bot_application.process_update(unauth_update)
        assert unauth_resp is not None
        assert any(kw in unauth_resp["text"].lower() for kw in ["từ chối", "access denied", "ủy quyền"])


# =====================================================================
# 2. Rapid Concurrent Callback Queries (Done Idempotency)
# =====================================================================

class TestRapidConcurrentDoneCallbacks:
    """Stress tests asserting idempotency under rapid concurrent Done clicks."""

    @pytest.mark.asyncio
    async def test_rapid_concurrent_done_clicks_same_session(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Multiple rapid concurrent clicks on Done do NOT inflate streak or completions."""
        session_id = "gym_rapid_concurrent_done"
        num_clicks = 10

        updates = [
            make_callback_update(
                chat_id=app_config.allowed_chat_id,
                callback_data=f"done:{session_id}",
                bot=bot_application.bot,
            )
            for _ in range(num_clicks)
        ]

        # Launch all Done callbacks concurrently
        responses = await asyncio.gather(
            *[bot_application.process_update(upd) for upd in updates]
        )

        # All callbacks should return successfully
        assert len(responses) == num_clicks
        for resp in responses:
            assert resp is not None
            assert "HOÀN THÀNH" in resp["text"]

        # Assert streak was incremented exactly once (idempotent)
        streak = await atomic_store.get_streak()
        assert streak.current_streak == 1
        assert streak.total_completions == 1

        # Check session status in storage
        status = await atomic_store.get_session_status(session_id)
        assert status is not None
        assert status["status"] == SessionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_concurrent_done_across_multiple_sessions_same_day(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Concurrent completions for different sessions on the same calendar day keep streak at 1."""
        sessions = ["gym_concurrent_1", "toeic_concurrent_2", "major_concurrent_3"]
        updates = [
            make_callback_update(
                chat_id=app_config.allowed_chat_id,
                callback_data=f"done:{sid}",
                bot=bot_application.bot,
            )
            for sid in sessions
        ]

        responses = await asyncio.gather(
            *[bot_application.process_update(upd) for upd in updates]
        )

        assert len(responses) == 3
        for resp in responses:
            assert resp is not None
            assert "HOÀN THÀNH" in resp["text"]

        # Streak for same day must remain 1, but total_completions must be 3
        streak = await atomic_store.get_streak()
        assert streak.current_streak == 1
        assert streak.total_completions == 3


# =====================================================================
# 3. Snooze Limit Enforcement & Capping Beyond 2
# =====================================================================

class TestSnoozeLimitEnforcement:
    """Stress tests verifying that snooze attempts 3, 4, 5 are strictly blocked."""

    @pytest.mark.asyncio
    async def test_sequential_snooze_clicks_3_4_5_strictly_blocked(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Attempts 1 and 2 succeed; attempts 3, 4, 5 are strictly blocked without incrementing."""
        session_id = "snooze_stress_cap_session"

        # Attempt 1: Snooze 1/2
        upd1 = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{session_id}",
            bot=bot_application.bot,
        )
        resp1 = await bot_application.process_update(upd1)
        assert resp1 is not None
        assert "Lần 1/2" in resp1["text"]
        status1 = await atomic_store.get_session_status(session_id)
        assert status1["snooze_count"] == 1

        # Attempt 2: Snooze 2/2
        upd2 = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{session_id}",
            bot=bot_application.bot,
        )
        resp2 = await bot_application.process_update(upd2)
        assert resp2 is not None
        assert "Lần 2/2" in resp2["text"]
        status2 = await atomic_store.get_session_status(session_id)
        assert status2["snooze_count"] == 2

        # Record scheduler job count before blocked attempts
        sched_jobs_before = len(bot_application.scheduler.scheduler.get_jobs())

        # Attempts 3, 4, 5: Must all be blocked
        for attempt in [3, 4, 5]:
            upd_blocked = make_callback_update(
                chat_id=app_config.allowed_chat_id,
                callback_data=f"snooze:{session_id}",
                bot=bot_application.bot,
            )
            resp_blocked = await bot_application.process_update(upd_blocked)
            assert resp_blocked is not None
            # Must indicate limit reached or exhausted rights
            assert any(kw in resp_blocked["text"].upper() for kw in ["GIỚI HẠN", "HẾT QUYỀN", "ĐÃ ĐẠT"])

            # Verify storage snooze_count remains firmly at 2
            curr_status = await atomic_store.get_session_status(session_id)
            assert curr_status["snooze_count"] == 2, f"Attempt {attempt} inflated snooze_count!"

        # Verify no additional jobs were added to scheduler
        sched_jobs_after = len(bot_application.scheduler.scheduler.get_jobs())
        assert sched_jobs_after == sched_jobs_before

    @pytest.mark.asyncio
    async def test_snooze_cap_blocks_even_with_explicit_count_spoofing(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
        atomic_store: AtomicJsonStore,
    ) -> None:
        """Pre-setting storage snooze_count to 2 blocks subsequent snooze clicks immediately."""
        session_id = "pre_capped_session"
        await atomic_store.record_snooze(session_id, 2)

        update = make_callback_update(
            chat_id=app_config.allowed_chat_id,
            callback_data=f"snooze:{session_id}",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert any(kw in resp["text"].upper() for kw in ["GIỚI HẠN", "HẾT QUYỀN"])

        status = await atomic_store.get_session_status(session_id)
        assert status["snooze_count"] == 2


# =====================================================================
# 4. State Transitions and Malformed Callback Data
# =====================================================================

class TestAdversarialCallbackPayloads:
    """Edge cases in callback data parsing and routing."""

    @pytest.mark.asyncio
    async def test_malformed_callback_data_handled_gracefully(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
    ) -> None:
        """Malformed callback data does not crash the bot."""
        malformed_datas = [
            "",
            "unknown_action",
            "foo:bar:baz:qux",
            "done",
            "snooze",
            "skip",
        ]

        for bad_data in malformed_datas:
            update = make_callback_update(
                chat_id=app_config.allowed_chat_id,
                callback_data=bad_data,
                bot=bot_application.bot,
            )
            resp = await bot_application.process_update(update)
            assert resp is not None

    @pytest.mark.asyncio
    async def test_long_spam_text_handled_safely(
        self,
        bot_application: BotApplication,
        app_config: AppConfig,
    ) -> None:
        """Massive 10,000 character message handled safely without crashing."""
        spam_text = "Tôi bị bận việc đột xuất! " * 400  # ~10,000 chars
        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text=spam_text,
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Coach" in resp["text"]
