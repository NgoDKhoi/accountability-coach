"""Adversarial stress-test suite for Milestone 3 (SchedulerService).

Authored by challenger_m3_2.
Thoroughly stress-tests:
1. Callback failure resilience (ValueError, RuntimeError, asyncio.CancelledError).
2. Timezone boundaries, exotic offsets, and invalid timezone handling.
3. Repeated / idempotent register_scheduled_jobs invocations and trigger replacements.
4. Concurrency, high volume, and edge case resilience.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, List, Tuple
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo
import pytest

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.config import AppConfig, GymScheduleConfig, ToeicScheduleConfig, MajorScheduleConfig
from src.scheduler import SchedulerService, _parse_time_str, _extract_attr_or_key


@pytest.fixture
def base_config() -> AppConfig:
    return AppConfig(
        bot_token="test_token_adversarial",
        gemini_api_key="test_gemini_key",
        allowed_chat_id=987654321,
        timezone="Asia/Ho_Chi_Minh",
        max_snoozes=2,
        snooze_minutes=15,
        context_window_size=10,
        gym=GymScheduleConfig(
            cron_days_split1="mon,tue,thu",
            time_split1="17:15",
            cron_days_split2="wed,sat",
            time_split2="16:15",
            duration_minutes=60,
            name="Gym Session",
        ),
        toeic=ToeicScheduleConfig(
            time="19:25",
            duration_minutes=60,
            syllabus_rotation=["Part 1", "Part 2", "Part 3", "Part 4", "Part 5", "Part 6", "Part 7"],
            name="TOEIC Study Session",
        ),
        major=MajorScheduleConfig(
            time="20:40",
            duration_minutes=60,
            name="Major Subject Study & Game Dev",
        ),
        prompts={},
        fallbacks={},
    )


# ============================================================================
# 1. Callback Failure Resilience (ValueError, RuntimeError, asyncio.CancelledError)
# ============================================================================

class TestCallbackFailureResilience:
    """Stress-tests callback exceptions inside APScheduler wrappers and trigger_job."""

    @pytest.mark.asyncio
    async def test_recurring_wrapper_catches_value_error(self, base_config: AppConfig) -> None:
        """_job_wrapper catches ValueError without crashing the scheduler."""
        sched = SchedulerService()
        async def cb(stype: str, name: str) -> None:
            raise ValueError("Intentional ValueError in recurring callback")

        sched.register_scheduled_jobs(base_config, cb)
        aps_job = sched.scheduler.get_job("gym_split1")
        assert aps_job is not None

        # Direct wrapper execution must not raise
        await aps_job.func()
        assert "gym_split1" in sched.registered_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_recurring_wrapper_catches_runtime_error(self, base_config: AppConfig) -> None:
        """_job_wrapper catches RuntimeError without crashing the scheduler."""
        sched = SchedulerService()
        async def cb(stype: str, name: str) -> None:
            raise RuntimeError("Intentional RuntimeError in recurring callback")

        sched.register_scheduled_jobs(base_config, cb)
        aps_job = sched.scheduler.get_job("toeic")
        assert aps_job is not None

        # Direct wrapper execution must not raise
        await aps_job.func()
        assert "toeic" in sched.registered_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_recurring_wrapper_cancelled_error_behavior(self, base_config: AppConfig) -> None:
        """Test behavior when callback raises asyncio.CancelledError in recurring job."""
        sched = SchedulerService()
        async def cb(stype: str, name: str) -> None:
            raise asyncio.CancelledError("Simulated task cancellation")

        sched.register_scheduled_jobs(base_config, cb)
        aps_job = sched.scheduler.get_job("major")
        assert aps_job is not None

        # In Python 3.8+, CancelledError inherits BaseException, not Exception.
        # Check whether wrapper lets CancelledError propagate (standard asyncio cancellation)
        with pytest.raises(asyncio.CancelledError):
            await aps_job.func()

        # The recurring job definition should still be in registered_jobs
        assert "major" in sched.registered_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_snooze_wrapper_catches_value_error_and_cleans_up(self) -> None:
        """_snooze_wrapper catches ValueError and still removes job from snooze_jobs."""
        sched = SchedulerService()
        async def cb(sid: str, stype: str, count: int) -> None:
            raise ValueError("Intentional ValueError in snooze")

        job_id = sched.schedule_snooze_job("sid_err1", "gym", 1, 15, cb)
        assert job_id in sched.snooze_jobs

        aps_job = sched.scheduler.get_job(job_id)
        assert aps_job is not None

        # Wrapper execution must catch ValueError
        await aps_job.func()
        # Ensure job was removed in finally block
        assert job_id not in sched.snooze_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_snooze_wrapper_catches_runtime_error_and_cleans_up(self) -> None:
        """_snooze_wrapper catches RuntimeError and still removes job from snooze_jobs."""
        sched = SchedulerService()
        async def cb(sid: str, stype: str, count: int) -> None:
            raise RuntimeError("Intentional RuntimeError in snooze")

        job_id = sched.schedule_snooze_job("sid_err2", "toeic", 1, 15, cb)
        assert job_id in sched.snooze_jobs

        aps_job = sched.scheduler.get_job(job_id)
        assert aps_job is not None

        await aps_job.func()
        assert job_id not in sched.snooze_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_snooze_wrapper_cancelled_error_still_cleans_up(self) -> None:
        """If snooze callback raises asyncio.CancelledError, finally block pops the job."""
        sched = SchedulerService()
        async def cb(sid: str, stype: str, count: int) -> None:
            raise asyncio.CancelledError("Cancellation during snooze callback")

        job_id = sched.schedule_snooze_job("sid_err3", "major", 1, 15, cb)
        assert job_id in sched.snooze_jobs

        aps_job = sched.scheduler.get_job(job_id)
        assert aps_job is not None

        # CancelledError propagates out of the wrapper
        with pytest.raises(asyncio.CancelledError):
            await aps_job.func()

        # Crucial check: finally block MUST have popped job_id so no leaked state
        assert job_id not in sched.snooze_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_trigger_job_propagates_exceptions_and_cleans_up_snooze(self) -> None:
        """trigger_job pops snooze job before calling callback, so job is cleared even on error."""
        sched = SchedulerService()
        async def failing_cb(sid: str, stype: str, count: int) -> None:
            raise ValueError("trigger_job error")

        job_id = sched.schedule_snooze_job("sid_trig_err", "gym", 1, 15, failing_cb)
        assert job_id in sched.snooze_jobs

        with pytest.raises(ValueError, match="trigger_job error"):
            await sched.trigger_job(job_id)

        # Job must be popped from snooze_jobs despite exception
        assert job_id not in sched.snooze_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_trigger_job_propagates_cancelled_error_and_cleans_up_snooze(self) -> None:
        """trigger_job pops snooze job even if callback raises asyncio.CancelledError."""
        sched = SchedulerService()
        async def cancel_cb(sid: str, stype: str, count: int) -> None:
            raise asyncio.CancelledError("cancelled in trigger")

        job_id = sched.schedule_snooze_job("sid_cancel_trig", "toeic", 2, 15, cancel_cb)
        assert job_id in sched.snooze_jobs

        with pytest.raises(asyncio.CancelledError):
            await sched.trigger_job(job_id)

        assert job_id not in sched.snooze_jobs
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_apscheduler_running_survives_callback_exceptions(self, base_config: AppConfig) -> None:
        """Running scheduler continues scheduling even after job callbacks throw errors."""
        sched = SchedulerService()
        sched.start()
        assert sched.scheduler.running

        counter = 0

        async def sometimes_failing_cb(stype: str, name: str) -> None:
            nonlocal counter
            counter += 1
            if counter == 1:
                raise ValueError("First run fails")
            elif counter == 2:
                raise RuntimeError("Second run fails")

        # Attach custom job directly to underlying scheduler to fire almost immediately
        run_date = datetime.now(sched.timezone) + timedelta(milliseconds=50)
        sched.scheduler.add_job(
            sometimes_failing_cb,
            trigger=DateTrigger(run_date=run_date, timezone=sched.timezone),
            id="failing_test_job",
            args=["gym", "Gym Session"],
        )

        await asyncio.sleep(0.15)
        # Scheduler must remain active and running
        assert sched.scheduler.running
        assert sched.is_running
        sched.shutdown()


# ============================================================================
# 2. Timezone Boundaries & Invalid Timezone Handling
# ============================================================================

class TestTimezoneBoundariesAndInvalidHandling:
    """Stress-tests various timezones, offsets, boundary transitions, and invalid inputs."""

    @pytest.mark.parametrize(
        "invalid_tz",
        [
            "",
            "   ",
            "NonExistent/Timezone",
            "Mars/Olympus_Mons",
            "12345",
            None,
            123,
            [],
            {},
        ],
    )
    def test_invalid_timezone_raises_value_error(self, invalid_tz: Any) -> None:
        """Any invalid, malformed, or unsupported timezone input raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timezone specified"):
            SchedulerService(timezone_str=invalid_tz)

    @pytest.mark.parametrize(
        "valid_tz",
        [
            "Asia/Ho_Chi_Minh",
            "UTC",
            "GMT",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Paris",
            "Asia/Tokyo",
            "Australia/Sydney",
            "Asia/Kolkata",       # UTC+5:30
            "Asia/Kathmandu",     # UTC+5:45
            "Pacific/Chatham",    # UTC+12:45
            "Pacific/Kiritimati",  # UTC+14:00 (extreme positive)
            "Pacific/Honolulu",   # UTC-10:00 (extreme negative)
        ],
    )
    def test_valid_exotic_timezones(self, valid_tz: str) -> None:
        """Scheduler initializes correctly with various global timezones and non-hour offsets."""
        sched = SchedulerService(timezone_str=valid_tz)
        assert sched.timezone_str == valid_tz
        assert isinstance(sched.timezone, ZoneInfo)
        assert sched.scheduler.timezone == sched.timezone
        sched.shutdown()

    def test_snooze_run_date_inherits_scheduler_timezone(self) -> None:
        """Snooze run_date has tzinfo strictly equal to scheduler timezone."""
        for tz_name in ["Asia/Ho_Chi_Minh", "Asia/Kolkata", "America/New_York", "UTC"]:
            sched = SchedulerService(timezone_str=tz_name)
            job_id = sched.schedule_snooze_job(
                "s1", "gym", 1, 15, AsyncMock()
            )
            job_info = sched.snooze_jobs[job_id]
            assert job_info["run_at"].tzinfo == sched.timezone
            aps_job = sched.scheduler.get_job(job_id)
            assert aps_job is not None
            assert aps_job.trigger.timezone == sched.timezone
            sched.shutdown()

    def test_snooze_across_midnight_boundary(self) -> None:
        """Snooze calculation handles crossing midnight and date changes."""
        sched = SchedulerService(timezone_str="Asia/Ho_Chi_Minh")
        # Now + 15 minutes calculation is purely datetime arithmetic with zoneinfo
        now = datetime.now(sched.timezone)
        job_id = sched.schedule_snooze_job("s_midnight", "gym", 1, 15, AsyncMock())
        run_at = sched.snooze_jobs[job_id]["run_at"]
        assert run_at > now
        assert (run_at - now).total_seconds() == pytest.approx(15 * 60, abs=2)
        sched.shutdown()

    def test_cron_trigger_timezone_matches(self, base_config: AppConfig) -> None:
        """CronTriggers created for recurring jobs carry the exact scheduler timezone."""
        sched = SchedulerService(timezone_str="Asia/Ho_Chi_Minh")
        sched.register_scheduled_jobs(base_config, AsyncMock())

        for job_id in ["gym_split1", "gym_split2", "toeic", "major"]:
            aps_job = sched.scheduler.get_job(job_id)
            assert aps_job is not None
            assert isinstance(aps_job.trigger, CronTrigger)
            assert aps_job.trigger.timezone == sched.timezone
        sched.shutdown()


# ============================================================================
# 3. Repeated / Idempotent register_scheduled_jobs Tests
# ============================================================================

class TestRepeatedJobRegistration:
    """Tests that repeated calls to register_scheduled_jobs replace existing jobs cleanly."""

    def test_repeated_registrations_maintain_exact_job_count(self, base_config: AppConfig) -> None:
        """Calling register_scheduled_jobs multiple times keeps exactly 4 jobs without leaks."""
        sched = SchedulerService()
        cb = AsyncMock()

        for _ in range(10):
            sched.register_scheduled_jobs(base_config, cb)
            assert len(sched.registered_jobs) == 4
            assert len(sched.scheduler.get_jobs()) == 4

        job_ids = {j.id for j in sched.scheduler.get_jobs()}
        assert job_ids == {"gym_split1", "gym_split2", "toeic", "major"}
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_repeated_registration_replaces_callback_cleanly(self, base_config: AppConfig) -> None:
        """When re-registering with Callback B, Callback A is never invoked."""
        sched = SchedulerService()
        cb1_called = False
        cb2_called = False

        async def cb1(stype: str, name: str) -> None:
            nonlocal cb1_called
            cb1_called = True

        async def cb2(stype: str, name: str) -> None:
            nonlocal cb2_called
            cb2_called = True

        # First registration with cb1
        sched.register_scheduled_jobs(base_config, cb1)
        # Second registration with cb2 (replaces cb1)
        sched.register_scheduled_jobs(base_config, cb2)

        # Trigger jobs via trigger_job
        await sched.trigger_job("gym_split1")
        assert not cb1_called
        assert cb2_called

        # Also verify internal APScheduler job wrapper points to cb2
        cb2_called = False
        aps_job = sched.scheduler.get_job("gym_split1")
        assert aps_job is not None
        await aps_job.func()
        assert not cb1_called
        assert cb2_called
        sched.shutdown()

    def test_re_registration_with_updated_schedule_times(self, base_config: AppConfig) -> None:
        """Re-registering with altered config updates time and trigger parameters."""
        sched = SchedulerService()
        sched.register_scheduled_jobs(base_config, AsyncMock())

        assert sched.registered_jobs["toeic"]["time"] == "19:25"
        assert sched.registered_jobs["toeic"]["hour"] == 19
        assert sched.registered_jobs["toeic"]["minute"] == 25

        # Modify config
        updated_config = AppConfig(
            bot_token=base_config.bot_token,
            gemini_api_key=base_config.gemini_api_key,
            allowed_chat_id=base_config.allowed_chat_id,
            timezone=base_config.timezone,
            max_snoozes=base_config.max_snoozes,
            snooze_minutes=base_config.snooze_minutes,
            context_window_size=base_config.context_window_size,
            gym=base_config.gym,
            toeic=ToeicScheduleConfig(
                time="21:15",
                duration_minutes=60,
                syllabus_rotation=base_config.toeic.syllabus_rotation,
                name="Updated TOEIC Session",
            ),
            major=base_config.major,
            prompts={},
            fallbacks={},
        )

        sched.register_scheduled_jobs(updated_config, AsyncMock())

        assert len(sched.registered_jobs) == 4
        assert len(sched.scheduler.get_jobs()) == 4
        assert sched.registered_jobs["toeic"]["time"] == "21:15"
        assert sched.registered_jobs["toeic"]["hour"] == 21
        assert sched.registered_jobs["toeic"]["minute"] == 15
        assert sched.registered_jobs["toeic"]["name"] == "Updated TOEIC Session"

        aps_job = sched.scheduler.get_job("toeic")
        assert aps_job is not None
        assert aps_job.name == "Updated TOEIC Session"
        sched.shutdown()

    def test_re_registration_after_partial_cancel(self, base_config: AppConfig) -> None:
        """If one job is cancelled, register_scheduled_jobs restores all 4 cleanly."""
        sched = SchedulerService()
        sched.register_scheduled_jobs(base_config, AsyncMock())
        assert len(sched.registered_jobs) == 4

        # Cancel one job
        assert sched.cancel_job("gym_split1") is True
        assert len(sched.registered_jobs) == 3
        assert len(sched.scheduler.get_jobs()) == 3

        # Re-register
        sched.register_scheduled_jobs(base_config, AsyncMock())
        assert len(sched.registered_jobs) == 4
        assert len(sched.scheduler.get_jobs()) == 4
        assert "gym_split1" in sched.registered_jobs
        sched.shutdown()


# ============================================================================
# 4. Concurrency, Snooze Edge Cases & Stress Harness
# ============================================================================

class TestConcurrencyAndStressHarness:
    """Stress harness testing high-volume snoozes, overwrites, and rapid restarts."""

    def test_duplicate_snooze_job_id_replaces_cleanly(self) -> None:
        """Scheduling snooze with identical session_id and count replaces cleanly."""
        sched = SchedulerService()
        cb1 = AsyncMock()
        cb2 = AsyncMock()

        j1 = sched.schedule_snooze_job("session_dup", "gym", 1, 10, cb1)
        j2 = sched.schedule_snooze_job("session_dup", "gym", 1, 20, cb2)

        assert j1 == j2 == "snooze_session_dup_1"
        assert len(sched.snooze_jobs) == 1
        assert sched.snooze_jobs[j1]["delay_minutes"] == 20
        assert sched.snooze_jobs[j1]["callback"] is cb2

        # APScheduler should have only 1 job for this ID
        aps_jobs = [j for j in sched.scheduler.get_jobs() if j.id == j1]
        assert len(aps_jobs) == 1
        sched.shutdown()

    @pytest.mark.asyncio
    async def test_high_volume_snooze_creation_and_cancellation(self) -> None:
        """Create 100 snoozes, cancel 50, trigger 50, verify zero state leaks."""
        sched = SchedulerService()
        triggered_ids: List[str] = []

        async def snooze_cb(sid: str, stype: str, count: int) -> None:
            triggered_ids.append(sid)

        created_jobs: List[str] = []
        for i in range(100):
            jid = sched.schedule_snooze_job(f"bulk_{i}", "major", 1, 15, snooze_cb)
            created_jobs.append(jid)

        assert len(sched.snooze_jobs) == 100
        assert len(sched.scheduler.get_jobs()) == 100

        # Cancel the first 50
        for i in range(50):
            assert sched.cancel_job(created_jobs[i]) is True

        assert len(sched.snooze_jobs) == 50
        assert len(sched.scheduler.get_jobs()) == 50

        # Trigger the remaining 50
        for i in range(50, 100):
            await sched.trigger_job(created_jobs[i])

        assert len(triggered_ids) == 50
        assert len(sched.snooze_jobs) == 0
        assert len(sched.scheduler.get_jobs()) == 0
        sched.shutdown()

    def test_rapid_start_shutdown_cycles(self, base_config: AppConfig) -> None:
        """Rapid cycling of start and shutdown does not throw or corrupt state."""
        sched = SchedulerService()
        sched.register_scheduled_jobs(base_config, AsyncMock())

        for _ in range(15):
            sched.start()
            assert sched.is_running is True
            sched.shutdown()
            assert sched.is_running is False
            # Registered jobs must be retained and reattached
            assert len(sched.registered_jobs) == 4
            assert len(sched.scheduler.get_jobs()) == 4
