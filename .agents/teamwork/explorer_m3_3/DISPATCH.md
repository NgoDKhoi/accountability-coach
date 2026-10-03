# Dispatch: Milestone 3 Explorer 3 — Timezone Safety, Clock Mocking & Unit Test Suite

## Task Assignment
- Role: `teamwork_preview_explorer`
- Working Directory: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_3/`
- Mission: Investigate timezone verification (`Asia/Ho_Chi_Minh`), clock virtualization / mocking for time-advancement testing, and design the unit test suite for `tests/test_scheduler.py`.

## Required Reading
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md`

## Investigation Focus
1. Timezone verification:
   - Ensure jobs strictly evaluate in `Asia/Ho_Chi_Minh` (UTC+7) across all operating systems.
   - Day-of-week boundaries: ensure UTC vs local midnight differences do not trigger gym or TOEIC on wrong days.
2. Clock virtualization & deterministic offline test strategy:
   - How unit tests in `tests/test_scheduler.py` can test cron triggers, snooze job executions, and job cancellations without waiting real minutes.
   - Use of `freezegun` or mock clock or direct job trigger invocation.
3. Unit Test Suite Architecture (`tests/test_scheduler.py`):
   - Design test classes covering:
     - Initialization and timezone validation
     - Scheduled job registration (Gym Mon/Tue/Thu, Gym Wed/Sat, TOEIC daily, Major daily)
     - TOEIC 7-day syllabus rotation resolution across all 7 weekdays
     - Dynamic snooze job scheduling with `DateTrigger`
     - Snooze job execution and callback invocation
     - Snooze job cancellation
     - Lifecycle start and shutdown
4. Deliver `analysis.md` and `handoff.md` with complete unit test blueprints.


## 2026-10-03T12:41:47Z
You are teamwork_preview_explorer for Milestone 3 (Explorer 3).
Your working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_3/
Please read:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_3/DISPATCH.md

Investigate timezone verification (Asia/Ho_Chi_Minh), clock virtualization / mocking for offline testing, and design the unit test suite architecture for tests/test_scheduler.py.
Deliver analysis.md and handoff.md in your directory. When done, message the orchestrator.
