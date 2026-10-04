## 2026-10-04T05:40:24Z
You are worker_m4_r2 (teamwork_preview_worker).
Your working directory is: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m4_r2/
Project root is: c:/Users/khoi1/Documents/antigravity/serene-bohr

Read the authoritative requirements, audit report, and blueprint FIRST:
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/auditor_m4_1/handoff.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m4_r2_1/analysis.md
- c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m4_r2_1/handoff.md

Your task is to remediate Milestone 4 by implementing genuine python-telegram-bot Application architecture in `src/bot.py` and `src/main.py`:
Write ownership:
- You exclusively own: `src/bot.py`, `src/main.py`, and `tests/test_bot.py`.
- You MUST NOT modify: `src/config.py`, `src/storage.py`, `src/coach.py`, `src/scheduler.py`, or existing M1/M2/M3 test files.

Specific requirements per `explorer_m4_r2_1/analysis.md`:
1. `src/bot.py`:
   - Initialize authentic PTB `Application` using `Application.builder().token(config.bot_token).application_class(BotApplication).build()` (or proper `super().__init__` call), initializing real PTB internal structures (`updater`, `update_queue`, handler registries).
   - ZERO imports from `tests/` in `src/`. Completely remove `from tests.mock_services import MockTelegramBot`. In production, `self.bot` delegates to `super().bot`.
   - Implement `@bot.setter` so that test fixtures (`conftest.py`) can inject `mock_bot` seamlessly.
   - Register authentic PTB handlers via `self.add_handler`:
     - `CommandHandler("start", self._cmd_start)`
     - `CommandHandler("help", self._cmd_help)`
     - `CommandHandler("status", self._cmd_status)`
     - `CallbackQueryHandler(self._handle_callback)`
     - `MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message)`
   - Dual-mode `process_update(update)`:
     - If `isinstance(update, MockUpdate)` or mock bot injected: process update through the internal handler router returning outbound response dictionary (`{"text": ..., "chat_id": ...}`) for 100% backward compatibility with all offline test suites (`tests/test_e2e_tier*.py`).
     - If real `telegram.Update`: delegate to `await super().process_update(update)`.
   - Attach `reply_markup=make_inline_action_keyboard(session_id)` to 3rd snooze rejection message.
2. `src/main.py`:
   - Implement authentic live polling in `run_async()`:
     ```python
     await bot_app.initialize()
     await bot_app.start()
     await bot_app.updater.start_polling()
     ```
   - Graceful shutdown on `stop_event.wait()`:
     ```python
     if bot_app.updater and bot_app.updater.running:
         await bot_app.updater.stop()
     if bot_app.running:
         await bot_app.stop()
     await bot_app.shutdown()
     ```
3. Verification:
   - Run `pytest tests/test_bot.py -v`.
   - Run `pytest tests/test_e2e_tier1_features.py -v`.
   - Run all 4 E2E tiers: `pytest tests/test_e2e_tier1_features.py tests/test_e2e_tier2_boundaries.py tests/test_e2e_tier3_pairwise.py tests/test_e2e_tier4_scenarios.py -v`.
   - Ensure 100% tests pass and zero integrity violations remain.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When completed, write your handoff report to `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m4_r2/handoff.md` and notify parent via send_message.
