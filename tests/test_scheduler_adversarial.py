"""Adversarial stress harness for Milestone 3 (SchedulerService).

Adversarial stress-testing suite covering:
1. High-concurrency snooze job registrations (multiple session IDs & snooze counts).
2. Job cancellation edge cases (existing, non-existing, concurrent cancellations, race conditions).
3. Manual trigger via trigger_job, callback verification, and complete cleanup.
4. Rapid start/shutdown cycles and restart behavior.
5. Real live APScheduler execution, error resilience, and edge case parameters.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, List, Set, Tuple
from zoneinfo import ZoneInfo
import pytest

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from src.config import AppConfig, GymScheduleConfig, ToeicScheduleConfig, MajorScheduleConfig
from src.scheduler import SchedulerService, _parse_time_str, _extract_attr_or_key


@pytest.fixture
def adversarial_config() -> AppConfig:
    """Fixture providing complete AppConfig for adversarial tests."""
    return AppConfig(
        bot_token="adversarial_bot_token",
        gemini_api_key="adversarial_gemini_key",
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


@pytest.fixture
def adv_scheduler() -> SchedulerService:
    """Fixture providing a fresh SchedulerService."""
    svc = SchedulerService(timezone_str="Asia/Ho_Chi_Minh")
    yield svc
    svc.shutdown()


# =====================================================================
# 1. Concurrent Snooze Job Registrations
# =====================================================================

class TestConcurrentSnoozeRegistrations:
    """Stress-test concurrent registration of snooze jobs."""

    @pytest.mark.asyncio
    async def test_concurrent_registrations_distinct_sessions(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """100 concurrent tasks schedule snooze jobs with distinct session IDs."""
        adv_scheduler.start()
        total_jobs = 100
        invoked_jobs: List[str] = []

        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            invoked_jobs.append(sid)

        async def register_task(index: int) -> str:
            # Vary snooze count (1 or 2) and session types
            count = 1 if index % 2 == 0 else 2
            stype = "gym" if index % 3 == 0 else ("toeic" if index % 3 == 1 else "major")
            session_id = f"sess_concurrent_{index:04d}"
            return adv_scheduler.schedule_snooze_job(
                session_id=session_id,
                session_type=stype,
                snooze_count=count,
                delay_minutes=15,
                callback=dummy_cb,
            )

        # Launch 100 concurrent registrations
        job_ids = await asyncio.gather(*(register_task(i) for i in range(total_jobs)))

        # Assert all 100 job IDs are unique
        assert len(job_ids) == total_jobs
        assert len(set(job_ids)) == total_jobs

        # Assert all 100 jobs are tracked in snooze_jobs dict
        assert len(adv_scheduler.snooze_jobs) == total_jobs
        for jid in job_ids:
            assert jid in adv_scheduler.snooze_jobs
            # Verify APScheduler has the job registered
            aps_job = adv_scheduler.scheduler.get_job(jid)
            assert aps_job is not None

    @pytest.mark.asyncio
    async def test_concurrent_duplicate_registrations(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """20 concurrent tasks attempt to register the exact same session_id and snooze_count."""
        adv_scheduler.start()
        session_id = "duplicate_session_target"
        snooze_count = 1

        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        async def register_task(idx: int) -> str:
            # Minor yield to maximize concurrency interleaving
            await asyncio.sleep(0.001)
            return adv_scheduler.schedule_snooze_job(
                session_id=session_id,
                session_type="gym",
                snooze_count=snooze_count,
                delay_minutes=15,
                callback=dummy_cb,
            )

        job_ids = await asyncio.gather(*(register_task(i) for i in range(20)))

        # All returned job_ids should be identical
        expected_jid = f"snooze_{session_id}_{snooze_count}"
        assert all(jid == expected_jid for jid in job_ids)

        # snooze_jobs dictionary should cleanly have exactly 1 entry
        assert len(adv_scheduler.snooze_jobs) == 1
        assert expected_jid in adv_scheduler.snooze_jobs
        assert adv_scheduler.scheduler.get_job(expected_jid) is not None

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Simultaneous concurrent registrations and cancellations across 50 sessions."""
        adv_scheduler.start()

        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        # Phase 1: Register 50 jobs
        jobs_to_cancel = [f"mix_{i}" for i in range(25)]
        jobs_to_keep = [f"mix_{i}" for i in range(25, 50)]

        for sid in jobs_to_cancel + jobs_to_keep:
            adv_scheduler.schedule_snooze_job(sid, "gym", 1, 15, dummy_cb)

        # Phase 2: Concurrently cancel the first 25 while scheduling 25 new ones
        async def cancel_op(sid: str) -> bool:
            jid = f"snooze_{sid}_1"
            return adv_scheduler.cancel_job(jid)

        async def schedule_op(idx: int) -> str:
            sid = f"mix_new_{idx}"
            return adv_scheduler.schedule_snooze_job(sid, "toeic", 1, 15, dummy_cb)

        cancel_tasks = [cancel_op(sid) for sid in jobs_to_cancel]
        schedule_tasks = [schedule_op(i) for i in range(25)]

        results = await asyncio.gather(*(cancel_tasks + schedule_tasks))

        # First 25 were cancelled successfully
        for res in results[:25]:
            assert res is True

        # Total snooze_jobs should now be 25 kept + 25 newly scheduled = 50
        assert len(adv_scheduler.snooze_jobs) == 50
        for sid in jobs_to_cancel:
            assert f"snooze_{sid}_1" not in adv_scheduler.snooze_jobs
        for sid in jobs_to_keep:
            assert f"snooze_{sid}_1" in adv_scheduler.snooze_jobs


# =====================================================================
# 2. Cancelling Jobs (Existing, Non-existing, Concurrent)
# =====================================================================

class TestJobCancellationEdgeCases:
    """Stress-test cancel_job behavior under boundary and concurrent conditions."""

    def test_cancel_non_existing_jobs(self, adv_scheduler: SchedulerService) -> None:
        """Cancelling non-existing, malformed, or empty job IDs returns False safely."""
        assert adv_scheduler.cancel_job("non_existent_123") is False
        assert adv_scheduler.cancel_job("") is False
        assert adv_scheduler.cancel_job("   ") is False
        assert adv_scheduler.cancel_job("snooze_fake_session_1") is False

    @pytest.mark.asyncio
    async def test_concurrent_cancel_same_job(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Multiple concurrent tasks attempt to cancel the exact same job ID."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        job_id = adv_scheduler.schedule_snooze_job("target_cancel_job", "gym", 1, 15, dummy_cb)

        async def cancel_worker() -> bool:
            return adv_scheduler.cancel_job(job_id)

        # 20 concurrent cancellation attempts
        results = await asyncio.gather(*(cancel_worker() for _ in range(20)))

        # Exactly ONE call must return True, the remaining 19 must return False
        true_count = sum(1 for r in results if r is True)
        false_count = sum(1 for r in results if r is False)
        assert true_count == 1
        assert false_count == 19
        assert job_id not in adv_scheduler.snooze_jobs

    def test_cancel_registered_cron_job_removes_from_both_stores(
        self, adv_scheduler: SchedulerService, adversarial_config: AppConfig
    ) -> None:
        """Cancelling a registered recurring cron job removes from dict and APScheduler."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        adv_scheduler.register_scheduled_jobs(adversarial_config, dummy_cb)
        assert "gym_split1" in adv_scheduler.registered_jobs
        assert adv_scheduler.scheduler.get_job("gym_split1") is not None

        # Cancel gym_split1
        res = adv_scheduler.cancel_job("gym_split1")
        assert res is True
        assert "gym_split1" not in adv_scheduler.registered_jobs
        assert adv_scheduler.scheduler.get_job("gym_split1") is None

        # Gym split 2, toeic, major remain untouched
        assert "gym_split2" in adv_scheduler.registered_jobs
        assert "toeic" in adv_scheduler.registered_jobs
        assert "major" in adv_scheduler.registered_jobs

    def test_cancel_after_trigger_returns_false(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Cancelling a job after it was already triggered via trigger_job returns False."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        job_id = adv_scheduler.schedule_snooze_job("triggered_then_cancelled", "toeic", 1, 15, dummy_cb)
        asyncio.run(adv_scheduler.trigger_job(job_id))

        # Job is already removed
        assert adv_scheduler.cancel_job(job_id) is False


# =====================================================================
# 3. Triggering Snooze Jobs Manually & Cleanup Verification
# =====================================================================

class TestTriggerJobAndCleanup:
    """Stress-test trigger_job test harness entrypoint and cleanup semantics."""

    @pytest.mark.asyncio
    async def test_trigger_job_cleanup_verification(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """trigger_job completely purges snooze job from both snooze_jobs and APScheduler."""
        call_log: List[Tuple[str, str, int]] = []

        async def snooze_cb(sid: str, stype: str, count: int) -> None:
            call_log.append((sid, stype, count))

        job_id = adv_scheduler.schedule_snooze_job("session_cleanup_test", "major", 2, 15, snooze_cb)

        assert job_id in adv_scheduler.snooze_jobs
        assert adv_scheduler.scheduler.get_job(job_id) is not None

        await adv_scheduler.trigger_job(job_id)

        # 1. Callback verified
        assert len(call_log) == 1
        assert call_log[0] == ("session_cleanup_test", "major", 2)

        # 2. Complete cleanup verified
        assert job_id not in adv_scheduler.snooze_jobs
        assert adv_scheduler.scheduler.get_job(job_id) is None

        # 3. Subsequent trigger is no-op
        await adv_scheduler.trigger_job(job_id)
        assert len(call_log) == 1  # Not called again

    @pytest.mark.asyncio
    async def test_concurrent_trigger_job_race(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Concurrent calls to trigger_job on the same job_id only invoke callback once."""
        call_count = 0

        async def counting_cb(sid: str, stype: str, count: int) -> None:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)

        job_id = adv_scheduler.schedule_snooze_job("race_session", "gym", 1, 15, counting_cb)

        # 10 concurrent triggers
        await asyncio.gather(*(adv_scheduler.trigger_job(job_id) for _ in range(10)))

        # Callback must be invoked EXACTLY once
        assert call_count == 1
        assert job_id not in adv_scheduler.snooze_jobs

    @pytest.mark.asyncio
    async def test_trigger_job_exception_does_not_corrupt_state(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """When callback raises an exception in trigger_job, job is still purged from state."""
        async def exploding_cb(sid: str, stype: str, count: int) -> None:
            raise ValueError("Deliberate test explosion!")

        job_id = adv_scheduler.schedule_snooze_job("explode_session", "gym", 1, 15, exploding_cb)

        with pytest.raises(ValueError, match="Deliberate test explosion!"):
            await adv_scheduler.trigger_job(job_id)

        # Crucial: Job must STILL be popped from snooze_jobs so it cannot be re-triggered
        assert job_id not in adv_scheduler.snooze_jobs
        assert adv_scheduler.scheduler.get_job(job_id) is None

    @pytest.mark.asyncio
    async def test_trigger_job_non_existent_does_not_raise(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """trigger_job on unknown, None-like, or empty job_id is safe and does not raise."""
        await adv_scheduler.trigger_job("snooze_nonexistent_999")
        await adv_scheduler.trigger_job("")
        await adv_scheduler.trigger_job("random_string_xyz")


# =====================================================================
# 4. Rapid Start/Shutdown Cycles & Restart Behavior
# =====================================================================

class TestRapidLifecycleCycles:
    """Stress-test rapid start/shutdown/restart cycles."""

    @pytest.mark.asyncio
    async def test_rapid_start_shutdown_loop(
        self, adv_scheduler: SchedulerService, adversarial_config: AppConfig
    ) -> None:
        """50 rapid alternating start/shutdown cycles execute cleanly without crash or leak."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        adv_scheduler.register_scheduled_jobs(adversarial_config, dummy_cb)

        for i in range(50):
            adv_scheduler.start()
            assert adv_scheduler.is_running is True
            assert adv_scheduler.scheduler.running is True

            adv_scheduler.shutdown()
            assert adv_scheduler.is_running is False
            assert adv_scheduler.scheduler.running is False

    @pytest.mark.asyncio
    async def test_restart_retains_registered_jobs(
        self, adv_scheduler: SchedulerService, adversarial_config: AppConfig
    ) -> None:
        """Registered recurring jobs survive shutdown and can be triggered after restart."""
        invocations: List[str] = []

        async def push_cb(stype: str, name: str) -> None:
            invocations.append(f"{stype}:{name}")

        adv_scheduler.register_scheduled_jobs(adversarial_config, push_cb)

        adv_scheduler.start()
        adv_scheduler.shutdown()

        # Restart
        adv_scheduler.start()
        assert adv_scheduler.is_running is True

        # All 4 jobs are present and triggerable
        assert len(adv_scheduler.registered_jobs) == 4
        assert adv_scheduler.scheduler.get_job("gym_split1") is not None
        assert adv_scheduler.scheduler.get_job("gym_split2") is not None
        assert adv_scheduler.scheduler.get_job("toeic") is not None
        assert adv_scheduler.scheduler.get_job("major") is not None

        await adv_scheduler.trigger_job("gym_split1")
        await adv_scheduler.trigger_job("toeic")

        assert len(invocations) == 2
        assert invocations[0] == "gym:Gym Session"
        assert invocations[1] == "toeic:TOEIC Study Session"

        adv_scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_purges_pending_snooze_jobs(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Shutdown purges pending ephemeral snooze jobs while leaving system ready for new ones."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        j1 = adv_scheduler.schedule_snooze_job("sid_1", "gym", 1, 15, dummy_cb)
        j2 = adv_scheduler.schedule_snooze_job("sid_2", "toeic", 1, 15, dummy_cb)

        assert len(adv_scheduler.snooze_jobs) == 2

        adv_scheduler.shutdown()

        # All snooze jobs cleared
        assert len(adv_scheduler.snooze_jobs) == 0

        # Restart and schedule new snooze job
        adv_scheduler.start()
        j3 = adv_scheduler.schedule_snooze_job("sid_3", "major", 1, 15, dummy_cb)
        assert len(adv_scheduler.snooze_jobs) == 1
        assert j3 in adv_scheduler.snooze_jobs

        adv_scheduler.shutdown()

    def test_idempotent_multi_call_lifecycle(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Multiple consecutive starts or shutdowns do not throw exceptions."""
        for _ in range(5):
            adv_scheduler.start()
        assert adv_scheduler.is_running is True

        for _ in range(5):
            adv_scheduler.shutdown()
        assert adv_scheduler.is_running is False


# =====================================================================
# 5. Live APScheduler Execution & Edge Case Scenarios
# =====================================================================

class TestLiveExecutionAndEdgeCases:
    """Stress-test live background execution and edge case parameters."""

    @pytest.mark.asyncio
    async def test_live_snooze_job_fires_and_cleans_up(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Live running scheduler executes DateTrigger snooze job and auto-cleans dict."""
        adv_scheduler.start()
        fired_event = asyncio.Event()
        fired_data: List[Tuple[str, str, int]] = []

        async def live_snooze_cb(sid: str, stype: str, count: int) -> None:
            fired_data.append((sid, stype, count))
            fired_event.set()

        # Schedule snooze job with 0 delay (runs immediately)
        job_id = adv_scheduler.schedule_snooze_job(
            session_id="live_fire_session",
            session_type="gym",
            snooze_count=1,
            delay_minutes=0,
            callback=live_snooze_cb,
        )

        assert job_id in adv_scheduler.snooze_jobs

        # Wait for APScheduler worker to execute the job (max 2 seconds)
        try:
            await asyncio.wait_for(fired_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("APScheduler failed to fire snooze job within 2.0s")

        assert len(fired_data) == 1
        assert fired_data[0] == ("live_fire_session", "gym", 1)

        # Allow brief moment for finally block to complete
        await asyncio.sleep(0.05)
        # Verify job was automatically purged from snooze_jobs dict
        assert job_id not in adv_scheduler.snooze_jobs

    @pytest.mark.asyncio
    async def test_live_snooze_job_exception_does_not_crash_scheduler(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """An unhandled exception in live snooze callback is caught and does not crash scheduler."""
        adv_scheduler.start()
        exception_hit = asyncio.Event()

        async def exploding_live_cb(sid: str, stype: str, count: int) -> None:
            exception_hit.set()
            raise RuntimeError("Fatal callback error in worker thread!")

        job_id = adv_scheduler.schedule_snooze_job(
            session_id="exploding_live_session",
            session_type="toeic",
            snooze_count=1,
            delay_minutes=0,
            callback=exploding_live_cb,
        )

        await asyncio.wait_for(exception_hit.wait(), timeout=2.0)
        await asyncio.sleep(0.05)

        # Scheduler must still be running and healthy
        assert adv_scheduler.is_running is True
        assert adv_scheduler.scheduler.running is True
        # Faulty job was cleaned up
        assert job_id not in adv_scheduler.snooze_jobs

    def test_special_characters_in_session_id(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Session IDs with unicode, spaces, colons, slashes, and emojis are handled properly."""
        special_ids = [
            "session:2026-10-04_17:15",
            "session/slash/sub_id",
            "session with spaces",
            "session_tiếng_việt_thể_dục",
            "session_🏋️‍♂️_🔥",
        ]

        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        created_jobs: List[str] = []
        for sid in special_ids:
            jid = adv_scheduler.schedule_snooze_job(sid, "gym", 1, 15, dummy_cb)
            created_jobs.append(jid)
            assert jid in adv_scheduler.snooze_jobs
            assert adv_scheduler.scheduler.get_job(jid) is not None

        # Cancel all of them
        for jid in created_jobs:
            assert adv_scheduler.cancel_job(jid) is True
            assert jid not in adv_scheduler.snooze_jobs

    def test_extreme_delay_minutes(self, adv_scheduler: SchedulerService) -> None:
        """Boundary values for delay_minutes: 0, negative, very large."""
        async def dummy_cb(sid: str, stype: str, count: int) -> None:
            pass

        # 0 minutes
        j0 = adv_scheduler.schedule_snooze_job("zero_delay", "gym", 1, 0, dummy_cb)
        assert j0 in adv_scheduler.snooze_jobs

        # Negative delay (past date)
        j_neg = adv_scheduler.schedule_snooze_job("neg_delay", "gym", 1, -10, dummy_cb)
        assert j_neg in adv_scheduler.snooze_jobs

        # Very large delay (e.g. 1 year)
        j_large = adv_scheduler.schedule_snooze_job("large_delay", "gym", 1, 525600, dummy_cb)
        assert j_large in adv_scheduler.snooze_jobs

    def test_register_scheduled_jobs_malformed_time_raises(
        self, adv_scheduler: SchedulerService
    ) -> None:
        """Malformed time format in config raises ValueError."""
        async def dummy_cb(stype: str, name: str) -> None:
            pass

        malformed_cfg = {
            "gym": {"time_split1": "invalid_time"},
            "toeic": {"time": "19:25"},
            "major": {"time": "20:40"},
        }

        with pytest.raises(ValueError, match="Invalid time format"):
            adv_scheduler.register_scheduled_jobs(malformed_cfg, dummy_cb)
