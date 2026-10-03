# BRIEFING — 2026-10-03T12:45:30Z

## Mission
Investigate APScheduler AsyncIOScheduler architecture in src/scheduler.py, CronTrigger setup for Gym split, TOEIC, and Major subject in Asia/Ho_Chi_Minh timezone, and callback dispatcher interface.

## 🔒 My Identity
- Archetype: teamwork_preview_explorer
- Roles: explorer, investigator, synthesizer
- Working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/
- Original parent: ac41226a-6cc6-45bc-9027-605104e502f4
- Milestone: Milestone 3 (Explorer 1)

## 🔒 Key Constraints
- Read-only investigation — do NOT implement source code
- Files in .agents/teamwork/ must contain only agent metadata
- Deliver analysis.md and handoff.md in working directory
- Conformance to PROJECT.md interface contract for SchedulerService
- Strict adherence to Asia/Ho_Chi_Minh timezone and exact trigger requirements

## Current Parent
- Conversation ID: ac41226a-6cc6-45bc-9027-605104e502f4
- Updated: not yet

## Investigation State
- **Explored paths**:
  - `ORIGINAL_REQUEST.md` (R2, R3, R5, R6)
  - `orchestrator/PROJECT.md` (Features 7-12, 17, 33 and SchedulerService contract)
  - `requirements.txt` (APScheduler>=3.10.4,<4.0.0, tzdata>=2024.1)
  - `config.yaml` (schedules: gym, toeic, major)
  - `src/config.py` (GymScheduleConfig, ToeicScheduleConfig, MajorScheduleConfig, AppConfig)
  - `src/coach.py` and `src/storage.py` (architecture reference)
  - `tests/mock_services.py` (DefaultSchedulerService implementation reference)
  - `tests/test_e2e_tier1_features.py` (Group 2 tests f07, f08, f09, f10, f11, f12, f17, f33)
  - `tests/test_e2e_tier4_scenarios.py` (Scenario 3 snooze integration test)
- **Key findings**:
  - `APScheduler` is 3.10.4 (3.x branch). Needs `AsyncIOScheduler` from `apscheduler.schedulers.asyncio`.
  - Timezone must be `ZoneInfo("Asia/Ho_Chi_Minh")`.
  - CronTriggers:
    - `gym_split1`: `day_of_week="mon,tue,thu"`, `hour=17`, `minute=15`.
    - `gym_split2`: `day_of_week="wed,sat"`, `hour=16`, `minute=15`.
    - `toeic`: daily (`day_of_week="*"` or None), `hour=19`, `minute=25`.
    - `major`: daily (`day_of_week="*"` or None), `hour=20`, `minute=40`.
  - In addition to internal `AsyncIOScheduler`, `SchedulerService` must maintain `registered_jobs` dict, `snooze_jobs` dict, `timezone_str`, `is_running`, `trigger_job(job_id)` async method for testing parity with test suite.
  - Snooze jobs: one-shot `DateTrigger` at `now + timedelta(minutes=delay_minutes)` with ID format `snooze_{session_id}_{snooze_count}`.
- **Unexplored areas**:
  - None; all scheduler interaction touchpoints across tiers 1-4 and interfaces are identified.

## Key Decisions Made
- Architecture blueprint will provide full dual-layer design: real APScheduler `AsyncIOScheduler` triggers + test-harness dictionaries (`registered_jobs`, `snooze_jobs`, `trigger_job`) to ensure 100% test compatibility while providing real background scheduling when running live.

## Artifact Index
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/BRIEFING.md` — persistent working memory
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/progress.md` — heartbeat and progress tracking
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/analysis.md` — deep investigation report
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_1/handoff.md` — 5-component handoff report for worker
