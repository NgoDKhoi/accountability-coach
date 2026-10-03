# Task Assignment: Survey Phase - Interface Boundaries, Schemas & Lifecycle

Read:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`

Your Working Directory:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/`

Deliverable:
Write a comprehensive schemas, contracts, interface boundaries, and lifecycle analysis to:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/analysis.md`
and write your completion handoff report to:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/handoff.md`

When done, send a message back to the orchestrator.


## 2026-10-03T09:25:00Z
You are teamwork_preview_explorer for the Survey Phase.
Your assigned working directory is: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/
Please immediately read the authoritative requirements in:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
Also read your dispatch task at:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/DISPATCH.md

Your task:
- Define the schemas, interface boundaries, and data flow:
  1. `config.yaml` exact structure: schedules (gym, toeic with 7-day parts rotation, major), prompts, timezone, limits.
  2. `.env` and `.env.example`: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, ALLOWED_CHAT_ID.
  3. `data/records.json` schema: streak tracking (current_streak, last_completed_date), check-in history, active sessions state (session_id, status: pending/snoozed/completed/skipped, snooze_count, reminder_type, timestamp).
  4. Interface contracts between modules:
     - Config module (`src/config.py`)
     - Storage module (`src/storage.py`)
     - AI Coach module (`src/coach.py`)
     - Scheduler module (`src/scheduler.py`)
     - Bot handlers & UI module (`src/bot.py`)
  5. Deployment scripts: Dockerfile (python:3.11-slim or similar), docker-compose.yml, start.sh, start.bat.

Output:
Write your full schema and interface design to:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/analysis.md
and a complete handoff report to:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/handoff.md
Update progress.md in your directory as you work.
When finished, send a message to the orchestrator.
