"""Empirical Adversarial and Stress Tests for Milestone 1.

Written by teamwork_preview_challenger to empirically verify:
1. High concurrency writes and thread/coroutine safety of AtomicJsonStore.
2. Crash safety, failure injection during dump/fsync/replace, and corruption recovery.
3. Calendar streak calculation across leap years, year rollovers, timezone boundaries,
   same-day bursts, out-of-order dates, and effective streak expiry.
4. Edge case payloads and non-dict JSON recovery.
"""

from __future__ import annotations

import asyncio
import copy
from datetime import date, datetime, timedelta
import json
import os
import shutil
import tempfile
from typing import List
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.storage import (
    AtomicJsonStore,
    DEFAULT_DATA,
    HO_CHI_MINH_TZ,
    SessionStatus,
    StreakData,
)
from src.config import (
    AppConfig,
    load_config,
    validate_time_format,
)


@pytest.fixture
def stress_store_dir():
    temp_dir = tempfile.mkdtemp(prefix="coach_stress_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def stress_store(stress_store_dir) -> AtomicJsonStore:
    file_path = os.path.join(stress_store_dir, "records.json")
    return AtomicJsonStore(file_path)


# =====================================================================
# 1. HIGH CONCURRENCY STRESS TESTS
# =====================================================================

@pytest.mark.asyncio
class TestHighConcurrencyStress:
    """Empirically stress-tests AtomicJsonStore under high concurrency."""

    async def test_100_concurrent_completions_same_day(self, stress_store: AtomicJsonStore):
        """100 distinct sessions completing simultaneously on the same calendar day."""
        today = "2026-10-03"

        async def worker(idx: int):
            return await stress_store.record_completion(
                session_id=f"session_burst_{idx}",
                session_type="gym" if idx % 2 == 0 else "toeic",
                today_str=today,
            )

        results = await asyncio.gather(*(worker(i) for i in range(100)))

        # Verify all 100 completed without throwing
        assert len(results) == 100

        data = await stress_store.load_data()
        assert len(data["sessions"]) == 100
        assert data["streak"]["total_completions"] == 100
        # Same day: streak should be 1
        assert data["streak"]["current_streak"] == 1
        assert data["streak"]["best_streak"] == 1
        assert len(data["history"]) == 100

    async def test_100_concurrent_mixed_operations(self, stress_store: AtomicJsonStore):
        """100 concurrent tasks performing mixed completions, snoozes, skips, and reads."""
        today = "2026-10-03"

        async def completion_worker(idx: int):
            return await stress_store.record_completion(
                session_id=f"mixed_comp_{idx}",
                session_type="gym",
                today_str=today,
            )

        async def snooze_worker(idx: int):
            return await stress_store.record_snooze(
                session_id=f"mixed_snooze_{idx}",
                new_count=1,
            )

        async def skip_worker(idx: int):
            return await stress_store.record_skip(
                session_id=f"mixed_skip_{idx}",
                reason="Too tired",
                classification="EXCUSE",
                timestamp_str="2026-10-03T20:00:00+07:00",
            )

        async def read_worker():
            return await stress_store.get_streak()

        tasks = []
        for i in range(40):
            tasks.append(completion_worker(i))
        for i in range(30):
            tasks.append(snooze_worker(i))
        for i in range(30):
            tasks.append(skip_worker(i))
        for _ in range(20):
            tasks.append(read_worker())

        # Execute all 120 operations simultaneously
        await asyncio.gather(*tasks)

        data = await stress_store.load_data()
        # Verify 40 completed, 30 snoozed, 30 skipped = 100 sessions total
        assert len(data["sessions"]) == 100
        assert data["streak"]["total_completions"] == 40
        assert len(data["history"]) == 100

    async def test_multi_instance_file_safety(self, stress_store_dir: str):
        """Multiple independent AtomicJsonStore instances pointing to same file sequentially and concurrently."""
        file_path = os.path.join(stress_store_dir, "records.json")

        store1 = AtomicJsonStore(file_path)
        store2 = AtomicJsonStore(file_path)

        # Sequential cross-instance writes
        await store1.record_completion("inst1_s1", "gym", "2026-10-01")
        await store2.record_completion("inst2_s1", "toeic", "2026-10-02")

        streak = await store1.get_streak()
        assert streak.current_streak == 2
        assert streak.total_completions == 2

        # Verify both sessions present in store2
        s1 = await store2.get_session_status("inst1_s1")
        s2 = await store2.get_session_status("inst2_s1")
        assert s1 is not None and s1["status"] == SessionStatus.COMPLETED
        assert s2 is not None and s2["status"] == SessionStatus.COMPLETED


# =====================================================================
# 2. ATOMIC CRASH RESISTANCE & FAILURE INJECTION
# =====================================================================

@pytest.mark.asyncio
class TestFailureInjectionAndCrashSafety:
    """Verifies crash-safety when failures occur at various stages of write/replace."""

    async def test_failure_during_json_dump_preserves_target_file(self, stress_store: AtomicJsonStore):
        """Simulate serialization failure during json.dump: existing records.json must NOT be corrupted."""
        # Establish valid state
        await stress_store.record_completion("valid_1", "gym", "2026-10-01")
        initial_data = await stress_store.load_data()
        assert initial_data["streak"]["total_completions"] == 1

        # Simulate dump failure
        with patch("json.dump", side_effect=TypeError("Unserializable object")):
            with pytest.raises(TypeError, match="Unserializable object"):
                await stress_store.save_data({"unserializable": object()})

        # Verify original file untouched
        data_after = await stress_store.load_data()
        assert data_after["streak"]["total_completions"] == 1
        assert "valid_1" in data_after["sessions"]

        # Verify no orphaned temp files
        tmp_files = [f for f in os.listdir(stress_store.dir_name) if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    async def test_failure_during_fsync_preserves_target_file(self, stress_store: AtomicJsonStore):
        """Simulate disk I/O error during os.fsync: existing file must remain untouched."""
        await stress_store.record_completion("valid_1", "gym", "2026-10-01")

        with patch("os.fsync", side_effect=OSError("Disk write error")):
            with pytest.raises(OSError, match="Disk write error"):
                await stress_store.record_completion("valid_2", "toeic", "2026-10-02")

        data_after = await stress_store.load_data()
        assert data_after["streak"]["total_completions"] == 1
        assert "valid_2" not in data_after["sessions"]

        tmp_files = [f for f in os.listdir(stress_store.dir_name) if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    async def test_failure_during_os_replace_preserves_target_file(self, stress_store: AtomicJsonStore):
        """Simulate PermissionError (e.g. Windows file lock) during os.replace."""
        await stress_store.record_completion("valid_1", "gym", "2026-10-01")

        with patch("os.replace", side_effect=PermissionError("WinError 32: Access Denied")):
            with pytest.raises(PermissionError, match="WinError 32"):
                await stress_store.record_snooze("valid_1", 1)

        # File is intact
        data_after = await stress_store.load_data()
        assert data_after["sessions"]["valid_1"]["status"] == SessionStatus.COMPLETED

        tmp_files = [f for f in os.listdir(stress_store.dir_name) if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    async def test_corruption_recovery_on_truncated_json(self, stress_store: AtomicJsonStore):
        """Truncated/half-written JSON file is backed up and store is re-initialized to defaults."""
        await stress_store.record_completion("valid_1", "gym", "2026-10-01")

        # Truncate file halfway
        with open(stress_store.file_path, "w", encoding="utf-8") as f:
            f.write('{"streak": {"current_streak": 1, "best_streak":')

        # load_data should recover gracefully
        data = await stress_store.load_data()
        assert data["streak"]["current_streak"] == 0
        assert data["streak"]["total_completions"] == 0

        # Verify a corrupt backup file was created
        corrupt_backups = [f for f in os.listdir(stress_store.dir_name) if ".corrupt." in f]
        assert len(corrupt_backups) == 1

    async def test_corruption_recovery_on_binary_garbage(self, stress_store: AtomicJsonStore):
        """Binary garbage file is backed up and store recovers."""
        with open(stress_store.file_path, "wb") as f:
            f.write(b"\x00\xff\xfe\x00\xaa\xbb\xcc\xdd")

        data = await stress_store.load_data()
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0

        corrupt_backups = [f for f in os.listdir(stress_store.dir_name) if ".corrupt." in f]
        assert len(corrupt_backups) == 1

    async def test_corruption_recovery_on_json_array_root(self, stress_store: AtomicJsonStore):
        """JSON array root [] should recover gracefully to DEFAULT_DATA dict."""
        with open(stress_store.file_path, "w", encoding="utf-8") as f:
            f.write("[]")

        data = await stress_store.load_data()
        assert isinstance(data, dict)
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0

    async def test_corruption_recovery_on_json_null_root(self, stress_store: AtomicJsonStore):
        """JSON null root should recover gracefully to DEFAULT_DATA dict."""
        with open(stress_store.file_path, "w", encoding="utf-8") as f:
            f.write("null")

        data = await stress_store.load_data()
        assert isinstance(data, dict)
        assert data["version"] == 1

    async def test_corruption_recovery_on_json_number_root(self, stress_store: AtomicJsonStore):
        """JSON number root 12345 should recover gracefully to DEFAULT_DATA dict."""
        with open(stress_store.file_path, "w", encoding="utf-8") as f:
            f.write("12345")

        data = await stress_store.load_data()
        assert isinstance(data, dict)
        assert data["version"] == 1


# =====================================================================
# 3. CALENDAR STREAK ENGINE STRESS & EDGE CASES
# =====================================================================

@pytest.mark.asyncio
class TestCalendarStreakEngineStress:
    """Exhaustively stress-tests calendar streak progression across edge dates and timezones."""

    async def test_365_days_continuous_progression(self, stress_store: AtomicJsonStore):
        """Simulate a full 365-day continuous streak through all month boundaries."""
        start_date = date(2025, 1, 1)
        for day_offset in range(365):
            curr_date = start_date + timedelta(days=day_offset)
            date_str = curr_date.isoformat()
            res = await stress_store.record_completion(
                session_id=f"sess_{date_str}",
                session_type="gym",
                today_str=date_str,
            )
            assert res.current_streak == day_offset + 1
            assert res.best_streak == day_offset + 1
            assert res.total_completions == day_offset + 1

        final_streak = await stress_store.get_streak()
        assert final_streak.current_streak == 365
        assert final_streak.best_streak == 365
        assert final_streak.total_completions == 365

    async def test_leap_year_transition_progression(self, stress_store: AtomicJsonStore):
        """2024 is a leap year: Feb 28 -> Feb 29 -> Mar 01 must increment consecutively."""
        dates = ["2024-02-28", "2024-02-29", "2024-03-01"]
        for i, d in enumerate(dates):
            res = await stress_store.record_completion(f"leap_{i}", "toeic", d)
            assert res.current_streak == i + 1
            assert res.best_streak == i + 1

    async def test_non_leap_year_transition_progression(self, stress_store: AtomicJsonStore):
        """2025 is not a leap year: Feb 28 -> Mar 01 must increment consecutively."""
        dates = ["2025-02-28", "2025-03-01"]
        for i, d in enumerate(dates):
            res = await stress_store.record_completion(f"non_leap_{i}", "toeic", d)
            assert res.current_streak == i + 1
            assert res.best_streak == i + 1

    async def test_year_boundary_transition_progression(self, stress_store: AtomicJsonStore):
        """Dec 31 -> Jan 01 year rollover."""
        dates = ["2025-12-30", "2025-12-31", "2026-01-01", "2026-01-02"]
        for i, d in enumerate(dates):
            res = await stress_store.record_completion(f"yr_{i}", "major", d)
            assert res.current_streak == i + 1
            assert res.best_streak == i + 1

    async def test_multiple_gap_streak_resets_preserve_all_time_best(self, stress_store: AtomicJsonStore):
        """Build streak to 10, miss 2 days (reset to 1), build to 5, miss 10 days, build to 15 (new best)."""
        # Run 1: 10 days
        base = date(2026, 1, 1)
        for i in range(10):
            d = (base + timedelta(days=i)).isoformat()
            await stress_store.record_completion(f"r1_{i}", "gym", d)

        s = await stress_store.get_streak()
        assert s.current_streak == 10
        assert s.best_streak == 10

        # Gap of 2 days: Jan 10 -> Jan 13 (missed Jan 11 & Jan 12)
        res = await stress_store.record_completion("r2_0", "gym", "2026-01-13")
        assert res.current_streak == 1
        assert res.best_streak == 10  # Preserved

        # Run 2: 4 more days (total 5)
        for i in range(1, 5):
            d = (date(2026, 1, 13) + timedelta(days=i)).isoformat()
            res = await stress_store.record_completion(f"r2_{i}", "gym", d)
        assert res.current_streak == 5
        assert res.best_streak == 10

        # Gap of 10 days
        res = await stress_store.record_completion("r3_0", "gym", "2026-02-01")
        assert res.current_streak == 1
        assert res.best_streak == 10

        # Run 3: 15 days (Jan 01 + 15 -> passes old best of 10)
        for i in range(1, 15):
            d = (date(2026, 2, 1) + timedelta(days=i)).isoformat()
            res = await stress_store.record_completion(f"r3_{i}", "gym", d)

        assert res.current_streak == 15
        assert res.best_streak == 15

    async def test_out_of_order_past_date_completion_does_not_corrupt_streak(self, stress_store: AtomicJsonStore):
        """Late arrival / out-of-order date does not regress current streak or last_completed_date."""
        await stress_store.record_completion("s1", "gym", "2026-05-10")
        await stress_store.record_completion("s2", "gym", "2026-05-11")
        await stress_store.record_completion("s3", "gym", "2026-05-12")

        streak_before = await stress_store.get_streak()
        assert streak_before.current_streak == 3
        assert streak_before.last_completed_date == "2026-05-12"
        assert streak_before.total_completions == 3

        # Late submission for 2026-05-08
        res = await stress_store.record_completion("late_s", "gym", "2026-05-08")
        assert res.current_streak == 3
        assert res.last_completed_date == "2026-05-12"
        assert res.total_completions == 4

    async def test_timezone_midnight_boundary_behavior(self, stress_store: AtomicJsonStore):
        """Simulate completions across Ho Chi Minh midnight (+07:00).
        23:59:59 (Day 1) -> 00:00:01 (Day 2) must increment streak.
        """
        # UTC 2026-10-03T16:59:59Z is Vietnam 2026-10-03T23:59:59+07:00 -> Date: 2026-10-03
        t1 = datetime(2026, 10, 3, 23, 59, 59, tzinfo=HO_CHI_MINH_TZ)
        date1 = t1.strftime("%Y-%m-%d")
        res1 = await stress_store.record_completion("t1", "gym", today_str=date1)
        assert res1.current_streak == 1

        # UTC 2026-10-03T17:00:01Z is Vietnam 2026-10-04T00:00:01+07:00 -> Date: 2026-10-04
        t2 = datetime(2026, 10, 4, 0, 0, 1, tzinfo=HO_CHI_MINH_TZ)
        date2 = t2.strftime("%Y-%m-%d")
        res2 = await stress_store.record_completion("t2", "gym", today_str=date2)
        assert res2.current_streak == 2

    async def test_streak_data_effective_streak_comprehensive(self):
        """Test all boundary conditions for StreakData.get_effective_streak."""
        # None last_completed_date
        s0 = StreakData(current_streak=5, best_streak=5, last_completed_date=None, total_completions=5)
        assert s0.get_effective_streak("2026-10-03") == 0

        # 0 current_streak
        s1 = StreakData(current_streak=0, best_streak=5, last_completed_date="2026-10-02", total_completions=5)
        assert s1.get_effective_streak("2026-10-03") == 0

        # Completed today (delta = 0)
        s2 = StreakData(current_streak=5, best_streak=5, last_completed_date="2026-10-03", total_completions=5)
        assert s2.get_effective_streak("2026-10-03") == 5

        # Completed yesterday (delta = 1) -> active today until midnight
        s3 = StreakData(current_streak=5, best_streak=5, last_completed_date="2026-10-02", total_completions=5)
        assert s3.get_effective_streak("2026-10-03") == 5

        # Completed 2 days ago (delta = 2) -> expired
        s4 = StreakData(current_streak=5, best_streak=5, last_completed_date="2026-10-01", total_completions=5)
        assert s4.get_effective_streak("2026-10-03") == 0

        # Completed 30 days ago (delta = 30) -> expired
        s5 = StreakData(current_streak=5, best_streak=5, last_completed_date="2026-09-03", total_completions=5)
        assert s5.get_effective_streak("2026-10-03") == 0

        # Malformed today_str -> fallback to self.current_streak
        s6 = StreakData(current_streak=5, best_streak=5, last_completed_date="2026-10-03", total_completions=5)
        assert s6.get_effective_streak("not-a-date") == 5


# =====================================================================
# 4. CONFIG ADVERSARIAL STRESS
# =====================================================================

class TestConfigAdversarial:
    """Stress tests config parsing against hostile or edge inputs."""

    def test_extreme_time_values(self):
        with pytest.raises(ValueError, match="Hour must be 0-23"):
            validate_time_format("24:00", "test")
        with pytest.raises(ValueError, match="Hour must be 0-23"):
            validate_time_format("25:00", "test")
        with pytest.raises(ValueError, match="minute 0-59"):
            validate_time_format("12:60", "test")
        with pytest.raises(ValueError):
            validate_time_format("-1:00", "test")
        with pytest.raises(ValueError):
            validate_time_format("12:00:00", "test")

    def test_non_string_time(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_time_format(1715, "test")

    def test_empty_string_time(self):
        with pytest.raises(ValueError):
            validate_time_format("", "test")
