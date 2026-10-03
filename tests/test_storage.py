"""Unit tests for atomic JSON storage and calendar streak engine (Milestone 1)."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from src.storage import AtomicJsonStore, StreakData


@pytest.mark.asyncio
class TestStorageInitAndDirectory:
    """Verifies directory auto-creation and empty state handling."""

    async def test_auto_create_parent_directory(self, tmp_path: Path):
        nested_file = tmp_path / "deep" / "nested" / "path" / "records.json"
        assert not nested_file.parent.exists()

        AtomicJsonStore(file_path=str(nested_file))
        assert nested_file.parent.exists()

    async def test_load_data_when_file_does_not_exist(self, atomic_store: AtomicJsonStore):
        data = await atomic_store.load_data()
        assert isinstance(data, dict)
        assert "streak" in data
        assert "sessions" in data
        assert data["streak"]["current_streak"] == 0
        assert data["streak"]["best_streak"] == 0
        assert data["streak"]["last_completed_date"] is None
        assert data["streak"]["total_completions"] == 0

    async def test_get_streak_when_file_does_not_exist(self, atomic_store: AtomicJsonStore):
        streak = await atomic_store.get_streak()
        assert isinstance(streak, StreakData)
        assert streak.current_streak == 0
        assert streak.best_streak == 0
        assert streak.last_completed_date is None
        assert streak.total_completions == 0


@pytest.mark.asyncio
class TestAtomicWriteAndCrashSafety:
    """Verifies atomic replace semantics, Windows NTFS compatibility, and crash safety."""

    async def test_atomic_write_creates_valid_file(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        test_payload = {
            "version": 1,
            "streak": {
                "current_streak": 2,
                "best_streak": 2,
                "last_completed_date": "2026-10-02",
                "total_completions": 2,
            },
            "sessions": {"gym_20261002": {"status": "completed"}},
            "active_sessions": {},
            "awaiting_reason": None,
            "history": [],
        }
        await atomic_store.save_data(test_payload)

        assert temp_records_path.exists()
        with open(temp_records_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        assert disk_data == test_payload

    async def test_atomic_write_cleans_up_temporary_files(
        self, atomic_store: AtomicJsonStore, temp_data_dir: Path
    ):
        for i in range(5):
            await atomic_store.save_data(
                {
                    "version": 1,
                    "streak": {
                        "current_streak": i,
                        "best_streak": i,
                        "last_completed_date": None,
                        "total_completions": i,
                    },
                    "sessions": {},
                    "active_sessions": {},
                    "awaiting_reason": None,
                    "history": [],
                }
            )

        # Verify only records.json exists, no leftover .tmp files
        dir_contents = os.listdir(temp_data_dir)
        assert dir_contents == ["records.json"]

    async def test_crash_safety_on_serialization_error(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        initial = {
            "version": 1,
            "streak": {
                "current_streak": 5,
                "best_streak": 10,
                "last_completed_date": "2026-10-01",
                "total_completions": 5,
            },
            "sessions": {},
            "active_sessions": {},
            "awaiting_reason": None,
            "history": [],
        }
        await atomic_store.save_data(initial)

        # Attempt to save non-serializable object (set cannot be serialized to JSON)
        bad_payload = {"streak": {"invalid": set([1, 2, 3])}}
        with pytest.raises((TypeError, ValueError)):
            await atomic_store.save_data(bad_payload)

        # Original data must remain 100% intact
        disk_data = await atomic_store.load_data()
        assert disk_data["streak"]["current_streak"] == 5

    async def test_crash_safety_on_os_replace_failure(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        initial = {
            "version": 1,
            "streak": {
                "current_streak": 3,
                "best_streak": 3,
                "last_completed_date": "2026-10-01",
                "total_completions": 3,
            },
            "sessions": {},
            "active_sessions": {},
            "awaiting_reason": None,
            "history": [],
        }
        await atomic_store.save_data(initial)

        with patch("os.replace", side_effect=OSError("Simulated disk error")):
            with pytest.raises(OSError, match="Simulated disk error"):
                await atomic_store.save_data({"streak": {"current_streak": 99}})

        # Original data untouched
        data = await atomic_store.load_data()
        assert data["streak"]["current_streak"] == 3

    async def test_concurrent_writes_thread_safe(self, atomic_store: AtomicJsonStore):
        async def worker(index: int):
            data = await atomic_store.load_data()
            data["sessions"][f"session_{index}"] = {"status": "completed"}
            await atomic_store.save_data(data)

        # 10 concurrent write tasks
        await asyncio.gather(*(worker(i) for i in range(10)))

        final_data = await atomic_store.load_data()
        assert len(final_data["sessions"]) == 10


@pytest.mark.asyncio
class TestStreakProgression:
    """Verifies calendar streak arithmetic in Asia/Ho_Chi_Minh."""

    async def test_first_ever_session_completion(self, atomic_store: AtomicJsonStore):
        streak = await atomic_store.record_completion(
            session_id="gym_20261001",
            session_type="gym",
            today_str="2026-10-01",
        )
        assert streak.current_streak == 1
        assert streak.best_streak == 1
        assert streak.last_completed_date == "2026-10-01"
        assert streak.total_completions == 1

    async def test_consecutive_days_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("gym_20261001", "gym", "2026-10-01")
        await atomic_store.record_completion("toeic_20261002", "toeic", "2026-10-02")
        streak = await atomic_store.record_completion("major_20261003", "major", "2026-10-03")

        assert streak.current_streak == 3
        assert streak.best_streak == 3
        assert streak.last_completed_date == "2026-10-03"
        assert streak.total_completions == 3

    async def test_multi_session_same_day_idempotency(self, atomic_store: AtomicJsonStore):
        today = "2026-10-03"
        s1 = await atomic_store.record_completion("gym_1", "gym", today)
        assert s1.current_streak == 1
        assert s1.total_completions == 1

        # Second session on same day MUST NOT increment streak
        s2 = await atomic_store.record_completion("toeic_1", "toeic", today)
        assert s2.current_streak == 1
        assert s2.best_streak == 1
        assert s2.total_completions == 2

        # Third session on same day MUST NOT increment streak
        s3 = await atomic_store.record_completion("major_1", "major", today)
        assert s3.current_streak == 1
        assert s3.best_streak == 1
        assert s3.total_completions == 3

    async def test_duplicate_session_completion_idempotency(self, atomic_store: AtomicJsonStore):
        today = "2026-10-03"
        s1 = await atomic_store.record_completion("gym_1", "gym", today)
        # Calling again with exact same session_id
        s2 = await atomic_store.record_completion("gym_1", "gym", today)

        assert s2.current_streak == s1.current_streak
        assert s2.total_completions == s1.total_completions

    async def test_broken_streak_reset_to_one_after_gap(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("gym_1", "gym", "2026-10-01")
        await atomic_store.record_completion("gym_2", "gym", "2026-10-02")
        # 2026-10-03 is missed! Next completion is 2026-10-04
        streak = await atomic_store.record_completion("gym_4", "gym", "2026-10-04")

        assert streak.current_streak == 1  # Reset to 1
        assert streak.best_streak == 2     # Best streak preserved!
        assert streak.last_completed_date == "2026-10-04"
        assert streak.total_completions == 3

    async def test_large_gap_streak_reset(self, atomic_store: AtomicJsonStore):
        data = {
            "version": 1,
            "streak": {
                "current_streak": 10,
                "best_streak": 10,
                "last_completed_date": "2026-08-01",
                "total_completions": 10,
            },
            "sessions": {},
            "active_sessions": {},
            "awaiting_reason": None,
            "history": [],
        }
        await atomic_store.save_data(data)

        # Complete 2 months later
        streak = await atomic_store.record_completion("gym_new", "gym", "2026-10-03")
        assert streak.current_streak == 1
        assert streak.best_streak == 10
        assert streak.last_completed_date == "2026-10-03"
        assert streak.total_completions == 11

    async def test_new_best_streak_record(self, atomic_store: AtomicJsonStore):
        data = {
            "version": 1,
            "streak": {
                "current_streak": 3,
                "best_streak": 3,
                "last_completed_date": "2026-10-02",
                "total_completions": 3,
            },
            "sessions": {},
            "active_sessions": {},
            "awaiting_reason": None,
            "history": [],
        }
        await atomic_store.save_data(data)

        streak = await atomic_store.record_completion("gym_4", "gym", "2026-10-03")
        assert streak.current_streak == 4
        assert streak.best_streak == 4  # Surpassed previous best!

    async def test_month_boundary_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2026-10-31")
        streak = await atomic_store.record_completion("s2", "gym", "2026-11-01")
        assert streak.current_streak == 2

    async def test_year_boundary_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2026-12-31")
        streak = await atomic_store.record_completion("s2", "gym", "2027-01-01")
        assert streak.current_streak == 2

    async def test_leap_year_boundary_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2028-02-28")
        s2 = await atomic_store.record_completion("s2", "gym", "2028-02-29")
        assert s2.current_streak == 2
        s3 = await atomic_store.record_completion("s3", "gym", "2028-03-01")
        assert s3.current_streak == 3

    async def test_effective_streak_expiry(self, atomic_store: AtomicJsonStore):
        streak_data = StreakData(
            current_streak=5,
            best_streak=10,
            last_completed_date="2026-10-01",
            total_completions=15,
        )
        # Same day
        assert streak_data.get_effective_streak("2026-10-01") == 5
        # Next day (still active)
        assert streak_data.get_effective_streak("2026-10-02") == 5
        # 2 days later (expired)
        assert streak_data.get_effective_streak("2026-10-03") == 0


@pytest.mark.asyncio
class TestSessionTracking:
    """Verifies session status lifecycles, snoozes, and skips."""

    async def test_get_session_status_unknown(self, atomic_store: AtomicJsonStore):
        status = await atomic_store.get_session_status("nonexistent_session_id")
        assert status is None

    async def test_record_completion_persists_session(self, atomic_store: AtomicJsonStore):
        session_id = "toeic_20261003"
        await atomic_store.record_completion(session_id, "toeic", "2026-10-03")

        status = await atomic_store.get_session_status(session_id)
        assert status is not None
        assert status["status"] == "completed"
        assert status["session_type"] == "toeic"
        assert status["date"] == "2026-10-03"
        assert "completed_at" in status

    async def test_record_snooze_increments(self, atomic_store: AtomicJsonStore):
        session_id = "major_20261003"

        cnt1 = await atomic_store.record_snooze(session_id, new_count=1)
        assert cnt1 == 1
        st1 = await atomic_store.get_session_status(session_id)
        assert st1["status"] == "snoozed"
        assert st1["snooze_count"] == 1

        cnt2 = await atomic_store.record_snooze(session_id, new_count=2)
        assert cnt2 == 2
        st2 = await atomic_store.get_session_status(session_id)
        assert st2["status"] == "snoozed"
        assert st2["snooze_count"] == 2

    async def test_snooze_then_completed(self, atomic_store: AtomicJsonStore):
        session_id = "gym_20261003"
        await atomic_store.record_snooze(session_id, new_count=2)
        await atomic_store.record_completion(session_id, "gym", "2026-10-03")

        status = await atomic_store.get_session_status(session_id)
        assert status["status"] == "completed"
        assert status["snooze_count"] == 2  # Preserved snooze history

    async def test_record_skip_excuse(self, atomic_store: AtomicJsonStore):
        session_id = "major_20261003"
        reason = "Đang dở ván game Dota 2"
        ts = "2026-10-03T20:50:00+07:00"

        await atomic_store.record_skip(
            session_id, reason=reason, classification="EXCUSE", timestamp_str=ts
        )

        status = await atomic_store.get_session_status(session_id)
        assert status["status"] == "skipped"
        assert status["reason"] == reason
        assert status["classification"] == "EXCUSE"
        assert status["timestamp"] == ts

    async def test_record_skip_legitimate(self, atomic_store: AtomicJsonStore):
        session_id = "gym_20261003"
        reason = "Sốt cao 39.5 độ phải nằm viện"
        ts = "2026-10-03T17:20:00+07:00"

        await atomic_store.record_skip(
            session_id, reason=reason, classification="LEGITIMATE", timestamp_str=ts
        )

        status = await atomic_store.get_session_status(session_id)
        assert status["status"] == "skipped"
        assert status["reason"] == reason
        assert status["classification"] == "LEGITIMATE"

    async def test_skip_does_not_increment_streak(self, atomic_store: AtomicJsonStore):
        data = {
            "version": 1,
            "streak": {
                "current_streak": 4,
                "best_streak": 4,
                "last_completed_date": "2026-10-02",
                "total_completions": 4,
            },
            "sessions": {},
            "active_sessions": {},
            "awaiting_reason": None,
            "history": [],
        }
        await atomic_store.save_data(data)

        # User skips today
        await atomic_store.record_skip(
            "gym_20261003",
            reason="Bệnh",
            classification="LEGITIMATE",
            timestamp_str="2026-10-03T17:20:00+07:00",
        )

        streak = await atomic_store.get_streak()
        assert streak.current_streak == 4  # Did not increment!
        assert streak.last_completed_date == "2026-10-02"  # Last completion date unchanged!

    async def test_multiple_independent_sessions_same_day(self, atomic_store: AtomicJsonStore):
        today = "2026-10-03"
        await atomic_store.record_completion("gym_1", "gym", today)
        await atomic_store.record_snooze("toeic_1", new_count=1)
        await atomic_store.record_skip(
            "major_1",
            reason="Bận đồ án",
            classification="LEGITIMATE",
            timestamp_str="2026-10-03T21:00:00+07:00",
        )

        gym_st = await atomic_store.get_session_status("gym_1")
        toeic_st = await atomic_store.get_session_status("toeic_1")
        major_st = await atomic_store.get_session_status("major_1")

        assert gym_st["status"] == "completed"
        assert toeic_st["status"] == "snoozed"
        assert major_st["status"] == "skipped"

    async def test_awaiting_reason_lifecycle(self, atomic_store: AtomicJsonStore):
        session_id = "gym_await"
        await atomic_store.create_session(session_id, "gym")
        st = await atomic_store.get_session_status(session_id)
        assert st["status"] == "pending"

        await atomic_store.set_awaiting_reason(session_id)
        assert await atomic_store.get_awaiting_reason() == session_id
        st = await atomic_store.get_session_status(session_id)
        assert st["status"] == "awaiting_reason"

        await atomic_store.clear_awaiting_reason()
        assert await atomic_store.get_awaiting_reason() is None

    async def test_get_recent_history(self, atomic_store: AtomicJsonStore):
        for i in range(5):
            await atomic_store.record_completion(f"sess_{i}", "gym", f"2026-10-0{i+1}")

        hist = await atomic_store.get_recent_history(limit=3)
        assert len(hist) == 3
        # Newest first
        assert hist[0]["session_id"] == "sess_4"


@pytest.mark.asyncio
class TestDataCorruptionRecovery:
    """Verifies store behavior upon encountering invalid or corrupt storage files."""

    async def test_empty_file_recovery(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        temp_records_path.write_text("", encoding="utf-8")
        data = await atomic_store.load_data()
        assert data["streak"]["current_streak"] == 0

    async def test_corrupted_json_syntax_recovery(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        temp_records_path.write_text("{bad_json_not_valid", encoding="utf-8")
        data = await atomic_store.load_data()
        assert data["streak"]["current_streak"] == 0

    async def test_store_reset(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2026-10-01")
        assert (await atomic_store.get_streak()).current_streak == 1
        await atomic_store.reset()
        assert (await atomic_store.get_streak()).current_streak == 0

    async def test_out_of_order_date_streak_handling(self, atomic_store: AtomicJsonStore):
        # Complete on 2026-10-05, then later record an old session on 2026-10-02
        await atomic_store.record_completion("s2", "gym", "2026-10-05")
        streak = await atomic_store.record_completion("s1", "gym", "2026-10-02")
        # Streak should not regress or break
        assert streak.current_streak == 1
        assert streak.last_completed_date == "2026-10-05"
        assert streak.total_completions == 2

