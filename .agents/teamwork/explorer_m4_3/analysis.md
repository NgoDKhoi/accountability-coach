# Milestone 4 Deep-Dive Analysis: Entrypoint `src/main.py` & Test Suite `tests/test_bot.py`

**Agent**: `explorer_m4_3` (teamwork_preview_explorer)  
**Date**: 2026-10-04  
**Project**: Autonomous Telegram Personal Accountability Coach (`serene-bohr`)  
**Scope**: Milestone 4 Entrypoint (`src/main.py`), Test Suite (`tests/test_bot.py`), Push Notification Callbacks, and Lifecycle Orchestration.

---

## 1. Executive Summary

Milestone 4 completes the core user interaction layer by implementing:
1. `src/bot.py`: The Telegram bot dispatcher adhering to `build_application(config, storage, coach, scheduler)`, enforcing the `ALLOWED_CHAT_ID` whitelist security filter, command routing (`/start`, `/help`, `/status`), interactive inline actions (`done:`, `snooze:`, `skip:`), and two-way coaching dialogs.
2. `src/main.py`: The executable application entrypoint orchestrating configuration loading, persistence initialization, AI service connection, proactive scheduler setup, and graceful shutdown handling.
3. `tests/test_bot.py`: A comprehensive, standalone, 100% offline unit test suite validating security whitelist filtering, command handlers, callback state machine transitions, excuse vs. legitimate reason evaluations, free-form chat, and proactive notification push delivery.

This report establishes the technical architecture, execution flow, signal handling, and comprehensive test suite design for Milestone 4, ensuring full compatibility with previously verified Milestones (M1: Storage/Config, M2: AI Coach, M3: Proactive Scheduler) and existing E2E test suites (Tiers 1–4).

---

## 2. Architecture & Design of `src/main.py`

### 2.1 Subsystem Composition & Dependency Injection

The entrypoint `src/main.py` coordinates five decoupled subsystems:
```
                     +---------------------------------------+
                     |         src/config.py (load_config)    |
                     +---------------------------------------+
                                         |
          +------------------------------+------------------------------+
          |                              |                              |
          v                              v                              v
+--------------------+        +--------------------+        +--------------------+
|  src/storage.py    |        |    src/coach.py    |        |  src/scheduler.py  |
| (AtomicJsonStore)  |        |  (AICoachService)  |        | (SchedulerService) |
+--------------------+        +--------------------+        +--------------------+
          |                              |                              |
          +------------------------------+------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |          src/bot.py                   |
                     |      (build_application)              |
                     +---------------------------------------+
                                         |
                                         v
                     +---------------------------------------+
                     |           Proactive Callback          |
                     |     (Push reminders to Telegram)      |
                     +---------------------------------------+
```

1. **Configuration**:
   - Calls `load_config(config_path, env_path)` with optional environment overrides (`CONFIG_PATH`, `ENV_PATH`).
   - Retrieves typed `AppConfig` containing bot token, Gemini API key, allowed chat ID, schedule cron rules, prompts, and fallbacks.
2. **Storage**:
   - Instantiates `AtomicJsonStore(file_path=config.records_file)`.
   - Guarantees `data/` directory and `records.json` schema presence automatically.
3. **AI Coach Service**:
   - Instantiates `AICoachService(api_key=config.gemini_api_key, model_name=config.gemini_model, config=config)`.
   - Injected with sliding context deque (max 10 entries), persona prompts, and offline fallback heuristics.
4. **Proactive Scheduler**:
   - Instantiates `SchedulerService(timezone_str=config.timezone)` in `Asia/Ho_Chi_Minh` timezone.
5. **Bot Application**:
   - Instantiates `application = build_application(config=config, storage=storage, coach=coach, scheduler=scheduler)`.

---

### 2.2 Proactive Notification Push Callback & Button Attachment

The scheduler fires recurring cron jobs (`gym_split1`, `gym_split2`, `toeic`, `major`) and one-shot 15-minute snooze jobs (`snooze_{session_id}_{count}`). `src/main.py` connects the scheduler to outbound Telegram messages via a proactive push callback.

#### Callback Implementation Contract:
```python
async def push_proactive_reminder(session_type: str, session_name: str) -> None:
    """Invoked by SchedulerService when a recurring cron trigger fires."""
    now = datetime.now(ZoneInfo(config.timezone))
    today_str = now.strftime("%Y-%m-%d")
    date_compact = now.strftime("%Y%m%d")
    session_id = f"{session_type}_{date_compact}"

    # 1. Resolve domain-specific message content
    if session_type == "gym":
        # Check weekday split: Mon(0), Tue(1), Thu(3) -> Split 1; Wed(2), Sat(5) -> Split 2
        weekday = now.weekday()
        window = config.gym.window_split1 if weekday in (0, 1, 3) else config.gym.window_split2
        text = config.gym.message_template.format(window=window)
    elif session_type == "toeic":
        part_topic = config.toeic.get_part_for_weekday(now.weekday())
        weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        text = config.toeic.message_template.format(
            window=config.toeic.window,
            weekday_name=weekday_names[now.weekday()],
            part_topic=part_topic,
        )
    elif session_type == "major":
        text = config.major.message_template.format(window=config.major.window)
    else:
        text = f"⏰ *NHẮC NHỞ HOÀN THÀNH PHIÊN*: {session_name}"

    # 2. Attach standard 3-button interactive inline keyboard
    keyboard = make_inline_action_keyboard(session_id)

    # 3. Deliver push notification directly to authorized chat ID
    await bot.send_message(
        chat_id=config.allowed_chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
```

#### Snooze Job Callback Contract:
When a snooze job triggers (after 15 minutes), the scheduler invokes `_snooze_job_callback(session_id, session_type, snooze_count)`:
```python
async def push_snooze_reminder(session_id: str, session_type: str, snooze_count: int) -> None:
    """Invoked by SchedulerService when a 15-minute DateTrigger snooze fires."""
    text = (
        f"⏰ *HẾT 15 PHÚT LÙI GIỜ!*\n"
        f"Phiên `{session_type}` đang chờ bạn hoàn thành. (Lần lùi: {snooze_count}/{config.max_snoozes})"
    )
    keyboard = make_inline_action_keyboard(session_id)
    await bot.send_message(
        chat_id=config.allowed_chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
```

---

### 2.3 Async Run Loop & Graceful Shutdown Handling

#### The Lifecycle Challenge:
1. `APScheduler` (`AsyncIOScheduler`) requires an active, running event loop to schedule and execute background tasks.
2. `python-telegram-bot` (v20+) `Application.run_polling()` is blocking, handles its own event loop and signal registration, but does not natively know about external schedulers.
3. Windows OS limitation: Default `ProactorEventLoop` on Windows raises `NotImplementedError` if `loop.add_signal_handler(signal.SIGINT, ...)` is called.

#### Recommended Solution: Dual Lifecycle Architecture:

```python
async def run_async_application(
    config: Optional[AppConfig] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Asynchronous entrypoint suitable for programmatic control and testing."""
    if config is None:
        config = load_config()

    storage = AtomicJsonStore(file_path=config.records_file)
    coach = AICoachService(api_key=config.gemini_api_key, model_name=config.gemini_model, config=config)
    scheduler = SchedulerService(timezone_str=config.timezone)
    bot_app = build_application(config=config, storage=storage, coach=coach, scheduler=scheduler)

    # Register proactive push notifications
    async def _on_cron_trigger(session_type: str, session_name: str) -> None:
        await send_proactive_reminder(bot_app.bot, config, session_type, session_name)

    scheduler.register_scheduled_jobs(config, _on_cron_trigger)

    # Start proactive scheduler
    scheduler.start()
    logger.info("Scheduler started successfully in %s timezone.", config.timezone)

    try:
        if hasattr(bot_app, "start") and callable(bot_app.start):
            await bot_app.start()
        if hasattr(bot_app, "updater") and bot_app.updater:
            await bot_app.updater.start_polling()

        logger.info("Bot application started. Polling for updates...")

        if stop_event is None:
            stop_event = asyncio.Event()

        await stop_event.wait()
    finally:
        logger.info("Initiating graceful shutdown...")
        # 1. Stop scheduler first to prevent new triggers during shutdown
        scheduler.shutdown()
        logger.info("Scheduler stopped.")

        # 2. Stop bot polling and application
        if hasattr(bot_app, "updater") and bot_app.updater and bot_app.updater.running:
            await bot_app.updater.stop()
        if hasattr(bot_app, "stop") and callable(bot_app.stop):
            await bot_app.stop()
        if hasattr(bot_app, "shutdown") and callable(bot_app.shutdown):
            await bot_app.shutdown()
        logger.info("Bot application shutdown cleanly.")
```

#### Standard Main Entrypoint (`main()`):
For command-line invocation (`python src/main.py`):
```python
def main() -> None:
    """Synchronous process entrypoint configuring signal handlers for Windows & Unix."""
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("main")
    logger.info("Starting Autonomous Telegram Personal Accountability Coach...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _handle_shutdown(sig, frame):
        logger.info("Received termination signal %s. Shutting down...", sig)
        loop.call_soon_threadsafe(stop_event.set)

    # Cross-platform signal registration
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    try:
        loop.run_until_complete(run_async_application(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process interrupted by user.")
    finally:
        loop.close()
        logger.info("Event loop closed. Bye!")
```

---

## 3. Architecture & Test Design for `tests/test_bot.py`

### 3.1 Test Objectives
`tests/test_bot.py` must provide a 100% offline, deterministic, standalone unit test suite that isolates `src/bot.py` and `src/main.py` without requiring external network connections.

### 3.2 Test Suite Structure & Coverage Matrix

| Test Class | Focus Area | Features Covered | Assertions / Verification Target |
|---|---|---|---|
| `TestBotSecurityWhitelist` | Security gate & access control | F1, F36 | Authorized ID allowed; unauthorized IDs (zero, negative, off-by-one) rejected with warning; coach NEVER called on unauthorized requests; session state untouched. |
| `TestBotCommandHandlers` | Bot commands (`/start`, `/help`, `/status`) | F4, F5, F6 | `/start` delivers greeting + command list; `/help` details 3 buttons and snooze/skip mechanics; `/status` formats active/historical streak, best streak, and total completions. |
| `TestBotCallbackDone` | Completion flow | F14, F34 | Increments streak in `AtomicJsonStore`; fetches congratulation praise from AI coach; edits message text with Markdown; idempotent on duplicate clicks. |
| `TestBotCallbackSnooze` | 15m delay & limit cap | F15, F16, F17 | Snooze 1: increments count, schedules DateTrigger job, edits text (Warning 1); Snooze 2: schedules 2nd job, edits text (Warning 2); Snooze 3: BLOCKED, alert sent, text edited, no job added. |
| `TestBotCallbackSkipAndReason` | Justification evaluation | F18, F19, F20, F21 | Clicks Skip -> sets `awaiting_reason`; EXCUSE -> deconstructed + 2m micro-habit challenge; LEGITIMATE -> approved + skipped status in store; whitespace handled safely. |
| `TestBotFreeFormChat` | Reactive AI coach dialog | F23, F24, F25, F26 | User messages outside reminders routed to `coach.chat`; replies returned; context window history retained; offline fallback on timeout. |
| `TestBotProactivePush` | Scheduled reminders & keyboards | F8, F9, F10, F11, F12, F13 | Keyboard has 3 buttons with encoded callback data; Gym window template; TOEIC 7-day dynamic part rotation; Major window template; Snooze reminder push. |
| `TestMainLifecycle` | Application assembly & shutdown | F3, F7, F33 | Composition of all 5 modules; jobs registered; scheduler started; graceful shutdown without task leakage. |

---

### 3.3 Detailed Specification of Test Methods

#### Category 1: Whitelist Authorization
1. `test_whitelist_authorized_chat_accepted`:
   - Send text `/start` from `chat_id == config.allowed_chat_id`.
   - Assert response contains `"Chào mừng"` or `"Kỷ Luật"`.
2. `test_whitelist_unauthorized_chat_rejected_without_coach_call`:
   - Send text from `chat_id == 88888888` (not allowed).
   - Assert response contains `"từ chối"` or `"Access denied"`.
   - Assert `coach.client.aio.models.call_history` is empty (zero token/cost leakage).
3. `test_whitelist_unauthorized_callback_rejected`:
   - Send callback query `done:session_123` from unauthorized ID.
   - Assert `answer_callback_query` called with `show_alert=True`.
   - Assert storage record is NOT created.
4. `test_whitelist_boundary_chat_ids`:
   - Test adversarial IDs: `0`, `-1`, `-1001928374`, `allowed_id + 1`, `allowed_id - 1`.
   - All must be rejected immediately.

#### Category 2: Command Handlers
1. `test_start_command_greeting_and_commands`:
   - `/start` returns coach mission, `/status`, `/help`.
2. `test_help_command_explains_mechanics`:
   - `/help` explains `Đã hoàn thành`, `Xin lùi 15 phút`, `Hôm nay nghỉ`, and max 2 snoozes.
3. `test_status_command_zero_streak`:
   - Fresh database -> streak: 0, best: 0, total: 0, last: None / "Chưa có".
4. `test_status_command_active_streak`:
   - Complete session today -> streak: 1, best: 1, total: 1, last: today.
5. `test_status_command_lapsed_streak`:
   - Completion dated 5 days ago -> effective streak: 0, best streak: 1.

#### Category 3: Callback Queries: Done Flow
1. `test_done_callback_records_completion`:
   - Callback `done:gym_20261004` -> storage `record_completion` called.
   - Message edited with congratulations and current streak.
2. `test_done_callback_idempotent_duplicate_click`:
   - Two consecutive Done clicks on same session do not double-increment streak.
3. `test_done_callback_offline_coach_fallback`:
   - Inject error into coach -> completion still recorded, fallback congratulations returned.

#### Category 4: Callback Queries: Snooze Flow
1. `test_snooze_1st_attempt`:
   - Callback `snooze:session_toeic`.
   - Storage snooze_count becomes 1.
   - Scheduler registers `snooze_session_toeic_1` with 15m delay.
   - Message edited with `"Lần 1/2"`, 3 buttons re-attached.
2. `test_snooze_2nd_attempt`:
   - Second callback `snooze:session_toeic`.
   - Storage snooze_count becomes 2.
   - Scheduler registers `snooze_session_toeic_2`.
   - Message edited with `"Lần 2/2"` (escalating warning).
3. `test_snooze_3rd_attempt_blocked`:
   - Third callback `snooze:session_toeic`.
   - Storage snooze_count remains 2.
   - No new scheduler job created.
   - Alert shown: `"Đã đạt giới hạn lùi giờ!"`.
   - Message edited: `"HẾT QUYỀN LÙI GIỜ"`.

#### Category 5: Callback Queries: Skip with Reason & Routing
1. `test_skip_callback_triggers_awaiting_reason`:
   - Callback `skip:session_major`.
   - Storage `awaiting_reason` set to `{"session_id": "session_major", "session_type": "major"}`.
   - Message edited prompting for explanation.
2. `test_skip_reason_excuse_enforces_micro_habit`:
   - With `awaiting_reason` active, user sends: `"Mệt quá lười code tiếp"`.
   - AI evaluates classification as `EXCUSE`.
   - Status in storage recorded as `SKIPPED`, classification `EXCUSE`.
   - Bot replies with 2-minute micro-habit challenge (`"THỬ THÁCH MICRO-HABIT 2 PHÚT"`).
   - `awaiting_reason` cleared.
3. `test_skip_reason_legitimate_approved`:
   - User sends: `"Bị sốt xuất huyết 39 độ nằm viện"`.
   - AI evaluates classification as `LEGITIMATE`.
   - Status recorded as `SKIPPED`, classification `LEGITIMATE`.
   - Bot replies approving skip without streak penalty.
   - `awaiting_reason` cleared.
4. `test_skip_reason_whitespace_treated_as_excuse`:
   - User sends `"   \n   "`.
   - Handled safely as excuse without crash.

#### Category 6: Reactive Free-Form Coaching Chat
1. `test_free_form_chat_invokes_coach`:
   - User sends `"Làm sao để tập trung làm game?"`.
   - Bot replies with coach answer prefixed with `"🤖 Coach:"`.
2. `test_free_form_chat_context_window`:
   - Sliding deque in coach records interactions up to max context size.
3. `test_free_form_chat_offline_fallback`:
   - Coach raises timeout -> returns fallback `"AI tạm thời gián đoạn, nhưng kỷ luật của bạn thì không!"`.

#### Category 7: Proactive Push Reminders
1. `test_inline_action_keyboard_structure`:
   - Verify 3 buttons with exact labels and callbacks (`done:`, `snooze:`, `skip:`).
2. `test_proactive_push_gym_split_selection`:
   - Verify workout window matches Monday vs. Wednesday split.
3. `test_proactive_push_toeic_7day_syllabus_rotation`:
   - Verify dynamic rotation maps day 0 -> Part 1 through day 6 -> Part 7.
4. `test_snooze_reminder_push`:
   - Verify snooze push reminder formats current snooze count and re-attaches buttons.

#### Category 8: Main Application Composition
1. `test_main_composition_wiring`:
   - Verify all 5 subsystems are wired and interconnected cleanly.
2. `test_scheduler_registration_contains_all_four_cron_jobs`:
   - Verify `gym_split1`, `gym_split2`, `toeic`, `major` registered.
3. `test_graceful_shutdown_cleans_scheduler`:
   - Starting then shutting down cleanly stops jobs.

---

## 4. Test Doubles & Harness Integration (`tests/mock_services.py`)

### 4.1 Relationship to `src/bot.py` and `DefaultBotApplication`

In `tests/mock_services.py`, `DefaultBotApplication` exists as a reference implementation of the bot dispatcher.
Line 699:
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

### 4.2 Architectural Contract for `src/bot.py`
To satisfy both production Telegram execution and all 63 E2E tests in Tiers 1–4, `src/bot.py` must fulfill two requirements:
1. **Contract Attributes**: The application instance returned by `build_application` must have:
   - `app.config = config`
   - `app.storage = storage`
   - `app.coach = coach`
   - `app.scheduler = scheduler`
   - `app.bot = bot` (or injectable `app.bot = mock_bot`)
2. **`process_update(update)` Dispatcher**:
   - `async def process_update(self, update: Any) -> Optional[Dict[str, Any]]`
   - Must intercept `MockUpdate` or `telegram.Update`, evaluate security whitelist, execute command/callback/text handler, and return the response dictionary (`{"text": ..., "message_id": ...}`).
   - This ensures 100% compatibility with all E2E tests (`assert resp is not None`, `assert "..." in resp["text"]`).

---

## 5. Implementation Blueprint

### 5.1 Proposed Blueprint: `src/main.py`
```python
"""Entrypoint for Autonomous Telegram Personal Accountability Coach.

Orchestrates configuration loading, persistence, AI coach service,
proactive APScheduler jobs, Telegram bot application, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
import signal
import sys
from typing import Any, Optional
from zoneinfo import ZoneInfo

from src.config import AppConfig, load_config
from src.storage import AtomicJsonStore
from src.coach import AICoachService
from src.scheduler import SchedulerService
from src.bot import build_application, make_inline_action_keyboard

logger = logging.getLogger("main")


async def format_proactive_message(config: AppConfig, session_type: str, session_name: str) -> str:
    """Formats markdown reminder text based on schedule configuration."""
    now = datetime.now(ZoneInfo(config.timezone))
    if session_type == "gym":
        weekday = now.weekday()
        window = config.gym.window_split1 if weekday in (0, 1, 3) else config.gym.window_split2
        return config.gym.message_template.format(window=window)
    elif session_type == "toeic":
        part_topic = config.toeic.get_part_for_weekday(now.weekday())
        weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
        return config.toeic.message_template.format(
            window=config.toeic.window,
            weekday_name=weekday_names[now.weekday()],
            part_topic=part_topic,
        )
    elif session_type == "major":
        return config.major.message_template.format(window=config.major.window)
    return f"⏰ *NHẮC NHỞ HOÀN THÀNH PHIÊN*: {session_name}"


async def send_proactive_reminder(
    bot: Any,
    config: AppConfig,
    session_type: str,
    session_name: str,
) -> None:
    """Dispatches proactive reminder with 3 inline action buttons to allowed chat."""
    now = datetime.now(ZoneInfo(config.timezone))
    session_id = f"{session_type}_{now.strftime('%Y%m%d')}"
    text = await format_proactive_message(config, session_type, session_name)
    keyboard = make_inline_action_keyboard(session_id)

    try:
        await bot.send_message(
            chat_id=config.allowed_chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        logger.info("Proactive reminder sent for %s (%s).", session_type, session_id)
    except Exception as exc:
        logger.error("Failed to send proactive reminder: %s", exc, exc_info=True)


def create_system(
    config: Optional[AppConfig] = None,
    storage: Optional[AtomicJsonStore] = None,
    coach: Optional[AICoachService] = None,
    scheduler: Optional[SchedulerService] = None,
    bot: Optional[Any] = None,
) -> tuple[Any, SchedulerService, AppConfig]:
    """Assembles all application subsystems with dependency injection."""
    if config is None:
        config = load_config()

    if storage is None:
        storage = AtomicJsonStore(file_path=config.records_file)

    if coach is None:
        coach = AICoachService(
            api_key=config.gemini_api_key,
            model_name=config.gemini_model,
            config=config,
        )

    if scheduler is None:
        scheduler = SchedulerService(timezone_str=config.timezone)

    bot_app = build_application(
        config=config,
        storage=storage,
        coach=coach,
        scheduler=scheduler,
    )
    if bot is not None and hasattr(bot_app, "bot"):
        bot_app.bot = bot

    # Register proactive cron triggers with push callback
    async def _on_cron_trigger(session_type: str, session_name: str) -> None:
        await send_proactive_reminder(bot_app.bot, config, session_type, session_name)

    scheduler.register_scheduled_jobs(config, _on_cron_trigger)
    return bot_app, scheduler, config


async def run_async(
    config: Optional[AppConfig] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Runs the asynchronous bot loop and proactive scheduler."""
    bot_app, scheduler, app_config = create_system(config=config)

    scheduler.start()
    logger.info("Scheduler started in %s timezone.", app_config.timezone)

    try:
        if hasattr(bot_app, "start") and callable(bot_app.start):
            await bot_app.start()
        if hasattr(bot_app, "updater") and bot_app.updater:
            await bot_app.updater.start_polling()

        logger.info("Telegram Bot active. Listening for updates...")
        if stop_event is None:
            stop_event = asyncio.Event()

        await stop_event.wait()
    finally:
        logger.info("Shutting down bot application...")
        scheduler.shutdown()
        if hasattr(bot_app, "updater") and bot_app.updater and bot_app.updater.running:
            await bot_app.updater.stop()
        if hasattr(bot_app, "stop") and callable(bot_app.stop):
            await bot_app.stop()
        if hasattr(bot_app, "shutdown") and callable(bot_app.shutdown):
            await bot_app.shutdown()
        logger.info("Shutdown completed cleanly.")


def main() -> None:
    """Command-line entrypoint for execution."""
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Booting Autonomous Telegram Coach...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _on_signal(sig, frame):
        logger.info("Signal %s received. Stopping...", sig)
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        loop.run_until_complete(run_async(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process halted.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
```

---

## 6. Synthesis & Recommendations for Worker Agents

1. **Strict Decoupling**: Keep `src/bot.py` pure and agnostic of CLI execution; keep `src/main.py` as the composition root.
2. **Double Dispatch Compatibility**: Ensure `src/bot.py`'s `build_application` provides the `process_update(update)` method returning dict representations (`{"text": ..., ...}`) to pass all 63 E2E tests and `tests/test_bot.py`.
3. **Persisted Awaiting State**: When a user clicks `skip:`, persist `awaiting_reason` into `storage.save_data()` so that bot process crashes or restarts do not lose user context (validated by Tier 4 Scenario 4).
4. **Offline Resilience**: When Gemini API encounters rate limits or network drops during skip evaluations or chat, seamlessly fall back to `classify_skip_reason_offline` and configured fallbacks without raising uncaught exceptions.
5. **Clean Test Suite**: Implement `tests/test_bot.py` with the 8 specified test categories, leveraging existing fixtures in `conftest.py` and mocks in `mock_services.py` for 100% zero-network pass rate.
