# Task Assignment: Survey Phase - Technical Exploration & Library Architecture

Read:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`

Your Working Directory:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/`

Deliverable:
Write a comprehensive technical architecture and dependency investigation report to:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/analysis.md`
and write your completion handoff report to:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/handoff.md`

When done, send a message back to the orchestrator.

## 2026-10-03T09:25:00Z
You are teamwork_preview_explorer for the Survey Phase.
Your assigned working directory is: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/
Please immediately read the authoritative requirements in:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
Also read your dispatch task at:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/DISPATCH.md

Your task:
- Investigate the technical architecture and library integration:
  1. `python-telegram-bot` v20+ ApplicationBuilder, async job queue / integration with APScheduler (or running APScheduler alongside PTB), CommandHandler, CallbackQueryHandler, MessageHandler.
  2. `APScheduler` (v3 AsyncIOScheduler): configuring timezone 'Asia/Ho_Chi_Minh', registering CronTrigger jobs, scheduling dynamic DateTrigger / Interval one-shot snooze jobs with unique job IDs.
  3. `google-genai` SDK: client initialization, model `gemini-2.5-flash`, generate_content or chat sessions, sliding history representation, system instruction for persona, mock strategy for unit tests.
  4. Atomic file writing in Python on Windows & Linux (`tempfile.NamedTemporaryFile` + `os.replace` / `shutil.move`), directory creation, file locking / concurrency considerations.
  5. Test architecture: Pytest with `pytest-asyncio`, creating mock Telegram update/callback query objects and mock bot context, mocking google-genai client without external calls.

Output:
Write your full investigation to:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/analysis.md
and a complete handoff report to:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/handoff.md
Update progress.md in your directory as you work.
When finished, send a message to the orchestrator.
