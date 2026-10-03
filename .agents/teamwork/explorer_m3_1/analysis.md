# Milestone 3 Architecture Analysis: APScheduler Proactive Scheduler & Cron Triggers

**Author**: Milestone 3 Explorer 1 (`teamwork_preview_explorer`)  
**Target Component**: `src/scheduler.py` & `tests/test_scheduler.py`  
**Date**: 2026-10-03  
**Status**: Completed  

---

## 1. Executive Summary & Objective

Milestone 3 focuses on implementing the proactive scheduling engine for the Autonomous Telegram Accountability Coach. The scheduler is responsible for:
1. Configuring `APScheduler` (`AsyncIOScheduler`) with the IANA timezone `Asia/Ho_Chi_Minh` (UTC+7).
2. Registering recurring `CronTrigger` jobs for:
   - **Gym Split 1**: Mon, Tue, Thu at 17:15
   - **Gym Split 2**: Wed, Sat at 16:15
   - **TOEIC Study Session**: Daily at 19:25 (with dynamic 7-day syllabus rotation)
   - **Major Subject & Game Dev**: Daily at 20:40
3. Registering dynamic one-shot `DateTrigger` jobs for 15-minute snoozes (`snooze_{session_id}_{snooze_count}`).
4. Providing an asynchronous callback dispatch interface matching `PROJECT.md` contracts and satisfying all existing E2E tiers (Tier 1 `test_e2e_tier1_features.py`, Tier 4 `test_e2e_tier4_scenarios.py`).

---

## 2. Environment & Dependency Analysis

### 2.1 Dependencies in `requirements.txt`
- `APScheduler>=3.10.4,<4.0.0`: APScheduler 3.x branch (specifically 3.10.x).
- `tzdata>=2024.1`: IANA timezone database for Windows `ZoneInfo` support.
- `python-telegram-bot>=20.8,<22.0`: Async Telegram bot framework.
- `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`: Async test runner.

### 2.2 APScheduler 3.x Architecture
In APScheduler 3.x:
- `AsyncIOScheduler` (`apscheduler.schedulers.asyncio.AsyncIOScheduler`) is designed to run directly within Python's `asyncio` event loop.
- Default executor is `AsyncIOExecutor`, which schedules coroutine functions (`async def`) using `asyncio.ensure_future` / `asyncio.create_task`.
- Triggers:
  - `CronTrigger` (`apscheduler.triggers.cron.CronTrigger`): Supports cron-like fields (`day_of_week`, `hour`, `minute`, `timezone`).
  - `DateTrigger` (`apscheduler.triggers.date.DateTrigger`): Executes a job once at a specific `run_date` with `timezone`.
- Job removal: `scheduler.remove_job(job_id)` removes a scheduled job.
- State management: `scheduler.running` indicates whether the scheduler loop is active.

---

## 3. Detailed Schedule & Trigger Specifications

All schedules are driven by `config.yaml` / `AppConfig` (`src/config.py`).

| Job ID | Activity Name | Cron Days | Time | Window Display | Session Type |
|---|---|---|---|---|---|
| `gym_split1` | Gym Session | `mon,tue,thu` | 17:15 | 17:30 – 18:30 | `gym` |
| `gym_split2` | Gym Session | `wed,sat` | 16:15 | 16:30 – 17:30 | `gym` |
| `toeic` | TOEIC Study Session | `*` (Daily) | 19:25 | 19:30 – 20:30 | `toeic` |
| `major` | Major Subject Study & Game Dev | `*` (Daily) | 20:40 | 20:45 – 21:45 | `major` |

### 3.1 Time Parsing & Validation
`AppConfig` exposes helper properties on `GymScheduleConfig`, `ToeicScheduleConfig`, and `MajorScheduleConfig`:
- `gym.hour_split1`, `gym.minute_split1`
- `gym.hour_split2`, `gym.minute_split2`
- `toeic.hour`, `toeic.minute`
- `major.hour`, `major.minute`
- `toeic.get_part_for_weekday(weekday: int) -> str`

When creating `CronTrigger`:
```python
# Gym Split 1
CronTrigger(
    day_of_week=config.gym.cron_days_split1,
    hour=config.gym.hour_split1,
    minute=config.gym.minute_split1,
    timezone=self.timezone,
)

# Gym Split 2
CronTrigger(
    day_of_week=config.gym.cron_days_split2,
    hour=config.gym.hour_split2,
    minute=config.gym.minute_split2,
    timezone=self.timezone,
)

# TOEIC (Daily)
CronTrigger(
    hour=config.toeic.hour,
    minute=config.toeic.minute,
    timezone=self.timezone,
)

# Major (Daily)
CronTrigger(
    hour=config.major.hour,
    minute=config.major.minute,
    timezone=self.timezone,
)
```

---

## 4. Test Suite Contract & Dual-Layer Architecture

An essential finding from inspecting `tests/test_e2e_tier1_features.py`, `tests/test_e2e_tier4_scenarios.py`, and `tests/mock_services.py`:
The test suite validates `SchedulerService` through both real operational semantics AND explicit dictionary/method inspection:

1. **Timezone Attribute**:
   `assert scheduler_service.timezone_str == "Asia/Ho_Chi_Minh"`
2. **Registered Jobs Dictionary**:
   `job = scheduler_service.registered_jobs.get("gym_split1")`
   - Must contain: `"type"`, `"name"`, `"days"`, `"time"`, `"callback"`
   - `job["days"]` must contain `"mon,tue,thu"`
   - `job["time"] == "17:15"`
   - Similar entries for `"gym_split2"`, `"toeic"` (days: `"daily"`), `"major"` (days: `"daily"`).
3. **Snooze Jobs Dictionary & Naming**:
   - `job_id = f"snooze_{session_id}_{snooze_count}"`
   - Must be present in `scheduler_service.snooze_jobs[job_id]`
4. **Manual Trigger Hook**:
   `await scheduler_service.trigger_job(job_id)`
   - Used by offline tests to synchronously trigger a job without waiting 15 minutes.
   - For snooze jobs: executes callback `callback(session_id, session_type, snooze_count)` and pops from `snooze_jobs`.
   - For recurring jobs: executes `callback(type, name)`.
5. **Scheduler State Flags**:
   - `scheduler_service.is_running` boolean property.
   - `scheduler_service.start()` and `scheduler_service.shutdown()`.
   - In `test_f33_scheduler_verification`, `start()` and `shutdown()` are called in a synchronous test without a running event loop! The implementation must handle this gracefully without throwing `RuntimeError: There is no current event loop`.

### Architecture Pattern: Dual-Layer Scheduler
To simultaneously satisfy:
- **Real Production Operation**: Real `AsyncIOScheduler` scheduling with `CronTrigger` and `DateTrigger` in the Telegram bot's async loop.
- **Offline E2E Test Compatibility**: Inspection dictionaries (`registered_jobs`, `snooze_jobs`) and manual async trigger execution (`trigger_job`).

`SchedulerService` wraps `AsyncIOScheduler`, mirroring all scheduled tasks in memory.

---

## 5. Callback Dispatcher Architecture

### 5.1 Recurring Push Callback
Contract from `PROJECT.md`:
```python
trigger_callback: Callable[[str, str], Coroutine[Any, Any, None]]
```
Arguments: `(session_type: str, session_title: str)`
- When Gym split 1 fires: `trigger_callback("gym", config.gym.name)`
- When Gym split 2 fires: `trigger_callback("gym", config.gym.name)`
- When TOEIC fires: `trigger_callback("toeic", config.toeic.name)`
- When Major fires: `trigger_callback("major", config.major.name)`

In the Telegram bot (`src/bot.py`), `trigger_callback` constructs the message using the template from `config.yaml`, attaches the 3-button inline keyboard (`[✅ Đã hoàn thành]`, `[⏳ Xin lùi 15 phút]`, `[🛑 Hôm nay nghỉ (Có lý do)]`), and pushes to `ALLOWED_CHAT_ID`. For TOEIC, it resolves `{topic}` via `config.toeic.get_part_for_weekday(datetime.now(tz).weekday())`.

### 5.2 One-Shot Snooze Callback
Contract from `PROJECT.md`:
```python
callback: Callable[[str, str, int], Coroutine[Any, Any, None]]
```
Arguments: `(session_id: str, session_type: str, snooze_count: int)`
- Delay: `delay_minutes` (default 15 minutes).
- `run_at = datetime.now(self.timezone) + timedelta(minutes=delay_minutes)`.
- When fired via APScheduler or `trigger_job`: executes `callback(session_id, session_type, snooze_count)`.
- Cleans up `snooze_jobs[job_id]`.

---

## 6. Implementation Blueprint (`src/scheduler.py`)

```python
"""Proactive Scheduler service powered by APScheduler AsyncIOScheduler.

Manages recurring cron triggers for Gym, TOEIC, and Major subject sessions
in Asia/Ho_Chi_Minh timezone, dynamic 15-minute snooze jobs, and async callbacks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import inspect
import logging
from typing import Any, Callable, Coroutine, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """Async scheduler service managing recurring and one-shot accountability jobs."""

    def __init__(self, timezone_str: str = "Asia/Ho_Chi_Minh") -> None:
        self.timezone_str: str = timezone_str
        try:
            self.timezone: ZoneInfo = ZoneInfo(timezone_str)
        except (ZoneInfoNotFoundError, Exception) as e:
            raise ValueError(f"Invalid timezone specified: {timezone_str}") from e

        self.scheduler: AsyncIOScheduler = self._create_scheduler()
        self.registered_jobs: Dict[str, Dict[str, Any]] = {}
        self.snooze_jobs: Dict[str, Dict[str, Any]] = {}
        self.is_running: bool = False

    def _create_scheduler(self) -> AsyncIOScheduler:
        """Creates a fresh AsyncIOScheduler instance configured with timezone."""
        return AsyncIOScheduler(timezone=self.timezone)

    def register_scheduled_jobs(
        self,
        config: Any,
        trigger_callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        """Registers recurring cron jobs for Gym (split 1 & 2), TOEIC, and Major subject."""
        # 1. Gym Split 1 (Mon, Tue, Thu)
        gym_cfg = config.gym
        self.registered_jobs["gym_split1"] = {
            "type": "gym",
            "name": gym_cfg.name,
            "days": gym_cfg.cron_days_split1,
            "time": gym_cfg.time_split1,
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="gym_split1",
            session_type="gym",
            session_name=gym_cfg.name,
            day_of_week=gym_cfg.cron_days_split1,
            hour=gym_cfg.hour_split1,
            minute=gym_cfg.minute_split1,
            callback=trigger_callback,
        )

        # 2. Gym Split 2 (Wed, Sat)
        self.registered_jobs["gym_split2"] = {
            "type": "gym",
            "name": gym_cfg.name,
            "days": gym_cfg.cron_days_split2,
            "time": gym_cfg.time_split2,
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="gym_split2",
            session_type="gym",
            session_name=gym_cfg.name,
            day_of_week=gym_cfg.cron_days_split2,
            hour=gym_cfg.hour_split2,
            minute=gym_cfg.minute_split2,
            callback=trigger_callback,
        )

        # 3. TOEIC Study Session (Daily)
        toeic_cfg = config.toeic
        self.registered_jobs["toeic"] = {
            "type": "toeic",
            "name": toeic_cfg.name,
            "days": "daily",
            "time": toeic_cfg.time,
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="toeic",
            session_type="toeic",
            session_name=toeic_cfg.name,
            day_of_week=None,
            hour=toeic_cfg.hour,
            minute=toeic_cfg.minute,
            callback=trigger_callback,
        )

        # 4. Major Subject Study Session (Daily)
        major_cfg = config.major
        self.registered_jobs["major"] = {
            "type": "major",
            "name": major_cfg.name,
            "days": "daily",
            "time": major_cfg.time,
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="major",
            session_type="major",
            session_name=major_cfg.name,
            day_of_week=None,
            hour=major_cfg.hour,
            minute=major_cfg.minute,
            callback=trigger_callback,
        )

    def _add_cron_job(
        self,
        job_id: str,
        session_type: str,
        session_name: str,
        day_of_week: Optional[str],
        hour: int,
        minute: int,
        callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        """Helper to safely attach a CronTrigger job to internal AsyncIOScheduler."""
        trigger = CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone=self.timezone,
        )

        async def _job_wrapper() -> None:
            try:
                res = callback(session_type, session_name)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.error(f"Error executing scheduled job {job_id}: {e}", exc_info=True)

        try:
            self.scheduler.add_job(
                _job_wrapper,
                trigger=trigger,
                id=job_id,
                name=session_name,
                replace_existing=True,
            )
        except Exception as e:
            logger.warning(f"Could not attach job {job_id} to APScheduler instance: {e}")

    def schedule_snooze_job(
        self,
        session_id: str,
        session_type: str,
        snooze_count: int,
        delay_minutes: int,
        callback: Callable[[str, str, int], Coroutine[Any, Any, None]],
    ) -> str:
        """Schedules a one-shot DateTrigger snooze reminder after delay_minutes."""
        job_id = f"snooze_{session_id}_{snooze_count}"
        run_at = datetime.now(self.timezone) + timedelta(minutes=delay_minutes)

        self.snooze_jobs[job_id] = {
            "session_id": session_id,
            "session_type": session_type,
            "snooze_count": snooze_count,
            "delay_minutes": delay_minutes,
            "run_at": run_at,
            "callback": callback,
        }

        trigger = DateTrigger(run_date=run_at, timezone=self.timezone)

        async def _snooze_wrapper() -> None:
            try:
                res = callback(session_id, session_type, snooze_count)
                if inspect.isawaitable(res):
                    await res
            except Exception as e:
                logger.error(f"Error executing snooze job {job_id}: {e}", exc_info=True)
            finally:
                self.snooze_jobs.pop(job_id, None)

        try:
            self.scheduler.add_job(
                _snooze_wrapper,
                trigger=trigger,
                id=job_id,
                name=f"Snooze {session_id} #{snooze_count}",
                replace_existing=True,
            )
        except Exception as e:
            logger.warning(f"Could not attach snooze job {job_id} to APScheduler: {e}")

        return job_id

    def cancel_job(self, job_id: str) -> bool:
        """Cancels a scheduled or snooze job by job_id."""
        cancelled = False
        if job_id in self.snooze_jobs:
            del self.snooze_jobs[job_id]
            cancelled = True
        if job_id in self.registered_jobs:
            del self.registered_jobs[job_id]
            cancelled = True

        try:
            self.scheduler.remove_job(job_id)
            cancelled = True
        except Exception:
            pass

        return cancelled

    async def trigger_job(self, job_id: str) -> None:
        """Test harness entrypoint: manually fires a registered or snooze job."""
        if job_id in self.snooze_jobs:
            job = self.snooze_jobs[job_id]
            res = job["callback"](job["session_id"], job["session_type"], job["snooze_count"])
            if inspect.isawaitable(res):
                await res
            self.snooze_jobs.pop(job_id, None)
        elif job_id in self.registered_jobs:
            job = self.registered_jobs[job_id]
            res = job["callback"](job["type"], job["name"])
            if inspect.isawaitable(res):
                await res

    def start(self) -> None:
        """Starts the scheduler. Handles synchronous test environments gracefully."""
        self.is_running = True
        try:
            if not self.scheduler.running:
                self.scheduler.start()
        except RuntimeError:
            # Raised if no active event loop exists in the calling thread (e.g. sync unit test)
            pass

    def shutdown(self) -> None:
        """Shuts down the scheduler and clears pending snooze jobs."""
        self.is_running = False
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
        except Exception:
            pass
        self.snooze_jobs.clear()
        # Prepare a fresh instance in case start() is called again
        self.scheduler = self._create_scheduler()
```

---

## 7. Unit Test Blueprint (`tests/test_scheduler.py`)

A standalone unit test suite covering 100% of `src/scheduler.py` logic:
1. `test_scheduler_init_default_timezone`
2. `test_scheduler_init_invalid_timezone`
3. `test_register_scheduled_jobs_all_sessions`
4. `test_gym_split1_cron_fields`
5. `test_gym_split2_cron_fields`
6. `test_toeic_cron_fields`
7. `test_major_cron_fields`
8. `test_schedule_snooze_job_date_trigger`
9. `test_trigger_snooze_job_callback_and_cleanup`
10. `test_trigger_registered_job_callback`
11. `test_cancel_snooze_job`
12. `test_cancel_registered_job`
13. `test_cancel_nonexistent_job`
14. `test_scheduler_start_shutdown_lifecycle`
15. `test_scheduler_restart_after_shutdown`
16. `test_callback_exception_safety`
