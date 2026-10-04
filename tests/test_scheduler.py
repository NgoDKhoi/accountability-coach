"""Comprehensive unit tests for SchedulerService (Milestone 3).

Covers initialization, timezone configuration, CronTrigger job registration,
one-shot DateTrigger snooze jobs, test harness dispatcher, cancellation,
lifecycle (start/shutdown/restart), error resilience, and edge cases.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, List, Tuple
from zoneinfo import ZoneInfo
import pytest

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.config import AppConfig, GymScheduleConfig, ToeicScheduleConfig, MajorScheduleConfig
from src.scheduler import SchedulerService, _parse_time_str, _extract_attr_or_key


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def sample_config() -> AppConfig:
    """Fixture providing a complete AppConfig instance."""
    return AppConfig(
        bot_token="test_token_12345",
        gemini_api_key="test_gemini_key",
        allowed_chat_id=12345678,
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


@pytest.fixture
def scheduler() -> SchedulerService:
    """Fixture providing a fresh SchedulerService in Asia/Ho_Chi_Minh."""
    svc = SchedulerService(timezone_str="Asia/Ho_Chi_Minh")
    yield svc
    svc.shutdown()


# =====================================================================
# 1. Initialization & Timezone Tests
# =====================================================================

class TestSchedulerInitialization:
    """Tests for scheduler instantiation and timezone configuration."""

    def test_init_default_timezone(self) -> None:
        """Scheduler defaults to Asia/Ho_Chi_Minh with unstarted initial state."""
        svc = SchedulerService()
        assert svc.timezone_str == "Asia/Ho_Chi_Minh"
        assert isinstance(svc.timezone, ZoneInfo)
        assert svc.timezone.key == "Asia/Ho_Chi_Minh"
        assert svc.is_running is False
        assert len(svc.registered_jobs) == 0
        assert len(svc.snooze_jobs) == 0

    def test_init_custom_timezone(self) -> None:
        """Scheduler accepts custom valid IANA timezone string."""
        svc = SchedulerService(timezone_str="UTC")
        assert svc.timezone_str == "UTC"
        assert svc.timezone.key == "UTC"

    def test_init_with_zoneinfo_instance(self) -> None:
        """Scheduler accepts a direct ZoneInfo object."""
        tz = ZoneInfo("Asia/Tokyo")
        svc = SchedulerService(timezone_str=tz)
        assert svc.timezone == tz
        assert svc.timezone_str == "Asia/Tokyo"

    def test_init_invalid_timezone_raises_value_error(self) -> None:
        """Invalid timezone string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid timezone"):
            SchedulerService(timezone_str="Invalid/Nonexistent_Timezone_123")

    def test_parse_time_str_valid(self) -> None:
        """_parse_time_str correctly parses HH:MM format."""
        assert _parse_time_str("17:15") == (17, 15)
        assert _parse_time_str("00:00") == (0, 0)
        assert _parse_time_str("23:59") == (23, 59)

    def test_parse_time_str_invalid(self) -> None:
        """_parse_time_str raises ValueError on malformed time string."""
        with pytest.raises(ValueError):
            _parse_time_str("1715")
        with pytest.raises(ValueError):
            _parse_time_str("17:15:00")
        with pytest.raises(ValueError):
            _parse_time_str("not:time")

    def test_extract_attr_or_key(self) -> None:
        """_extract_attr_or_key works on both objects and dictionaries."""
        d = {"hello": "world"}
        assert _extract_attr_or_key(d, "hello") == "world"
        assert _extract_attr_or_key(d, "missing", "default") == "default"

        class Dummy:
            attr = 42

        assert _extract_attr_or_key(Dummy(), "attr") == 42
        assert _extract_attr_or_key(Dummy(), "none_exist", 99) == 99


# =====================================================================
# 2. Recurring Scheduled Jobs Registration Tests
# =====================================================================

class TestScheduledJobsRegistration:
    """Tests for registering recurring cron jobs."""

    def test_register_scheduled_jobs_all_sessions(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """All 4 sessions (Gym Split 1, Gym Split 2, TOEIC, Major) are registered."""
        async def dummy_callback(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_callback)

        assert len(scheduler.registered_jobs) == 4
        assert "gym_split1" in scheduler.registered_jobs
        assert "gym_split2" in scheduler.registered_jobs
        assert "toeic" in scheduler.registered_jobs
        assert "major" in scheduler.registered_jobs

    def test_gym_split1_job_details(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Gym Split 1 cron job matches Mon, Tue, Thu at 17:15."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_cb)
        job = scheduler.registered_jobs["gym_split1"]
        assert job["type"] == "gym"
        assert job["name"] == "Gym Session"
        assert job["days"] == "mon,tue,thu"
        assert job["time"] == "17:15"
        assert job["hour"] == 17
        assert job["minute"] == 15

        # Check internal APScheduler job
        aps_job = scheduler.scheduler.get_job("gym_split1")
        assert aps_job is not None
        assert isinstance(aps_job.trigger, CronTrigger)

    def test_gym_split2_job_details(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Gym Split 2 cron job matches Wed, Sat at 16:15."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_cb)
        job = scheduler.registered_jobs["gym_split2"]
        assert job["type"] == "gym"
        assert job["name"] == "Gym Session"
        assert job["days"] == "wed,sat"
        assert job["time"] == "16:15"
        assert job["hour"] == 16
        assert job["minute"] == 15

        aps_job = scheduler.scheduler.get_job("gym_split2")
        assert aps_job is not None
        assert isinstance(aps_job.trigger, CronTrigger)

    def test_toeic_job_details(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """TOEIC study session cron job runs daily at 19:25."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_cb)
        job = scheduler.registered_jobs["toeic"]
        assert job["type"] == "toeic"
        assert job["name"] == "TOEIC Study Session"
        assert job["days"] == "daily"
        assert job["time"] == "19:25"
        assert job["hour"] == 19
        assert job["minute"] == 25

        aps_job = scheduler.scheduler.get_job("toeic")
        assert aps_job is not None
        assert isinstance(aps_job.trigger, CronTrigger)

    def test_major_job_details(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Major Subject study session cron job runs daily at 20:40."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_cb)
        job = scheduler.registered_jobs["major"]
        assert job["type"] == "major"
        assert job["name"] == "Major Subject Study & Game Dev"
        assert job["days"] == "daily"
        assert job["time"] == "20:40"
        assert job["hour"] == 20
        assert job["minute"] == 40

        aps_job = scheduler.scheduler.get_job("major")
        assert aps_job is not None
        assert isinstance(aps_job.trigger, CronTrigger)

    def test_register_scheduled_jobs_with_dict_config(
        self, scheduler: SchedulerService
    ) -> None:
        """Dictionary config format is accepted and parsed accurately."""
        dict_config = {
            "gym": {
                "name": "Gym Time",
                "cron_days_split1": "mon,wed,fri",
                "time_split1": "07:00",
                "cron_days_split2": "tue,thu",
                "time_split2": "08:30",
            },
            "toeic": {
                "name": "TOEIC Practice",
                "time": "18:00",
            },
            "major": {
                "name": "Game Architecture",
                "time": "21:00",
            },
        }

        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(dict_config, dummy_cb)
        assert scheduler.registered_jobs["gym_split1"]["time"] == "07:00"
        assert scheduler.registered_jobs["gym_split1"]["hour"] == 7
        assert scheduler.registered_jobs["gym_split2"]["time"] == "08:30"
        assert scheduler.registered_jobs["toeic"]["time"] == "18:00"
        assert scheduler.registered_jobs["major"]["time"] == "21:00"

    def test_register_scheduled_jobs_invalid_inputs(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """register_scheduled_jobs validates config and callback inputs."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        with pytest.raises(ValueError, match="Configuration cannot be None"):
            scheduler.register_scheduled_jobs(None, dummy_cb)

        with pytest.raises(TypeError, match="trigger_callback must be a callable"):
            scheduler.register_scheduled_jobs(sample_config, "not_a_callback")  # type: ignore

    def test_register_scheduled_jobs_idempotent_replace(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Calling register_scheduled_jobs multiple times replaces jobs cleanly."""
        async def cb1(stype: str, name: str) -> None:
            pass

        async def cb2(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, cb1)
        assert len(scheduler.registered_jobs) == 4

        # Register again with different callback
        scheduler.register_scheduled_jobs(sample_config, cb2)
        assert len(scheduler.registered_jobs) == 4
        assert scheduler.registered_jobs["gym_split1"]["callback"] is cb2


# =====================================================================
# 3. Snooze Job Scheduling Tests
# =====================================================================

class TestSnoozeJobScheduling:
    """Tests for dynamic 15-minute one-shot snooze jobs."""

    def test_schedule_snooze_job_attributes(self, scheduler: SchedulerService) -> None:
        """Snooze job creates DateTrigger with 15m delay and expected job_id."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        start_time = datetime.now(scheduler.timezone)
        job_id = scheduler.schedule_snooze_job(
            session_id="session_101",
            session_type="gym",
            snooze_count=1,
            delay_minutes=15,
            callback=dummy_cb,
        )

        assert job_id == "snooze_session_101_1"
        assert job_id in scheduler.snooze_jobs
        job_info = scheduler.snooze_jobs[job_id]
        assert job_info["session_id"] == "session_101"
        assert job_info["session_type"] == "gym"
        assert job_info["snooze_count"] == 1
        assert job_info["delay_minutes"] == 15
        assert job_info["callback"] is dummy_cb

        # run_at should be approximately 15 minutes ahead
        diff_seconds = (job_info["run_at"] - start_time).total_seconds()
        assert 14 * 60 <= diff_seconds <= 16 * 60

        # APScheduler job verification
        aps_job = scheduler.scheduler.get_job(job_id)
        assert aps_job is not None
        assert isinstance(aps_job.trigger, DateTrigger)

    def test_schedule_multiple_snooze_jobs(self, scheduler: SchedulerService) -> None:
        """Multiple concurrent snooze jobs are tracked independently."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        j1 = scheduler.schedule_snooze_job("sid_A", "gym", 1, 15, dummy_cb)
        j2 = scheduler.schedule_snooze_job("sid_B", "toeic", 2, 15, dummy_cb)

        assert j1 == "snooze_sid_A_1"
        assert j2 == "snooze_sid_B_2"
        assert len(scheduler.snooze_jobs) == 2
        assert j1 in scheduler.snooze_jobs
        assert j2 in scheduler.snooze_jobs

    def test_schedule_snooze_job_invalid_callback(self, scheduler: SchedulerService) -> None:
        """Non-callable snooze callback raises TypeError."""
        with pytest.raises(TypeError, match="Snooze callback must be callable"):
            scheduler.schedule_snooze_job("sid_A", "gym", 1, 15, "invalid")  # type: ignore


# =====================================================================
# 4. Trigger Job Dispatcher Tests (Test Harness)
# =====================================================================

class TestTriggerJobDispatcher:
    """Tests for async trigger_job test harness dispatch method."""

    @pytest.mark.asyncio
    async def test_trigger_snooze_job_async_callback(
        self, scheduler: SchedulerService
    ) -> None:
        """Triggering a snooze job invokes callback and removes job from dictionary."""
        invoked: List[Tuple[str, str, int]] = []

        async def snooze_cb(sid: str, stype: str, count: int) -> None:
            invoked.append((sid, stype, count))

        job_id = scheduler.schedule_snooze_job(
            session_id="gym_session_99",
            session_type="gym",
            snooze_count=2,
            delay_minutes=15,
            callback=snooze_cb,
        )

        assert job_id in scheduler.snooze_jobs
        await scheduler.trigger_job(job_id)

        assert len(invoked) == 1
        assert invoked[0] == ("gym_session_99", "gym", 2)
        # Snooze job is cleared after firing
        assert job_id not in scheduler.snooze_jobs
        assert scheduler.scheduler.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_trigger_snooze_job_sync_callback(
        self, scheduler: SchedulerService
    ) -> None:
        """Triggering a snooze job works with synchronous callback."""
        invoked: List[Tuple[str, str, int]] = []

        def sync_snooze_cb(sid: str, stype: str, count: int) -> None:
            invoked.append((sid, stype, count))

        job_id = scheduler.schedule_snooze_job("sync_sid", "toeic", 1, 15, sync_snooze_cb)  # type: ignore
        await scheduler.trigger_job(job_id)

        assert len(invoked) == 1
        assert invoked[0] == ("sync_sid", "toeic", 1)

    @pytest.mark.asyncio
    async def test_trigger_registered_job_async_callback(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Triggering a recurring registered job invokes callback without removing it."""
        invoked: List[Tuple[str, str]] = []

        async def push_cb(stype: str, name: str) -> None:
            invoked.append((stype, name))

        scheduler.register_scheduled_jobs(sample_config, push_cb)

        await scheduler.trigger_job("gym_split1")
        assert len(invoked) == 1
        assert invoked[0] == ("gym", "Gym Session")
        # Registered recurring job remains active
        assert "gym_split1" in scheduler.registered_jobs

        await scheduler.trigger_job("toeic")
        assert len(invoked) == 2
        assert invoked[1] == ("toeic", "TOEIC Study Session")

        await scheduler.trigger_job("major")
        assert len(invoked) == 3
        assert invoked[2] == ("major", "Major Subject Study & Game Dev")

    @pytest.mark.asyncio
    async def test_trigger_registered_job_sync_callback(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Triggering a recurring registered job works with sync callback."""
        invoked: List[Tuple[str, str]] = []

        def sync_push_cb(stype: str, name: str) -> None:
            invoked.append((stype, name))

        scheduler.register_scheduled_jobs(sample_config, sync_push_cb)  # type: ignore
        await scheduler.trigger_job("gym_split2")

        assert len(invoked) == 1
        assert invoked[0] == ("gym", "Gym Session")

    @pytest.mark.asyncio
    async def test_trigger_unregistered_job_no_op(
        self, scheduler: SchedulerService
    ) -> None:
        """Triggering an unknown job_id does not raise and completes cleanly."""
        # Should execute safely without uncaught exception
        await scheduler.trigger_job("nonexistent_job_123")


# =====================================================================
# 5. Job Cancellation Tests
# =====================================================================

class TestJobCancellation:
    """Tests for cancel_job method."""

    def test_cancel_snooze_job(self, scheduler: SchedulerService) -> None:
        """Cancelling a snooze job removes it from both dict and APScheduler."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        job_id = scheduler.schedule_snooze_job("sid_cancel", "gym", 1, 15, dummy_cb)
        assert job_id in scheduler.snooze_jobs
        assert scheduler.scheduler.get_job(job_id) is not None

        result = scheduler.cancel_job(job_id)
        assert result is True
        assert job_id not in scheduler.snooze_jobs
        assert scheduler.scheduler.get_job(job_id) is None

    def test_cancel_registered_job(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Cancelling a registered cron job removes it from both dict and APScheduler."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_cb)
        assert "gym_split1" in scheduler.registered_jobs

        result = scheduler.cancel_job("gym_split1")
        assert result is True
        assert "gym_split1" not in scheduler.registered_jobs
        assert scheduler.scheduler.get_job("gym_split1") is None

    def test_cancel_nonexistent_job_returns_false(
        self, scheduler: SchedulerService
    ) -> None:
        """Cancelling an unknown job returns False."""
        assert scheduler.cancel_job("random_nonexistent_id") is False

    def test_cancel_already_cancelled_job(self, scheduler: SchedulerService) -> None:
        """Cancelling the same job twice returns False on second call."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        job_id = scheduler.schedule_snooze_job("sid_twice", "gym", 1, 15, dummy_cb)
        assert scheduler.cancel_job(job_id) is True
        assert scheduler.cancel_job(job_id) is False


# =====================================================================
# 6. Lifecycle Management Tests (start, shutdown, restart)
# =====================================================================

class TestSchedulerLifecycle:
    """Tests for scheduler lifecycle state transitions."""

    def test_lifecycle_sync_environment(self, scheduler: SchedulerService) -> None:
        """start() and shutdown() work safely in synchronous unit test environment."""
        assert scheduler.is_running is False

        # In sync environment with no running loop, start() does not raise RuntimeError
        scheduler.start()
        assert scheduler.is_running is True

        scheduler.shutdown()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_lifecycle_async_environment(self, scheduler: SchedulerService) -> None:
        """start() actively starts APScheduler within an async event loop."""
        assert scheduler.is_running is False
        assert scheduler.scheduler.running is False

        scheduler.start()
        assert scheduler.is_running is True
        assert scheduler.scheduler.running is True

        scheduler.shutdown()
        assert scheduler.is_running is False
        assert scheduler.scheduler.running is False

    def test_shutdown_clears_snooze_jobs_preserves_registered(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """shutdown() clears ephemeral snooze jobs and re-attaches recurring jobs."""
        async def push_cb(stype: str, name: str) -> None:
            pass

        async def snooze_cb(sid: str, stype: str, count: int) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, push_cb)
        snooze_id = scheduler.schedule_snooze_job("sid_1", "gym", 1, 15, snooze_cb)

        assert len(scheduler.registered_jobs) == 4
        assert len(scheduler.snooze_jobs) == 1

        scheduler.shutdown()

        # Snooze jobs are cleared
        assert len(scheduler.snooze_jobs) == 0
        # Registered recurring jobs are preserved
        assert len(scheduler.registered_jobs) == 4
        # New APScheduler instance has the 4 recurring jobs re-attached
        assert scheduler.scheduler.get_job("gym_split1") is not None
        assert scheduler.scheduler.get_job("toeic") is not None

    def test_restart_scheduler_after_shutdown(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Calling start() after shutdown() restarts cleanly without exceptions."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        scheduler.register_scheduled_jobs(sample_config, dummy_cb)
        scheduler.start()
        assert scheduler.is_running is True

        scheduler.shutdown()
        assert scheduler.is_running is False

        # Restart
        scheduler.start()
        assert scheduler.is_running is True
        scheduler.shutdown()
        assert scheduler.is_running is False

    def test_idempotent_start_and_shutdown(self, scheduler: SchedulerService) -> None:
        """Calling start() or shutdown() multiple times in succession is safe."""
        scheduler.start()
        scheduler.start()
        assert scheduler.is_running is True

        scheduler.shutdown()
        scheduler.shutdown()
        assert scheduler.is_running is False


# =====================================================================
# 7. Error Resilience & Wrapper Safety Tests
# =====================================================================

class TestErrorResilience:
    """Tests verifying exception safety during job execution."""

    @pytest.mark.asyncio
    async def test_snooze_wrapper_exception_cleanup(
        self, scheduler: SchedulerService
    ) -> None:
        """Even if snooze callback raises an exception, the job is popped cleanly."""
        async def failing_snooze_cb(sid: str, stype: str, count: int) -> None:
            raise RuntimeError("Simulated snooze callback failure!")

        job_id = scheduler.schedule_snooze_job("fail_sid", "gym", 1, 15, failing_snooze_cb)
        assert job_id in scheduler.snooze_jobs

        # Get the internal APScheduler job coroutine function and execute directly
        aps_job = scheduler.scheduler.get_job(job_id)
        assert aps_job is not None

        # Execute internal wrapper coroutine directly
        await aps_job.func()

        # Verify job was removed from snooze_jobs despite exception
        assert job_id not in scheduler.snooze_jobs

    @pytest.mark.asyncio
    async def test_job_wrapper_exception_resilience(
        self, scheduler: SchedulerService, sample_config: AppConfig
    ) -> None:
        """Even if recurring job callback raises, internal wrapper does not crash."""
        async def failing_push_cb(stype: str, name: str) -> None:
            raise RuntimeError("Simulated push callback failure!")

        scheduler.register_scheduled_jobs(sample_config, failing_push_cb)

        aps_job = scheduler.scheduler.get_job("gym_split1")
        assert aps_job is not None

        # Directly invoke wrapper to confirm error is caught and logged
        await aps_job.func()
        # Job still registered
        assert "gym_split1" in scheduler.registered_jobs
