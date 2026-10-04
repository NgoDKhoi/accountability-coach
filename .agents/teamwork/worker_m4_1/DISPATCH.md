## 2026-10-04T05:04:35Z
You are worker_m4_1 (teamwork_preview_worker).
Your working directory is: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m4_1/
Project root is: c:/Users/khoi1/Documents/antigravity/serene-bohr

Read the authoritative requirements FIRST:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m4_1/analysis.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m4_2/analysis.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m4_3/analysis.md

Your task is to implement Milestone 4: Telegram Bot Core & Interactive Inline Actions.
Write ownership:
- You exclusively own: `src/bot.py`, `src/main.py`, and `tests/test_bot.py`.
- You MUST NOT modify: `src/config.py`, `src/storage.py`, `src/coach.py`, `src/scheduler.py`, or existing M1/M2/M3 test files.

Implementation details:
1. `src/bot.py`:
   - `BotApplication(Application)` extending python-telegram-bot Application with `@property def bot` and `@bot.setter def bot` (required by conftest.py mock injection).
   - `build_application(config: Any, storage: Any, coach: Any, scheduler: Any) -> BotApplication` exposing `app.config`, `app.storage`, `app.coach`, `app.scheduler`.
   - Security whitelist gate: strictly validates `int(update.effective_chat.id) == int(config.allowed_chat_id)`. Rejects unauthorized messages with warning, unauthorized callbacks with alert, without calling Gemini or altering storage.
   - Command handlers: `/start` (mission, list /status and /help), `/help` (guidelines, buttons explanation), `/status` (reports current streak, best streak, last completed date).
   - Inline keyboard builder: `make_inline_action_keyboard(session_id)` with `done:{session_id}`, `snooze:{session_id}`, `skip:{session_id}`.
   - Callback handlers:
     - `done`: calls `storage.record_completion()`, requests `coach.get_congratulation()`, edits message.
     - `snooze`: if snooze count < max_snoozes (2), records snooze in storage, schedules `scheduler.schedule_snooze_job()`, edits message with warning & reattached buttons; if >= 2, alerts and rejects with firm warning without scheduling.
     - `skip`: enters `awaiting_reason` (persisted in storage under "awaiting_reason"), prompts for justification text.
   - Text message handler:
     - If `awaiting_reason` active: routes to `coach.evaluate_skip_reason()`. If EXCUSE: delivers 2-minute micro-habit. If LEGITIMATE: approves skip and calls `storage.record_skip()`. Clears `awaiting_reason` in storage.
     - If outside `awaiting_reason` and not command: routes to `coach.chat()`.
   - Proactive notification push callback: `send_session_reminder(session_type, session_title)` formatting message from config and attaching inline keyboard.
   - Universal `process_update(update)`: asynchronous dispatcher returning the outbound response dictionary for tests (`{"text": ..., "chat_id": ...}`).
2. `src/main.py`:
   - Composition root: `load_config()`, `AtomicJsonStore()`, `AICoachService()`, `SchedulerService()`, `build_application()`.
   - Wires proactive push callbacks into scheduler.
   - Starts scheduler, starts bot application.
   - Windows-safe signal handling (`SIGINT`, `SIGTERM`), graceful shutdown.
3. `tests/test_bot.py`:
   - Comprehensive unit test suite covering whitelist rejection, commands, callbacks, snooze limit, skip flow (excuse & legitimate), free chat, and lifecycle.
4. Verification:
   - Run `pytest tests/test_bot.py -v`.
   - Run `pytest tests/test_e2e_tier1_features.py -v`.
   - Run all 4 E2E tiers: `pytest tests/test_e2e_tier1_features.py tests/test_e2e_tier2_boundaries.py tests/test_e2e_tier3_pairwise.py tests/test_e2e_tier4_scenarios.py -v`.
   - Ensure 100% tests pass.
