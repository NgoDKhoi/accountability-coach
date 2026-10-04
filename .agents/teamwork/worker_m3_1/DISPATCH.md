## 2026-10-04T03:37:27Z
You are worker_m3_1 (teamwork_preview_worker).
Your working directory is: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m3_1/
Project root is: c:/Users/khoi1/Documents/antigravity/serene-bohr

Read the authoritative requirements FIRST:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/analysis.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/handoff.md

Your task is to implement Milestone 3: Proactive Scheduler Service.
Write ownership:
- You exclusively own: `src/scheduler.py` and `tests/test_scheduler.py`.
- You MUST NOT modify: `src/config.py`, `src/storage.py`, `src/coach.py`, or existing M1/M2 tests.

Implementation details:
1. `src/scheduler.py`: Implement `SchedulerService` wrapping `APScheduler` (`AsyncIOScheduler`) with timezone `Asia/Ho_Chi_Minh` (UTC+7).
   - Cron triggers: Gym Split 1 (Mon, Tue, Thu at 17:15), Gym Split 2 (Wed, Sat at 16:15), TOEIC (Daily at 19:25), Major subject (Daily at 20:40).
   - One-shot DateTrigger for snooze jobs (`snooze_{session_id}_{snooze_count}`) with 15-minute delay and cleanup.
   - Dual-layer compatibility: maintain `registered_jobs` and `snooze_jobs` dicts, and async `trigger_job(job_id)` method for testing.
   - Robust lifecycle: `start()` and `shutdown()` handling synchronous test environments gracefully without uncaught RuntimeError.
2. `tests/test_scheduler.py`: Comprehensive standalone unit tests covering all functions, triggers, cancellations, callbacks, error handling, and lifecycle.
3. Verification: Run pytest on `tests/test_scheduler.py` and `tests/test_e2e_tier1_features.py` Group 2 (Features 7, 8, 9, 10, 11, 12, 17, 33). Ensure all tests pass.
