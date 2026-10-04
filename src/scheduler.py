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


def _parse_time_str(time_str: str) -> tuple[int, int]:
    """Helper to parse 'HH:MM' time string into (hour, minute) integers."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: '{time_str}', expected 'HH:MM'")
    return int(parts[0]), int(parts[1])


def _extract_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Helper to extract a property or dictionary key gracefully."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class SchedulerService:
    """Async scheduler service managing recurring and one-shot accountability jobs.

    Adheres strictly to the PROJECT.md interface contract and supports both
    real APScheduler execution in an async event loop and deterministic offline
    test harness triggering.
    """

    def __init__(self, timezone_str: str = "Asia/Ho_Chi_Minh") -> None:
        if isinstance(timezone_str, ZoneInfo):
            self.timezone: ZoneInfo = timezone_str
            self.timezone_str: str = getattr(timezone_str, "key", "Asia/Ho_Chi_Minh")
        else:
            self.timezone_str: str = str(timezone_str)
            try:
                self.timezone: ZoneInfo = ZoneInfo(self.timezone_str)
            except (ZoneInfoNotFoundError, KeyError, Exception) as exc:
                raise ValueError(f"Invalid timezone specified: {timezone_str}") from exc

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
        if config is None:
            raise ValueError("Configuration cannot be None")
        if not callable(trigger_callback):
            raise TypeError("trigger_callback must be a callable")

        gym_cfg = _extract_attr_or_key(config, "gym")
        toeic_cfg = _extract_attr_or_key(config, "toeic")
        major_cfg = _extract_attr_or_key(config, "major")

        # 1. Gym Split 1 (Mon, Tue, Thu)
        gym_name = _extract_attr_or_key(gym_cfg, "name", "Gym Session")
        cron_days_split1 = _extract_attr_or_key(gym_cfg, "cron_days_split1", "mon,tue,thu")
        time_split1 = _extract_attr_or_key(gym_cfg, "time_split1", "17:15")
        h_split1 = _extract_attr_or_key(gym_cfg, "hour_split1")
        m_split1 = _extract_attr_or_key(gym_cfg, "minute_split1")
        if h_split1 is None or m_split1 is None:
            h_split1, m_split1 = _parse_time_str(time_split1)

        self.registered_jobs["gym_split1"] = {
            "type": "gym",
            "name": gym_name,
            "days": cron_days_split1,
            "time": time_split1,
            "hour": h_split1,
            "minute": m_split1,
            "cron_day_of_week": cron_days_split1,
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="gym_split1",
            session_type="gym",
            session_name=gym_name,
            day_of_week=cron_days_split1,
            hour=h_split1,
            minute=m_split1,
            callback=trigger_callback,
        )

        # 2. Gym Split 2 (Wed, Sat)
        cron_days_split2 = _extract_attr_or_key(gym_cfg, "cron_days_split2", "wed,sat")
        time_split2 = _extract_attr_or_key(gym_cfg, "time_split2", "16:15")
        h_split2 = _extract_attr_or_key(gym_cfg, "hour_split2")
        m_split2 = _extract_attr_or_key(gym_cfg, "minute_split2")
        if h_split2 is None or m_split2 is None:
            h_split2, m_split2 = _parse_time_str(time_split2)

        self.registered_jobs["gym_split2"] = {
            "type": "gym",
            "name": gym_name,
            "days": cron_days_split2,
            "time": time_split2,
            "hour": h_split2,
            "minute": m_split2,
            "cron_day_of_week": cron_days_split2,
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="gym_split2",
            session_type="gym",
            session_name=gym_name,
            day_of_week=cron_days_split2,
            hour=h_split2,
            minute=m_split2,
            callback=trigger_callback,
        )

        # 3. TOEIC Study Session (Daily)
        toeic_name = _extract_attr_or_key(toeic_cfg, "name", "TOEIC Study Session")
        toeic_time = _extract_attr_or_key(toeic_cfg, "time", "19:25")
        toeic_h = _extract_attr_or_key(toeic_cfg, "hour")
        toeic_m = _extract_attr_or_key(toeic_cfg, "minute")
        if toeic_h is None or toeic_m is None:
            toeic_h, toeic_m = _parse_time_str(toeic_time)

        self.registered_jobs["toeic"] = {
            "type": "toeic",
            "name": toeic_name,
            "days": "daily",
            "time": toeic_time,
            "hour": toeic_h,
            "minute": toeic_m,
            "cron_day_of_week": "*",
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="toeic",
            session_type="toeic",
            session_name=toeic_name,
            day_of_week="*",
            hour=toeic_h,
            minute=toeic_m,
            callback=trigger_callback,
        )

        # 4. Major Subject Study Session (Daily)
        major_name = _extract_attr_or_key(major_cfg, "name", "Major Subject Study & Game Dev")
        major_time = _extract_attr_or_key(major_cfg, "time", "20:40")
        major_h = _extract_attr_or_key(major_cfg, "hour")
        major_m = _extract_attr_or_key(major_cfg, "minute")
        if major_h is None or major_m is None:
            major_h, major_m = _parse_time_str(major_time)

        self.registered_jobs["major"] = {
            "type": "major",
            "name": major_name,
            "days": "daily",
            "time": major_time,
            "hour": major_h,
            "minute": major_m,
            "cron_day_of_week": "*",
            "callback": trigger_callback,
        }
        self._add_cron_job(
            job_id="major",
            session_type="major",
            session_name=major_name,
            day_of_week="*",
            hour=major_h,
            minute=major_m,
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
            except Exception as exc:
                logger.error(
                    "Error executing scheduled job %s: %s",
                    job_id,
                    exc,
                    exc_info=True,
                )

        try:
            self.scheduler.add_job(
                _job_wrapper,
                trigger=trigger,
                id=job_id,
                name=session_name,
                replace_existing=True,
            )
        except Exception as exc:
            logger.warning("Could not attach job %s to APScheduler instance: %s", job_id, exc)

    def schedule_snooze_job(
        self,
        session_id: str,
        session_type: str,
        snooze_count: int,
        delay_minutes: int,
        callback: Callable[[str, str, int], Coroutine[Any, Any, None]],
    ) -> str:
        """Schedules a one-shot DateTrigger snooze reminder after delay_minutes."""
        if not callable(callback):
            raise TypeError("Snooze callback must be callable")

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
            if job_id not in self.snooze_jobs:
                return
            try:
                res = callback(session_id, session_type, snooze_count)
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:
                logger.error("Error executing snooze job %s: %s", job_id, exc, exc_info=True)
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
        except Exception as exc:
            logger.warning("Could not attach snooze job %s to APScheduler: %s", job_id, exc)

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
            job = self.snooze_jobs.pop(job_id)
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
            res = job["callback"](job["session_id"], job["session_type"], job["snooze_count"])
            if inspect.isawaitable(res):
                await res
        elif job_id in self.registered_jobs:
            job = self.registered_jobs[job_id]
            res = job["callback"](job["type"], job["name"])
            if inspect.isawaitable(res):
                await res
        else:
            logger.warning("trigger_job called for unregistered job_id: %s", job_id)

    def _re_attach_registered_jobs(self) -> None:
        """Re-attaches stored recurring jobs to a freshly initialized scheduler."""
        for job_id, info in self.registered_jobs.items():
            self._add_cron_job(
                job_id=job_id,
                session_type=info["type"],
                session_name=info["name"],
                day_of_week=info.get("cron_day_of_week"),
                hour=info["hour"],
                minute=info["minute"],
                callback=info["callback"],
            )

    def start(self) -> None:
        """Starts the scheduler. Handles synchronous test environments gracefully."""
        self.is_running = True
        try:
            if not self.scheduler.running:
                self.scheduler.start()
        except RuntimeError:
            # Raised if no active event loop exists in calling thread (e.g. sync unit test)
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
        self._re_attach_registered_jobs()
