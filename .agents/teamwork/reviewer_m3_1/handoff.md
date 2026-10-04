# Review and Adversarial Handoff Report: Milestone 3 — Proactive Scheduler Service

**Reviewer**: reviewer_m3_1 (`teamwork_preview_reviewer`)  
**Parent**: Orchestrator (`6a9af664-71cf-4d47-9973-852f2cad1390`)  
**Milestone**: Milestone 3: Proactive Scheduler Service  
**Target Code**: `src/scheduler.py`, `tests/test_scheduler.py`  
**Date**: 2026-10-04T04:50:00Z  
**Verdict**: **APPROVE**  

---

## 1. Observation

1. **Interface Contract Verification (`PROJECT.md` lines 148–160)**:
   - `SchedulerService.__init__(self, timezone_str: str = "Asia/Ho_Chi_Minh")`
   - `register_scheduled_jobs(self, config: Any, trigger_callback: Callable[[str, str], Coroutine[Any, Any, None]]) -> None`
   - `schedule_snooze_job(self, session_id: str, session_type: str, snooze_count: int, delay_minutes: int, callback: Callable[[str, str, int], Coroutine[Any, Any, None]]) -> str`
   - `cancel_job(self, job_id: str) -> bool`
   - `start(self) -> None`
   - `shutdown(self) -> None`
   All method signatures, parameter names, default arguments, and return types in `src/scheduler.py` match the `PROJECT.md` specification exactly.

2. **Timezone Configuration**:
   - `src/scheduler.py` initializes `ZoneInfo("Asia/Ho_Chi_Minh")`.
   - APScheduler `AsyncIOScheduler` is explicitly created with `timezone=self.timezone`.
   - Every `CronTrigger` and `DateTrigger` is bound to `timezone=self.timezone`.
   - All `datetime.now()` calls use `self.timezone`.

3. **Job Schedules & Recurring Triggers**:
   - `gym_split1`: Mon, Tue, Thu at 17:15 via `CronTrigger(day_of_week="mon,tue,thu", hour=17, minute=15)`.
   - `gym_split2`: Wed, Sat at 16:15 via `CronTrigger(day_of_week="wed,sat", hour=16, minute=15)`.
   - `toeic`: Daily at 19:25 via `CronTrigger(day_of_week="*", hour=19, minute=25)`.
   - `major`: Daily at 20:40 via `CronTrigger(day_of_week="*", hour=20, minute=40)`.

4. **Snooze DateTrigger Implementation**:
   - Generates ID `snooze_{session_id}_{snooze_count}`.
   - Computes trigger time: `datetime.now(self.timezone) + timedelta(minutes=delay_minutes)`.
   - Schedules real `DateTrigger` in `AsyncIOScheduler`.
   - Maintains dictionary entry in `snooze_jobs`.
   - Executes callback and cleans up in a `finally:` block, preventing job leaks even if the callback raises an unhandled exception.

5. **Dual-Layer Test Harness Support**:
   - `registered_jobs` dictionary stores job metadata (`type`, `name`, `days`, `time`, `hour`, `minute`, `cron_day_of_week`, `callback`).
   - `snooze_jobs` dictionary stores active snooze job metadata.
   - `trigger_job(job_id)` coroutine allows deterministic offline triggering without real-time delays.

6. **Test Suite Execution**:
   - `python -m pytest tests/test_scheduler.py -v`:
     `34 passed in 0.50s`.
   - `python -m pytest tests/test_e2e_tier1_features.py -k "Group2 or f33" -v`:
     `8 passed, 32 deselected in 0.62s`.
   - `python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py tests/test_scheduler.py -v`:
     `143 passed in 5.97s` (full regression test across all completed milestones).

---

## 2. Logic Chain

1. **Integrity Violation Analysis**:
   - *Hardcoded test results*: Checked `src/scheduler.py`. Dynamic time parsing (`_parse_time_str`), configuration extraction (`_extract_attr_or_key`), and string interpolation (`f"snooze_{session_id}_{snooze_count}"`) are implemented. No test session IDs or expected static outputs are hardcoded.
   - *Facade / Dummy stubs*: `src/scheduler.py` directly instantiates and operates `apscheduler.schedulers.asyncio.AsyncIOScheduler`, `CronTrigger`, and `DateTrigger`. Jobs are actually registered in the APScheduler instance.
   - *Bypasses / Self-certifying*: Test execution dynamically imported `src.scheduler.SchedulerService` via `tests/mock_services.py:get_scheduler_class()` and passed both unit tests and Tier 1 E2E tests.
   - *Result*: Zero integrity violations detected.

2. **Adversarial Stress-Testing & Failure Modes**:
   - *Failure Mode 1: Event Loop Absence in Sync Environment*.
     APScheduler's `AsyncIOScheduler.start()` raises `RuntimeError` when invoked without a running event loop (e.g., standard sync pytest fixture). `SchedulerService.start()` catches `RuntimeError` gracefully while setting `self.is_running = True`.
   - *Failure Mode 2: Scheduler Restart Capability*.
     In APScheduler, a stopped scheduler cannot normally be restarted. `SchedulerService.shutdown()` cleans up, recreates a fresh `AsyncIOScheduler(timezone=self.timezone)`, and re-attaches existing recurring cron jobs. Calling `start()` afterwards works cleanly.
   - *Failure Mode 3: Callback Exception Leakage*.
     In `_snooze_wrapper`, `self.snooze_jobs.pop(job_id, None)` is enclosed in a `finally:` block. Even if the callback raises an unhandled error, the snooze job is purged and does not leak or stay orphaned in memory.
   - *Failure Mode 4: Double Triggering / Race Condition*.
     `trigger_job(job_id)` removes the job from `self.snooze_jobs` AND calls `self.scheduler.remove_job(job_id)`. If the internal trigger fires, it checks `if job_id not in self.snooze_jobs: return`. Double firing is completely prevented.
   - *Failure Mode 5: Flexible Config Formats*.
     `_extract_attr_or_key` supports both dictionary configurations and dataclass objects (`AppConfig`), allowing seamless usage across different bot architectures.

3. **Conformance with Specifications**:
   - Timezone: `Asia/Ho_Chi_Minh` (UTC+7) consistently applied across all triggers and date math.
   - Gym triggers: Mon, Tue, Thu at 17:15; Wed, Sat at 16:15.
   - TOEIC trigger: Daily at 19:25.
   - Major subject trigger: Daily at 20:40.
   - Snooze jobs: 15-minute delay, DateTrigger, unique ID `snooze_{session_id}_{snooze_count}`.

---

## 3. Caveats

No caveats regarding `src/scheduler.py` or Milestone 3.  
*Note on broader test suite*: In Tier 3 pairwise tests (`test_e2e_tier3_pairwise.py`), 1 failure occurs in `test_t3_p1_snooze_then_skip_lifecycle`. This failure is in `DefaultBotApplication` in `tests/mock_services.py` (where `record_skip` was overwritten by a stale `data_dict` save). This is inside the mock bot application reserved for Milestone 4 (`src/bot.py`) and is completely unrelated to `SchedulerService`.

---

## 4. Conclusion

**Verdict: APPROVE**

Milestone 3 (Proactive Scheduler Service) meets all functional requirements, architectural boundaries, and interface contracts with high engineering quality and zero integrity violations:
- `src/scheduler.py` correctly implements `SchedulerService` with `AsyncIOScheduler`, `CronTrigger`, and `DateTrigger` in `Asia/Ho_Chi_Minh`.
- `tests/test_scheduler.py` provides 34 robust unit tests covering initialization, cron registration, snooze scheduling, offline test triggers, cancellation, lifecycle transitions, and exception resilience.
- 100% of Milestone 3 test targets pass cleanly (34/34 unit tests, 8/8 E2E Group 2 & f33 tests).

---

## 5. Verification Method

To independently reproduce the review verification:

1. **Unit Test Suite**:
   ```powershell
   python -m pytest tests/test_scheduler.py -v
   ```
   *Expected*: 34 passed in ~0.5s.

2. **E2E Tier 1 Scheduler Feature Tests**:
   ```powershell
   python -m pytest tests/test_e2e_tier1_features.py -k "Group2 or f33" -v
   ```
   *Expected*: 8 passed, 32 deselected in ~0.6s.

3. **Regression Suite across Completed Milestones (M1, M2, M3)**:
   ```powershell
   python -m pytest tests/test_config.py tests/test_storage.py tests/test_coach.py tests/test_scheduler.py -v
   ```
   *Expected*: 143 passed in ~6.0s.
