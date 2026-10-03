"""Tier 2 E2E Test Suite: Boundary & Corner Cases.

Tests boundary limits, extreme inputs, Unicode, null characters, rapid clicks,
midnight crossovers, and adversarial edge cases with zero network dependencies.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict
import pytest

from src.config import AppConfig
from src.storage import AtomicJsonStore, SessionStatus
from tests.mock_services import (
    MockTelegramBot,
    make_text_update,
    make_callback_update,
)


class TestTier2BoundariesAndCornerCases:
    """Verifies edge conditions, input stress, and boundary handling across all subsystems."""

    @pytest.mark.asyncio
    async def test_t2_whitelist_boundary_chat_ids(
        self, bot_application: Any, app_config: AppConfig
    ) -> None:
        """Adversarial Chat IDs (0, negative, off-by-one) are strictly rejected."""
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
            assert any(term in resp["text"].lower() for term in ["từ chối", "access denied", "ủy quyền"])

    @pytest.mark.asyncio
    async def test_t2_snooze_limit_hard_boundary(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Snooze count progression: 0 -> 1 -> 2 (cap) -> 3 (rejected) -> 4 (rejected)."""
        sid = "t2_boundary_snooze"

        # Attempt 1 (Snooze 1)
        up1 = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot
        )
        r1 = await bot_application.process_update(up1)
        assert "Lần 1/2" in r1["text"] or "15 PHÚT" in r1["text"]
        s1 = await atomic_store.get_session_status(sid)
        assert s1["snooze_count"] == 1

        # Attempt 2 (Snooze 2)
        up2 = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot
        )
        r2 = await bot_application.process_update(up2)
        assert "Lần 2/2" in r2["text"]
        s2 = await atomic_store.get_session_status(sid)
        assert s2["snooze_count"] == 2

        # Attempt 3 (Snooze 3 -> Must be rejected)
        up3 = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot
        )
        r3 = await bot_application.process_update(up3)
        assert "HẾT QUYỀN" in r3["text"] or "GIỚI HẠN" in r3["text"]
        s3 = await atomic_store.get_session_status(sid)
        assert s3["snooze_count"] == 2  # Remains capped at 2

        # Attempt 4 (Snooze 4 -> Still rejected)
        up4 = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"snooze:{sid}", bot=bot_application.bot
        )
        r4 = await bot_application.process_update(up4)
        assert "HẾT QUYỀN" in r4["text"] or "GIỚI HẠN" in r4["text"]
        s4 = await atomic_store.get_session_status(sid)
        assert s4["snooze_count"] == 2

    @pytest.mark.asyncio
    async def test_t2_reason_empty_or_whitespace_handling(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Empty or whitespace-only skip justifications are treated safely as excuses."""
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": "sess_empty", "session_type": "gym"}
        await atomic_store.save_data(data)

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text="     \n\t   ",
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "BAO BIỆN" in resp["text"] or "MICRO-HABIT" in resp["text"] or "Coach" in resp["text"]

    @pytest.mark.asyncio
    async def test_t2_reason_unicode_and_vietnamese_diacritics(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Complex Vietnamese diacritics and accented characters are processed without corruption."""
        sid = "t2_unicode_sess"
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": sid, "session_type": "toeic"}
        await atomic_store.save_data(data)

        reason = "Em bị sốt xuất huyết 39.5 độ, chóng mặt buồn nôn, bác sĩ chỉ định nhập viện cấp cứu!"
        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text=reason,
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "CHÍNH ĐÁNG" in resp["text"] or "nghỉ" in resp["text"].lower()

        status = await atomic_store.get_session_status(sid)
        assert status is not None
        assert status["reason"] == reason
        assert status["classification"] == "LEGITIMATE"

    @pytest.mark.asyncio
    async def test_t2_reason_markdown_and_special_character_injection(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Markdown injection, HTML tags, and SQL meta-characters do not crash the bot."""
        sid = "t2_injection_sess"
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": sid, "session_type": "major"}
        await atomic_store.save_data(data)

        malicious_input = "*bold* _italic_ `code` ```python\nprint('hello')``` <script>alert('xss')</script> ' OR '1'='1"
        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text=malicious_input,
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        # Verify persistence didn't corrupt
        status = await atomic_store.get_session_status(sid)
        assert status is not None
        assert status["reason"] == malicious_input

    @pytest.mark.asyncio
    async def test_t2_reason_extreme_large_text(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Very long justification (10,000 characters) is handled gracefully without crash."""
        sid = "t2_huge_text_sess"
        data = await atomic_store.load_data()
        data["awaiting_reason"] = {"session_id": sid, "session_type": "major"}
        await atomic_store.save_data(data)

        huge_text = "Lý do: " + ("Em bận fix bug game engine " * 400)
        assert len(huge_text) > 8000

        update = make_text_update(
            chat_id=app_config.allowed_chat_id,
            text=huge_text,
            bot=bot_application.bot,
        )
        resp = await bot_application.process_update(update)
        assert resp is not None
        assert "Coach" in resp["text"] or "BAO BIỆN" in resp["text"] or "MICRO-HABIT" in resp["text"]

    @pytest.mark.asyncio
    async def test_t2_sliding_window_overflow_boundary(self, coach_service: Any) -> None:
        """Adding 30 messages to sliding context window strictly caps at 10 items."""
        coach_service.clear_context()
        for i in range(30):
            await coach_service.chat(f"Prompt test {i}")
        assert len(coach_service.context_window) <= 10
        # Oldest prompts must have been pruned
        recent_texts = [msg for role, msg in coach_service.context_window]
        assert any("29" in t for t in recent_texts)
        assert not any("Prompt test 0" in t for t in recent_texts)

    @pytest.mark.asyncio
    async def test_t2_duplicate_rapid_clicks_idempotency(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Clicking Done multiple times for the same session does not artificially inflate streak."""
        sid = "t2_duplicate_click_sess"
        up = make_callback_update(
            chat_id=app_config.allowed_chat_id, callback_data=f"done:{sid}", bot=bot_application.bot
        )

        # 5 consecutive clicks
        for _ in range(5):
            await bot_application.process_update(up)

        streak = await atomic_store.get_streak()
        assert streak.current_streak == 1
        assert streak.total_completions == 1

    @pytest.mark.asyncio
    async def test_t2_unauthorized_user_inline_callback_rejection(
        self, bot_application: Any, app_config: AppConfig, atomic_store: AtomicJsonStore
    ) -> None:
        """Unauthorized user attempting to click inline buttons has callbacks rejected."""
        unauthorized_id = 888888888
        assert unauthorized_id != app_config.allowed_chat_id

        for action in ["done:t2_hack", "snooze:t2_hack", "skip:t2_hack"]:
            cb_update = make_callback_update(
                chat_id=unauthorized_id,
                callback_data=action,
                bot=bot_application.bot,
            )
            resp = await bot_application.process_update(cb_update)
            # Should not record any status in storage
            status = await atomic_store.get_session_status("t2_hack")
            assert status is None

    @pytest.mark.asyncio
    async def test_t2_midnight_rollover_streak_continuity(
        self, atomic_store: AtomicJsonStore
    ) -> None:
        """Completions across 23:59:59 (Day N) and 00:00:01 (Day N+1) advance streak cleanly."""
        day1 = "2026-10-15"
        day2 = "2026-10-16"

        s1 = await atomic_store.record_completion("ses_d1", "gym", day1)
        assert s1.current_streak == 1

        s2 = await atomic_store.record_completion("ses_d2", "toeic", day2)
        assert s2.current_streak == 2
        assert s2.last_completed_date == day2
