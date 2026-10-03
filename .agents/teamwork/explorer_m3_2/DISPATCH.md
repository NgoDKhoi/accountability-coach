# Dispatch: Milestone 3 Explorer 2 — TOEIC Syllabus Rotation & Dynamic Snooze DateTrigger

## 2026-10-03T12:41:47Z

## Task Assignment
- Role: `teamwork_preview_explorer`
- Working Directory: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m3_2/`
- Mission: Investigate dynamic 7-day TOEIC syllabus resolution (Monday: Part 1 through Sunday: Part 7) and dynamic one-shot `DateTrigger` snooze job scheduling and cancellation in `src/scheduler.py`.

## Required Reading
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md` (TOEIC syllabus rotation, 15m snooze job)
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md` (Features 11, 15, 17, and interface contract)

## Investigation Focus
1. 7-day TOEIC syllabus resolution:
   - Python `datetime.now(tz).weekday()` (0 = Monday -> Part 1, ..., 6 = Sunday -> Part 7).
   - Mapping from `config.toeic.syllabus_rotation` list.
   - Dynamic prompt/title construction for the daily TOEIC reminder.
2. Dynamic Snooze Job Scheduling:
   - `schedule_snooze_job(session_id: str, session_type: str, snooze_count: int, delay_minutes: int, callback: Callable)`
   - `DateTrigger(run_date=now + timedelta(minutes=delay_minutes), timezone=tz)`
   - Return unique `job_id: str`.
3. Job cancellation:
   - `cancel_job(job_id: str) -> bool` when user clicks "Done" or "Skip" before a snooze job fires.
4. Deliver `analysis.md` and `handoff.md` with concrete logic and blueprints for Worker.
