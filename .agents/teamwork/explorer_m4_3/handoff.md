# Handoff Report — Milestone 4: Entrypoint `src/main.py` & Test Suite `tests/test_bot.py`

**Agent**: `explorer_m4_3` (teamwork_preview_explorer)  
**Date**: 2026-10-04  
**Project Root**: `c:/Users/khoi1/Documents/antigravity/serene-bohr`  
**Handoff Type**: Hard (Task Complete)

---

## 1. Observation

1. **Authoritative Contracts in `PROJECT.md`**:
   - `PROJECT.md:164-168`: Contract for `src/bot.py`:
     ```python
     from telegram.ext import Application
     from typing import Any

     def build_application(config: Any, storage: Any, coach: Any, scheduler: Any) -> Application: ...
     ```
   - `PROJECT.md:149-160`: Contract for `src/scheduler.py`:
     ```python
     class SchedulerService:
         def __init__(self, timezone_str: str = "Asia/Ho_Chi_Minh"): ...
         def register_scheduled_jobs(self, config: Any, trigger_callback: Callable[[str, str], Coroutine[Any, Any, None]]) -> None: ...
         def schedule_snooze_job(self, session_id: str, session_type: str, snooze_count: int, delay_minutes: int, callback: Callable[[str, str, int], Coroutine[Any, Any, None]]) -> str: ...
         def cancel_job(self, job_id: str) -> bool: ...
         def start(self) -> None: ...
         def shutdown(self) -> None: ...
     ```

2. **Existing Implementation Status in `src/`**:
   - `src/config.py`: Complete `AppConfig`, `GymScheduleConfig`, `ToeicScheduleConfig`, `MajorScheduleConfig`, `load_config()`.
   - `src/storage.py`: Complete `AtomicJsonStore` with crash-safe atomic replace, `StreakData`, `SessionStatus`.
   - `src/coach.py`: Complete `AICoachService` with Gemini 2.5 Flash, sliding deque (maxlen 10), excuse/legitimate classifier with 2-minute micro-habit, and offline fallbacks.
   - `src/scheduler.py`: Complete `SchedulerService` with `AsyncIOScheduler` in `Asia/Ho_Chi_Minh`, 4 cron jobs (`gym_split1`, `gym_split2`, `toeic`, `major`), DateTrigger snooze jobs, and trigger hooks.
   - `src/bot.py` and `src/main.py`: Not yet present in repository root.

3. **E2E Testing Expectations in `tests/test_e2e_tier*.py`**:
   - `tests/test_e2e_tier1_features.py:38-40`:
     ```python
     update = make_text_update(chat_id=app_config.allowed_chat_id, text="/start")
     resp = await bot_application.process_update(update)
     assert resp is not None
     assert "Chào mừng" in resp["text"] or "Kỷ Luật" in resp["text"]
     ```
   - `tests/test_e2e_tier1_features.py:60-64`:
     ```python
     assert bot_application is not None
     assert bot_application.config.allowed_chat_id == app_config.allowed_chat_id
     assert bot_application.storage is atomic_store
     assert bot_application.coach is not None
     assert bot_application.scheduler is not None
     ```
   - `tests/test_e2e_tier1_features.py:504-509`:
     ```python
     for bad_id in [1, 99999, -1001234567, 123456788]:
         update = make_text_update(chat_id=bad_id, text="/status")
         resp = await bot_application.process_update(update)
         assert "từ chối" in resp["text"] or "Access denied" in resp["text"]
     ```
   - `tests/test_e2e_tier4_scenarios.py:174-180`:
     ```python
     build_fn = get_build_application_fn()
     new_bot_app = build_fn(app_config, atomic_store, coach_service, scheduler_service)
     r_status = await new_bot_app.process_update(
         make_text_update(chat_id=app_config.allowed_chat_id, text="/status", bot=new_bot_app.bot)
     )
     ```

4. **Offline Test Harness in `tests/mock_services.py`**:
   - `tests/mock_services.py:477-677`: `DefaultBotApplication` implements reference dispatcher returning response dictionaries (`{"text": ..., "chat_id": ...}`) for `send_message` and `edit_message_text`.
   - `tests/mock_services.py:699-706`:
     ```python
     def get_build_application_fn() -> Any:
         try:
             from src.bot import build_application
             return build_application
         except ImportError:
             def _build_app(config: Any, storage: Any, coach: Any, scheduler: Any) -> DefaultBotApplication:
                 return DefaultBotApplication(config, storage, coach, scheduler)
             return _build_app
     ```

---

## 2. Logic Chain

1. **Need for Dual-Mode Dispatcher in `src/bot.py`**:
   - Observation 3 shows that all 63 E2E tests in Tiers 1–4 call `resp = await bot_application.process_update(update)` where `update` is a `MockUpdate` instance, and they assert `resp["text"]`.
   - Standard `python-telegram-bot` `Application.process_update(update)` expects a `telegram.Update` instance and returns `None` (calling handlers asynchronously).
   - Therefore, `src/bot.py`'s `build_application` must return an application that provides a `process_update(update)` method returning dictionary results for tests while also providing standard PTB application hooks (`bot`, `run_polling`, `add_handler`) for production.

2. **Composition & Execution Architecture for `src/main.py`**:
   - Observation 1 and 2 define the contracts for `AppConfig`, `AtomicJsonStore`, `AICoachService`, `SchedulerService`, and `build_application`.
   - `src/main.py` must act as the composition root:
     1. Load `config = load_config()`.
     2. Initialize `storage = AtomicJsonStore(config.records_file)`.
     3. Initialize `coach = AICoachService(api_key=config.gemini_api_key, model_name=config.gemini_model, config=config)`.
     4. Initialize `scheduler = SchedulerService(timezone_str=config.timezone)`.
     5. Build `bot_app = build_application(config, storage, coach, scheduler)`.
     6. Connect proactive push callback via `scheduler.register_scheduled_jobs(config, on_cron_trigger)`.
     7. Provide both an asynchronous `run_async(config, stop_event)` for programmatic control and a synchronous CLI entrypoint `main()` handling `SIGINT`/`SIGTERM` cleanly.
     8. Ensure Windows compatibility: Avoid `loop.add_signal_handler` which raises `NotImplementedError` on Windows `ProactorEventLoop`. Instead use standard `signal.signal(signal.SIGINT, ...)` with `loop.call_soon_threadsafe`.

3. **Standalone Unit Test Suite Design for `tests/test_bot.py`**:
   - Based on Observations 1–4 and Milestone 4 requirements, `tests/test_bot.py` must cover 8 distinct test classes:
     1. `TestBotSecurityWhitelist`: Whitelist authorization filter (authorized accepted, unauthorized blocked, adversarial chat IDs, zero Gemini token leakage).
     2. `TestBotCommandHandlers`: Core commands (`/start`, `/help`, `/status` with empty, active, and lapsed streak states).
     3. `TestBotCallbackDone`: Completion callback query, streak increment, AI praise, idempotent duplicate clicks.
     4. `TestBotCallbackSnooze`: 1st snooze (Warning 1), 2nd snooze (Warning 2), 3rd snooze (strictly blocked, alert raised, no job added).
     5. `TestBotCallbackSkipAndReason`: Skip flow, transition to `awaiting_reason`, excuse evaluation triggering 2m micro-habit, legitimate evaluation approved, empty reason resilience.
     6. `TestBotFreeFormChat`: Reactive chat outside reminders routed to `coach.chat`, context accumulation, offline fallback.
     7. `TestBotProactivePush`: Proactive reminder formatting for Gym (weekday splits), TOEIC (7-day dynamic rotation), Major subject, and 15-minute snooze reminder pushes.
     8. `TestMainLifecycle`: Subsystem wiring, cron job registration, and graceful shutdown.

---

## 3. Caveats

1. **Real Telegram Bot Token**: In production, `TELEGRAM_BOT_TOKEN` must be a valid token from BotFather. In unit tests and E2E suites, all tests run 100% offline using `MockTelegramBot`.
2. **Persistent Awaiting Reason State**: The `awaiting_reason` dictionary must be stored in `AtomicJsonStore` (under key `"awaiting_reason"`) rather than solely in memory, so that process restarts (as tested in Tier 4 Scenario 4) do not lose user state.
3. **External Dependencies**: No new external dependencies are required beyond those declared in `requirements.txt`.

---

## 4. Conclusion

1. Milestone 4 implementation is completely specified with full compatibility across M1, M2, M3, and all E2E test suites.
2. Complete blueprints for `src/main.py` and `tests/test_bot.py` have been formulated and documented in `.agents/teamwork/explorer_m4_3/analysis.md`.
3. Worker agents implementing M4 can proceed with `src/bot.py`, `src/main.py`, and `tests/test_bot.py` with zero ambiguity.

---

## 5. Verification Method

To independently verify after implementation:
1. Run Milestone 4 unit test suite:
   ```bash
   python -m pytest tests/test_bot.py -v
   ```
2. Run Tier 1 E2E feature suite:
   ```bash
   python -m pytest tests/test_e2e_tier1_features.py -v
   ```
3. Run all 4 E2E tiers:
   ```bash
   python -m pytest tests/test_e2e_tier1_features.py tests/test_e2e_tier2_boundaries.py tests/test_e2e_tier3_pairwise.py tests/test_e2e_tier4_scenarios.py -v
   ```
4. Verify entrypoint starts and exits cleanly without errors:
   ```bash
   python -c "import src.main; print('src.main import successful')"
   ```
5. Invalidation conditions:
   - Any test fails or attempts network calls.
   - Unauthorized chat ID invokes Gemini API.
   - Snooze exceeds 2 attempts without being blocked.
