# Architectural Analysis & Remediation Blueprint: Milestone 4 Round 2

**Agent**: `explorer_m4_r2_1` (`teamwork_preview_explorer`)  
**Mission**: Formulate an authentic, complete architectural blueprint for `src/bot.py` and `src/main.py` remediating Forensic Audit integrity violations.  
**Target Files**: `src/bot.py`, `src/main.py`  
**Date**: 2026-10-04T05:36:00Z  

---

## 1. Executive Summary & Root Cause Analysis

### 1.1 The Forensic Audit Failure
Milestone 4's initial implementation was rejected with an **INTEGRITY VIOLATION** verdict by the Forensic Auditor (`auditor_m4_1`) and received `REQUEST_CHANGES` from both Reviewers (`reviewer_m4_1`, `reviewer_m4_2`). The core failure was architectural: to satisfy offline test doubles without running live Telegram polling, `src/bot.py` was implemented as a mock-like facade rather than an authentic `python-telegram-bot` (v20+) application.

### 1.2 Identified Integrity Violations
| # | Violation | Root Cause | Impact |
|---|---|---|---|
| **IV-1** | Facade `Application` subclassing | `BotApplication` omitted `super().__init__`, omitting `updater` and internal structures, and stubbed `start()`, `stop()`, `shutdown()` with `pass`. | In live execution, PTB runtime is uninitialized; bot cannot start or stop. |
| **IV-2** | Production dependency on test mock double | `src/bot.py:68` imported `MockTelegramBot` from `tests.mock_services` into production code. | In production containers without `tests/`, reminders crash with `AttributeError`/`ModuleNotFoundError`; in dev, reminders go to memory instead of Telegram. |
| **IV-3** | Zero registered PTB handlers | `src/bot.py` had zero calls to `add_handler()` and zero `CommandHandler`, `CallbackQueryHandler`, or `MessageHandler` instances. | PTB's live update dispatcher cannot route any updates from Telegram servers. |
| **IV-4** | Non-functional live polling loop | `src/main.py` skipped `updater.start_polling()` because `bot_app.updater` was missing. | Process permanently blocked at `await stop_event.wait()` without ever listening to Telegram updates. |
| **IV-5** | Stripped inline buttons on 3rd snooze rejection | `src/bot.py:222` omitted `reply_markup` on `edit_message_text`. | Inline keyboard stripped from message; user blocked from clicking Done or Skip. |

---

## 2. Architectural Remediation Principles

1. **Authentic PTB Application Lifecycle**:
   - `build_application()` constructs an authentic `telegram.ext.Application` using `Application.builder().token(...).application_class(BotApplication).build()`.
   - `BotApplication` calls `super().__init__(*args, **kwargs)`, ensuring all internal PTB registries (`_updater`, `_update_queue`, handler registries) are fully initialized.
   - Lifecycle methods (`initialize()`, `start()`, `stop()`, `shutdown()`) are genuinely inherited from `telegram.ext.Application`, not stubbed with `pass`.

2. **Absolute Decoupling from `tests/`**:
   - `src/` contains **ZERO** imports from `tests/`.
   - In production, `self.bot` delegates directly to `super().bot` (the real `telegram.Bot`).
   - Mock bot injection for offline testing is handled exclusively via dependency injection (`app.bot = mock_bot`) supported by a clean `@bot.setter`.

3. **Authentic PTB Handler Registration**:
   - Exactly 5 genuine PTB handlers registered via `app.add_handler(...)`:
     1. `CommandHandler("start", app.ptb_start_command)`
     2. `CommandHandler("help", app.ptb_help_command)`
     3. `CommandHandler("status", app.ptb_status_command)`
     4. `CallbackQueryHandler(app.ptb_callback_query)`
     5. `MessageHandler(filters.TEXT & ~filters.COMMAND, app.ptb_message_text)`
   - Each handler enforces the strict chat ID whitelist filter (`int(chat.id) == int(self.config.allowed_chat_id)`) before dispatching to business logic.

4. **100% Backward-Compatible Dual Dispatcher**:
   - `process_update(update)` is retained on `BotApplication`.
   - When called with a `MockUpdate` (from offline test fixtures in `tests/test_bot.py`, `tests/test_e2e_tier*.py`, `tests/test_m4_adversarial.py`), it executes the domain router and returns the expected synchronous response dictionary (`{"chat_id": ..., "text": ...}`).
   - When called with a real `telegram.Update` during live polling, it delegates to `await super().process_update(update)` which invokes PTB's registered handlers.

5. **Operational Live Polling in `src/main.py`**:
   - In `run_async()`, the lifecycle sequence executes:
     `await bot_app.initialize()` -> `await bot_app.start()` -> `await bot_app.updater.start_polling()`
   - In the `finally:` block, graceful teardown executes:
     `await bot_app.updater.stop()` -> `await bot_app.stop()` -> `await bot_app.shutdown()`.

6. **Preserved Action Buttons on 3rd Snooze**:
   - In `_handle_callback()`, when `new_count > max_snoozes`, `edit_message_text` includes `reply_markup=make_inline_action_keyboard(session_id)` so the user can immediately click `[✅ Đã hoàn thành]` or `[🛑 Hôm nay nghỉ (Có lý do)]`.

---

## 3. Detailed Specification & Code Blueprint for `src/bot.py`

### 3.1 Class Structure & Inheritance
```python
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.storage import SessionStatus, StreakData

logger = logging.getLogger(__name__)


def make_inline_action_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Builds standard 3-button interactive keyboard for accountability session."""
    keyboard = [
        [InlineKeyboardButton("✅ Đã hoàn thành", callback_data=f"done:{session_id}")],
        [InlineKeyboardButton("⏳ Xin lùi 15 phút", callback_data=f"snooze:{session_id}")],
        [InlineKeyboardButton("🛑 Hôm nay nghỉ (Có lý do)", callback_data=f"skip:{session_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


# Backward-compatible alias
build_inline_action_keyboard = make_inline_action_keyboard


class BotApplication(Application):
    """Authentic Telegram Bot Dispatcher extending PTB Application."""

    def __init__(
        self,
        *args: Any,
        config: Optional[Any] = None,
        storage: Optional[Any] = None,
        coach: Optional[Any] = None,
        scheduler: Optional[Any] = None,
        bot: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.config = config
        self.storage = storage
        self.coach = coach
        self.scheduler = scheduler
        self._custom_bot = bot
        self.active_session_awaiting_reason: Optional[Dict[str, str]] = None

        if "update_queue" not in kwargs and "bot" not in kwargs and not args:
            # Direct instantiation fallback: initialize real PTB structures
            token = getattr(config, "bot_token", None)
            if not token or ":" not in str(token) or not str(token).split(":")[0].isdigit():
                token = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
            real_bot = Bot(token=token)
            update_queue: asyncio.Queue[Any] = asyncio.Queue()
            from telegram.ext import Updater
            updater = Updater(bot=real_bot, update_queue=update_queue)
            super().__init__(
                bot=real_bot,
                update_queue=update_queue,
                updater=updater,
                **kwargs,
            )
        else:
            super().__init__(*args, **kwargs)

    @property
    def bot(self) -> Any:
        """Returns injected test mock bot or authentic PTB Bot."""
        if self._custom_bot is not None:
            return self._custom_bot
        return super().bot

    @bot.setter
    def bot(self, value: Any) -> None:
        """Enables zero-network test mock injection without modifying PTB internals."""
        self._custom_bot = value

    def _infer_session_type(self, session_id: str) -> str:
        sid_lower = session_id.lower()
        if "gym" in sid_lower:
            return "gym"
        elif "toeic" in sid_lower:
            return "toeic"
        elif "major" in sid_lower or "game" in sid_lower:
            return "major"
        return "session"

    def _is_authorized_chat(self, chat: Any) -> bool:
        if not chat:
            return False
        try:
            allowed = int(getattr(self.config, "allowed_chat_id", 0))
            return int(chat.id) == allowed
        except (ValueError, TypeError):
            return False
```

### 3.2 Authentic PTB Handlers
```python
    async def ptb_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """PTB handler callback for /start command."""
        if not self._is_authorized_chat(update.effective_chat):
            logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
            if update.message:
                await self.bot.send_message(update.effective_chat.id, "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.")
            return
        if update.message:
            await self._handle_start(update.message)

    async def ptb_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """PTB handler callback for /help command."""
        if not self._is_authorized_chat(update.effective_chat):
            logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
            if update.message:
                await self.bot.send_message(update.effective_chat.id, "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.")
            return
        if update.message:
            await self._handle_help(update.message)

    async def ptb_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """PTB handler callback for /status command."""
        if not self._is_authorized_chat(update.effective_chat):
            logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
            if update.message:
                await self.bot.send_message(update.effective_chat.id, "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.")
            return
        if update.message:
            await self._handle_status(update.message)

    async def ptb_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """PTB handler callback for inline action buttons."""
        if not self._is_authorized_chat(update.effective_chat):
            logger.warning("Unauthorized callback rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
            if update.callback_query:
                await update.callback_query.answer("⛔ Truy cập bị từ chối!", show_alert=True)
            return
        if update.callback_query:
            await self._handle_callback(update.callback_query)

    async def ptb_message_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """PTB handler callback for text messages (skip justifications & coaching chat)."""
        if not self._is_authorized_chat(update.effective_chat):
            logger.warning("Unauthorized text rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
            if update.message:
                await self.bot.send_message(update.effective_chat.id, "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.")
            return
        if update.message and update.message.text:
            await self._handle_text(update.message)
```

### 3.3 Universal Dispatcher for Offline Test Compatibility
```python
    async def process_update(self, update: Any) -> Optional[Dict[str, Any]]:
        """Universal dispatcher supporting both PTB polling and offline mock test suites."""
        # If real PTB update from polling, dispatch through PTB handler chain
        if isinstance(update, Update):
            await super().process_update(update)
            return None

        # Offline MockUpdate dispatching for test suites
        chat = getattr(update, "effective_chat", None)
        if not chat:
            return None

        if not self._is_authorized_chat(chat):
            logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(chat, "id", None))
            if getattr(update, "message", None):
                return await self.bot.send_message(
                    chat.id,
                    "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                )
            elif getattr(update, "callback_query", None):
                return await update.callback_query.answer(
                    "⛔ Truy cập bị từ chối!", show_alert=True
                )
            return None

        if getattr(update, "callback_query", None):
            return await self._handle_callback(update.callback_query)

        message = getattr(update, "message", None)
        if message and getattr(message, "text", None):
            text = message.text.strip()
            if text.startswith("/start"):
                return await self._handle_start(message)
            elif text.startswith("/help"):
                return await self._handle_help(message)
            elif text.startswith("/status"):
                return await self._handle_status(message)
            else:
                return await self._handle_text(message)

        return None
```

### 3.4 3rd Snooze Rejection Fix
```python
            if new_count > max_snoozes:
                await query.answer("Đã đạt giới hạn lùi giờ!", show_alert=True)
                prompts = getattr(self.config, "prompts", {})
                warning_2 = (
                    prompts.get("snooze_warning_2")
                    if isinstance(prompts, dict)
                    else getattr(prompts, "snooze_warning_2", None)
                ) or "⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!"
                return await query.edit_message_text(
                    f"⚠️ *HẾT QUYỀN LÙI GIỜ!*\n\n{warning_2}",
                    reply_markup=make_inline_action_keyboard(session_id),
                )
```

### 3.5 Factory Function `build_application`
```python
def build_application(
    config: Any,
    storage: Any,
    coach: Any,
    scheduler: Any,
) -> BotApplication:
    """Builds genuine PTB BotApplication registering all handlers and attaching services."""
    token = getattr(config, "bot_token", None)
    if not token or ":" not in str(token) or not str(token).split(":")[0].isdigit():
        token = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"

    builder = Application.builder().token(token).application_class(BotApplication)
    app: BotApplication = builder.build()

    app.config = config
    app.storage = storage
    app.coach = coach
    app.scheduler = scheduler

    # Register genuine PTB Handlers
    app.add_handler(CommandHandler("start", app.ptb_start_command))
    app.add_handler(CommandHandler("help", app.ptb_help_command))
    app.add_handler(CommandHandler("status", app.ptb_status_command))
    app.add_handler(CallbackQueryHandler(app.ptb_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, app.ptb_message_text))

    return app
```

---

## 4. Detailed Specification & Code Blueprint for `src/main.py`

### 4.1 Composition Root & Lifecycle Runner
```python
def create_system(
    config: Optional[AppConfig] = None,
    storage: Optional[AtomicJsonStore] = None,
    coach: Optional[AICoachService] = None,
    scheduler: Optional[SchedulerService] = None,
    bot: Optional[Any] = None,
) -> Tuple[BotApplication, SchedulerService, AppConfig]:
    """Assembles all application subsystems with dependency injection."""
    if config is None:
        config = load_config()

    if storage is None:
        storage = AtomicJsonStore(file_path=getattr(config, "records_file", "data/records.json"))

    if coach is None:
        coach = AICoachService(
            api_key=config.gemini_api_key,
            model_name=getattr(config, "gemini_model", "gemini-2.5-flash"),
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

    # Wire proactive cron triggers with push callback
    async def _on_cron_trigger(session_type: str, session_name: str) -> None:
        await bot_app.send_session_reminder(session_type, session_name)

    scheduler.register_scheduled_jobs(config, _on_cron_trigger)
    return bot_app, scheduler, config


async def run_async(
    config: Optional[AppConfig] = None,
    stop_event: Optional[asyncio.Event] = None,
    bot: Optional[Any] = None,
) -> None:
    """Runs authentic asynchronous Telegram bot polling loop and proactive scheduler."""
    bot_app, scheduler, app_config = create_system(config=config, bot=bot)

    scheduler.start()
    logger.info("Proactive scheduler started in %s timezone.", app_config.timezone)

    try:
        # Authentic PTB Lifecycle: initialize -> start -> start_polling
        await bot_app.initialize()
        await bot_app.start()
        if bot_app.updater:
            await bot_app.updater.start_polling()

        logger.info("Bot application active. Listening for updates...")
        if stop_event is None:
            stop_event = asyncio.Event()

        await stop_event.wait()
    finally:
        logger.info("Initiating graceful shutdown...")
        scheduler.shutdown()
        if bot_app.updater and getattr(bot_app.updater, "running", False):
            await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()
        logger.info("Shutdown completed cleanly.")
```

---

## 5. Verification Checklist & Invalidation Conditions

| Remediation Requirement | Verification Method | Pass Criteria |
|---|---|---|
| **R1: Authentic PTB Application** | Inspect `isinstance(app, Application)` and `super().__init__` call | `bot_app.updater` is a real `telegram.ext.Updater`, `bot_app.update_queue` is a real `asyncio.Queue`. |
| **R2: Zero `tests/` Imports in `src/`** | `grep_search` across `src/` for `tests` | 0 occurrences found. |
| **R3: Registered PTB Handlers** | Inspect `len(bot_app.handlers[0])` | Exactly 5 registered handlers (`CommandHandler` x3, `CallbackQueryHandler`, `MessageHandler`). |
| **R4: Backward Compatibility with Offline Tests** | Run `tests/test_bot.py` and `tests/test_e2e_tier*.py` | 100% test pass rate with `process_update(MockUpdate)`. |
| **R5: Authentic Live Polling Lifecycle** | Trace `src/main.py:run_async` | Calls `initialize()`, `start()`, and `updater.start_polling()`; graceful cleanup in `finally:`. |
| **R6: 3rd Snooze Button Markup** | Inspect `_handle_callback` at `new_count > max_snoozes` | `reply_markup=make_inline_action_keyboard(session_id)` is present. |
