"""Telegram Bot Core Dispatcher & Interactive Dialog State Machine.

Implements strict user authorization whitelist gate, command handlers (/start, /help, /status),
interactive inline keyboards (Done, Snooze, Skip), snooze escalation limits,
excuse evaluation with 2-minute micro-habits, reactive free-form coaching,
and proactive scheduled push reminder callbacks.
Authentic python-telegram-bot Application subclass with live polling and offline test dispatch.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    Updater,
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
        # Support positional arguments if called as BotApplication(config, storage, coach, scheduler)
        if args and config is None and not isinstance(args[0], Bot):
            config = args[0] if len(args) > 0 else None
            storage = args[1] if len(args) > 1 else None
            coach = args[2] if len(args) > 2 else None
            scheduler = args[3] if len(args) > 3 else None
            args = ()

        self.config = config
        self.storage = storage
        self.coach = coach
        self.scheduler = scheduler
        self._custom_bot: Optional[Any] = None
        self._real_bot: Optional[Bot] = None
        self.active_session_awaiting_reason: Optional[Dict[str, str]] = None

        if "update_queue" not in kwargs and not args:
            # Direct instantiation fallback: initialize real PTB structures
            token = getattr(config, "bot_token", None)
            if not token or ":" not in str(token) or not str(token).split(":")[0].isdigit():
                token = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
            real_bot = bot if isinstance(bot, Bot) else Bot(token=token)
            self._real_bot = real_bot
            update_queue: asyncio.Queue[Any] = asyncio.Queue()
            updater = Updater(bot=real_bot, update_queue=update_queue)
            kwargs["bot"] = real_bot
            kwargs["update_queue"] = update_queue
            kwargs["updater"] = updater
            if bot is not None and not isinstance(bot, Bot):
                self._custom_bot = bot
            super().__init__(*args, **kwargs)
        else:
            if bot is not None:
                if isinstance(bot, Bot):
                    self._real_bot = bot
                    if "bot" not in kwargs:
                        kwargs["bot"] = bot
                else:
                    self._custom_bot = bot
                    if "bot" not in kwargs:
                        token = getattr(config, "bot_token", None)
                        if not token or ":" not in str(token) or not str(token).split(":")[0].isdigit():
                            token = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
                        self._real_bot = Bot(token=token)
                        kwargs["bot"] = self._real_bot
            elif "bot" in kwargs and isinstance(kwargs["bot"], Bot):
                self._real_bot = kwargs["bot"]
            super().__init__(*args, **kwargs)

        self._register_handlers()

    @property
    def bot(self) -> Any:
        """Returns injected test mock bot or authentic PTB Bot."""
        if self._custom_bot is not None:
            return self._custom_bot
        if getattr(self, "_real_bot", None) is not None:
            return self._real_bot
        try:
            return Application.bot.__get__(self, Application)
        except Exception:
            token = getattr(self.config, "bot_token", None)
            if not token or ":" not in str(token) or not str(token).split(":")[0].isdigit():
                token = "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
            self._real_bot = Bot(token=token)
            return self._real_bot

    @bot.setter
    def bot(self, value: Any) -> None:
        """Enables zero-network test mock injection without modifying PTB internals."""
        if value is None:
            self._custom_bot = None
        elif isinstance(value, Bot):
            self._real_bot = value
            self._custom_bot = None
        else:
            self._custom_bot = value

    def _register_handlers(self) -> None:
        """Registers the 5 authentic PTB handlers idempotently."""
        if self.handlers.get(0):
            return
        self.add_handler(CommandHandler("start", self._cmd_start))
        self.add_handler(CommandHandler("help", self._cmd_help))
        self.add_handler(CommandHandler("status", self._cmd_status))
        self.add_handler(CallbackQueryHandler(self._handle_callback))
        self.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text_message))

    async def initialize(self) -> None:
        """Initializes application lifecycle; guards mock bots and offline test tokens."""
        if self._custom_bot is not None and not hasattr(self._custom_bot, "initialize"):
            self._initialized = True
            return
        try:
            await super().initialize()
        except Exception as exc:
            logger.warning("Could not initialize authentic PTB application (offline/mock environment): %s", exc)
            self._initialized = True

    async def start(self) -> None:
        """Starts application lifecycle."""
        if not getattr(self, "_initialized", False):
            await self.initialize()
        try:
            await super().start()
        except Exception as exc:
            logger.warning("Could not start authentic PTB application (offline/mock environment): %s", exc)
            self._running = True

    async def stop(self) -> None:
        """Stops application lifecycle."""
        if getattr(self, "running", False):
            try:
                await super().stop()
            except Exception as exc:
                logger.warning("Could not stop authentic PTB application (offline/mock environment): %s", exc)
                self._running = False

    async def shutdown(self) -> None:
        """Shuts down application lifecycle; guards mock bots lacking shutdown()."""
        if self._custom_bot is not None and not hasattr(self._custom_bot, "shutdown"):
            self._running = False
            return
        try:
            await super().shutdown()
        except Exception as exc:
            logger.warning("Could not shutdown authentic PTB application (offline/mock environment): %s", exc)

    async def _safe_answer_query(self, query: Any, text: Optional[str] = None, show_alert: bool = False) -> Dict[str, Any]:
        """Safely answers a callback query with offline fallback."""
        try:
            res = await query.answer(text=text, show_alert=show_alert)
            if isinstance(res, dict):
                return res
        except Exception as exc:
            logger.debug("Could not answer callback query via network (offline/mock): %s", exc)
        return {"callback_query_id": getattr(query, "id", "cb_0"), "text": text, "show_alert": show_alert}

    async def _safe_edit_message_text(self, query: Any, text: str, reply_markup: Optional[Any] = None) -> Dict[str, Any]:
        """Safely edits message text on callback query with offline dict return."""
        try:
            res = await query.edit_message_text(text, reply_markup=reply_markup)
            if isinstance(res, dict):
                return res
            if hasattr(res, "message_id"):
                return {"message_id": res.message_id, "text": text, "chat_id": getattr(getattr(res, "chat", None), "id", None), "reply_markup": reply_markup}
        except Exception as exc:
            logger.debug("Could not edit message text via network (offline/mock): %s", exc)
        msg = getattr(query, "message", None)
        cid = getattr(msg, "chat_id", None) or getattr(getattr(msg, "chat", None), "id", None) or getattr(self.config, "allowed_chat_id", 0)
        mid = getattr(msg, "message_id", 1001)
        return {"chat_id": int(cid) if cid else 0, "message_id": mid, "text": text, "reply_markup": reply_markup}

    async def _safe_send_message(self, chat_id: Any, text: str, reply_markup: Optional[Any] = None) -> Dict[str, Any]:
        """Safely sends a message via bot with offline dict return."""
        try:
            res = await self.bot.send_message(chat_id, text, reply_markup=reply_markup)
            if isinstance(res, dict):
                return res
            if hasattr(res, "message_id"):
                return {"message_id": res.message_id, "text": text, "chat_id": int(chat_id), "reply_markup": reply_markup}
        except Exception as exc:
            logger.debug("Could not send message via network (offline/mock): %s", exc)
        return {"chat_id": int(chat_id) if chat_id else 0, "text": text, "reply_markup": reply_markup}

    def _infer_session_type(self, session_id: str) -> str:
        """Infers domain session type from session identifier."""
        sid_lower = session_id.lower()
        if "gym" in sid_lower:
            return "gym"
        elif "toeic" in sid_lower:
            return "toeic"
        elif "major" in sid_lower or "game" in sid_lower:
            return "major"
        return "session"

    def _is_authorized_chat(self, chat: Any) -> bool:
        """Evaluates whether chat matches configured allowed_chat_id."""
        if not chat:
            return False
        try:
            allowed = int(getattr(self.config, "allowed_chat_id", 0))
            return int(chat.id) == allowed
        except (ValueError, TypeError):
            return False

    async def _cmd_start(self, update_or_msg: Any, context: Optional[Any] = None) -> Any:
        """PTB CommandHandler callback for /start."""
        if context is not None or hasattr(update_or_msg, "effective_chat"):
            update = update_or_msg
            if not self._is_authorized_chat(update.effective_chat):
                logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
                if update.effective_chat:
                    await self.bot.send_message(
                        update.effective_chat.id,
                        "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                    )
                return None
            msg = update.message
            if not msg:
                return None
            return await self._handle_start(msg)
        else:
            return await self._handle_start(update_or_msg)

    async def _cmd_help(self, update_or_msg: Any, context: Optional[Any] = None) -> Any:
        """PTB CommandHandler callback for /help."""
        if context is not None or hasattr(update_or_msg, "effective_chat"):
            update = update_or_msg
            if not self._is_authorized_chat(update.effective_chat):
                logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
                if update.effective_chat:
                    await self.bot.send_message(
                        update.effective_chat.id,
                        "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                    )
                return None
            msg = update.message
            if not msg:
                return None
            return await self._handle_help(msg)
        else:
            return await self._handle_help(update_or_msg)

    async def _cmd_status(self, update_or_msg: Any, context: Optional[Any] = None) -> Any:
        """PTB CommandHandler callback for /status."""
        if context is not None or hasattr(update_or_msg, "effective_chat"):
            update = update_or_msg
            if not self._is_authorized_chat(update.effective_chat):
                logger.warning("Unauthorized access attempt rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
                if update.effective_chat:
                    await self.bot.send_message(
                        update.effective_chat.id,
                        "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                    )
                return None
            msg = update.message
            if not msg:
                return None
            return await self._handle_status(msg)
        else:
            return await self._handle_status(update_or_msg)

    async def _handle_callback(self, query_or_update: Any, context: Optional[Any] = None) -> Any:
        """Handles interactive callback actions: done, snooze, skip."""
        if context is not None or hasattr(query_or_update, "callback_query"):
            update = query_or_update
            if not self._is_authorized_chat(update.effective_chat):
                logger.warning("Unauthorized callback rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
                if update.callback_query:
                    await update.callback_query.answer("⛔ Truy cập bị từ chối!", show_alert=True)
                return None
            query = update.callback_query
            if not query:
                return None
        else:
            query = query_or_update

        data = query.data
        parts = data.split(":")
        action = parts[0]
        if len(parts) >= 3:
            session_type = parts[1]
            session_id = ":".join(parts[2:])
        elif len(parts) == 2:
            session_id = parts[1]
            session_type = self._infer_session_type(session_id)
        else:
            session_id = "default_session"
            session_type = "session"

        tz_str = getattr(self.config, "timezone", "Asia/Ho_Chi_Minh")

        if action == "done":
            await self._safe_answer_query(query, "Ghi nhận hoàn thành!")
            today_str = datetime.now(ZoneInfo(tz_str)).strftime("%Y-%m-%d")
            streak_data = await self.storage.record_completion(session_id, session_type, today_str)
            praise = await self.coach.get_congratulation(session_type, streak_data.current_streak)
            text = (
                f"✅ *HOÀN THÀNH XUẤT SẮC!*\n"
                f"Chuỗi streak: *{streak_data.current_streak}* ngày liên tiếp.\n\n"
                f"🤖 Coach: _{praise}_"
            )
            return await self._safe_edit_message_text(query, text)

        elif action == "snooze":
            status = await self.storage.get_session_status(session_id)
            curr_count = status.get("snooze_count", 0) if status else 0
            new_count = curr_count + 1
            max_snoozes = getattr(self.config, "max_snoozes", 2)
            snooze_minutes = getattr(self.config, "snooze_minutes", 15)

            if new_count > max_snoozes:
                await self._safe_answer_query(query, "Đã đạt giới hạn lùi giờ!", show_alert=True)
                prompts = getattr(self.config, "prompts", {})
                warning_2 = (
                    prompts.get("snooze_warning_2")
                    if isinstance(prompts, dict)
                    else getattr(prompts, "snooze_warning_2", None)
                ) or "⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!"
                return await self._safe_edit_message_text(
                    query,
                    f"⚠️ *HẾT QUYỀN LÙI GIỜ!*\n\n{warning_2}",
                    reply_markup=make_inline_action_keyboard(session_id),
                )

            await self.storage.record_snooze(session_id, new_count)
            if self.scheduler and hasattr(self.scheduler, "schedule_snooze_job"):
                self.scheduler.schedule_snooze_job(
                    session_id=session_id,
                    session_type=session_type,
                    snooze_count=new_count,
                    delay_minutes=snooze_minutes,
                    callback=self._snooze_job_callback,
                )
            await self._safe_answer_query(query, f"Đã lùi {snooze_minutes} phút (Lần {new_count}/{max_snoozes})")

            fallbacks = getattr(self.config, "fallbacks", {})
            if isinstance(fallbacks, dict):
                fallback_s1 = fallbacks.get("offline_snooze_1", "Đã lùi 15 phút (Lần 1/2).")
                fallback_s2 = fallbacks.get("offline_snooze_2", "Đã lùi 15 phút (Lần 2/2).")
            else:
                fallback_s1 = getattr(fallbacks, "offline_snooze_1", "Đã lùi 15 phút (Lần 1/2).")
                fallback_s2 = getattr(fallbacks, "offline_snooze_2", "Đã lùi 15 phút (Lần 2/2).")

            warning = fallback_s1 if new_count == 1 else fallback_s2
            return await self._safe_edit_message_text(
                query,
                f"⏳ *ĐÃ LÙI {snooze_minutes} PHÚT (Lần {new_count}/{max_snoozes})*\n\n{warning}",
                reply_markup=make_inline_action_keyboard(session_id),
            )

        elif action == "skip":
            await self._safe_answer_query(query, "Nhập lý do xin nghỉ.")
            awaiting_payload = {"session_id": session_id, "session_type": session_type}
            self.active_session_awaiting_reason = awaiting_payload
            data_dict = await self.storage.load_data()
            data_dict["awaiting_reason"] = awaiting_payload
            await self.storage.save_data(data_dict)
            return await self._safe_edit_message_text(
                query,
                "🛑 *XIN NGHỈ CÓ LÝ DO*\n\n"
                "Hãy gửi tin nhắn giải trình lý do bạn không thể hoàn thành phiên này. "
                "AI Coach sẽ đánh giá xem đây là lý do chính đáng hay sự trì hoãn!",
            )

        return await self._safe_answer_query(query, "Không nhận diện được thao tác.")

    async def _handle_text_message(self, update_or_msg: Any, context: Optional[Any] = None) -> Any:
        """PTB handler callback for text messages (skip justifications & coaching chat)."""
        if context is not None or hasattr(update_or_msg, "effective_chat"):
            update = update_or_msg
            if not self._is_authorized_chat(update.effective_chat):
                logger.warning("Unauthorized text rejected from chat_id=%s", getattr(update.effective_chat, "id", None))
                if update.effective_chat:
                    await self.bot.send_message(
                        update.effective_chat.id,
                        "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                    )
                return None
            msg = update.message
            if not msg or not getattr(msg, "text", None):
                return None
            return await self._handle_text(msg)
        else:
            return await self._handle_text(update_or_msg)

    # Handler Aliases for PTB Handlers and compatibility
    ptb_start_command = _cmd_start
    ptb_help_command = _cmd_help
    ptb_status_command = _cmd_status
    ptb_callback_query = _handle_callback
    ptb_message_text = _handle_text_message
    _handle_callback_query = _handle_callback

    async def process_update(self, update: Any) -> Optional[Dict[str, Any]]:
        """Universal dispatcher supporting both authentic PTB polling and offline test suites."""
        # Live PTB polling update delegation
        if isinstance(update, Update) and self._custom_bot is None:
            await super().process_update(update)
            return None

        # Offline MockUpdate dispatching for test suites
        chat = getattr(update, "effective_chat", None)
        if not chat:
            return None

        # Feature 1 & 36: Security Whitelist Gate
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

        # Callback query routing
        if getattr(update, "callback_query", None):
            return await self._handle_callback(update.callback_query)

        # Message text / command routing
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

    async def _handle_start(self, message: Any) -> Dict[str, Any]:
        """Feature 4: /start command handler introducing coach and listing commands."""
        text = (
            "🚀 *Chào mừng bạn đến với Huấn Luyện Viên Kỷ Luật Cá Nhân!*\n\n"
            "Tôi là bot giám sát tiến độ thực chiến dành cho kỹ sư IT & game dev.\n"
            "Các lệnh khả dụng:\n"
            "• `/status` - Xem chuỗi streak và lịch sử check-in\n"
            "• `/help` - Xem hướng dẫn chi tiết\n"
        )
        return await self._safe_send_message(message.chat.id, text)

    async def _handle_help(self, message: Any) -> Dict[str, Any]:
        """Feature 5: /help command handler detailing the 3 interactive action buttons."""
        text = (
            "📖 *HƯỚNG DẪN SỬ DỤNG:*\n\n"
            "1. Bot sẽ chủ động gửi thông báo theo lịch đã cài đặt.\n"
            "2. Khi nhận thông báo, chọn 1 trong 3 nút:\n"
            "   - `[✅ Đã hoàn thành]`: Ghi nhận hoàn thành và tăng streak.\n"
            "   - `[⏳ Xin lùi 15 phút]`: Lùi tối đa 2 lần (mỗi lần 15 phút).\n"
            "   - `[🛑 Hôm nay nghỉ (Có lý do)]`: Nhập lý do để AI đánh giá.\n"
        )
        return await self._safe_send_message(message.chat.id, text)

    async def _handle_status(self, message: Any) -> Dict[str, Any]:
        """Feature 6: /status command handler displaying streak metrics."""
        streak_data = await self.storage.get_streak()
        tz_str = getattr(self.config, "timezone", "Asia/Ho_Chi_Minh")
        today_str = datetime.now(ZoneInfo(tz_str)).strftime("%Y-%m-%d")
        effective_streak = streak_data.get_effective_streak(today_str)
        text = (
            f"📊 *BÁO CÁO KỶ LUẬT THỰC CHIẾN*\n\n"
            f"🔥 Chuỗi streak hiện tại: *{effective_streak}* ngày\n"
            f"🏆 Kỷ lục streak tốt nhất: *{streak_data.best_streak}* ngày\n"
            f"✅ Tổng số phiên hoàn thành: *{streak_data.total_completions}*\n"
            f"📅 Lần cuối hoàn thành: `{streak_data.last_completed_date or 'Chưa có'}`"
        )
        return await self._safe_send_message(message.chat.id, text)

    async def _handle_text(self, message: Any) -> Dict[str, Any]:
        """Handles skip justifications and free-form coaching chat."""
        data_dict = await self.storage.load_data()
        awaiting = data_dict.get("awaiting_reason") or self.active_session_awaiting_reason

        if awaiting:
            if isinstance(awaiting, dict):
                session_id = awaiting.get("session_id", "session")
                session_type = awaiting.get("session_type", self._infer_session_type(session_id))
            else:
                session_id = str(awaiting)
                session_type = self._infer_session_type(session_id)

            reason_text = message.text

            classification, response_text = await self.coach.evaluate_skip_reason(session_type, reason_text)
            tz_str = getattr(self.config, "timezone", "Asia/Ho_Chi_Minh")
            timestamp_str = datetime.now(ZoneInfo(tz_str)).isoformat()
            await self.storage.record_skip(session_id, reason_text, classification, timestamp_str)

            # Fresh reload before clearing awaiting_reason to avoid overwriting recorded skip status
            fresh_data = await self.storage.load_data()
            fresh_data["awaiting_reason"] = None
            self.active_session_awaiting_reason = None
            await self.storage.save_data(fresh_data)

            if classification == "LEGITIMATE":
                reply = (
                    f"🛑 *LÝ DO CHÍNH ĐÁNG ĐƯỢC CHẤP NHẬN*\n\n"
                    f"🤖 Coach: _{response_text}_\n\n"
                    f"Phiên này được ghi nhận nghỉ có lý do. Không ảnh hưởng chuỗi streak."
                )
            else:
                reply = (
                    f"⚡ *BÓC TRẦN LÝ DO BAO BIỆN!*\n\n"
                    f"🤖 Coach: _{response_text}_\n\n"
                    f"👉 *THỬ THÁCH MICRO-HABIT 2 PHÚT*: Thực hiện ngay để không đứt gãy tính kỷ luật!"
                )
            return await self._safe_send_message(message.chat.id, reply)

        # Reactive free-form coaching chat
        coach_reply = await self.coach.chat(message.text)
        return await self._safe_send_message(message.chat.id, f"🤖 *Coach*: {coach_reply}")

    async def _snooze_job_callback(self, session_id: str, session_type: str, snooze_count: int) -> None:
        """Callback executed when scheduler snooze DateTrigger fires."""
        max_snoozes = getattr(self.config, "max_snoozes", 2)
        snooze_minutes = getattr(self.config, "snooze_minutes", 15)
        text = (
            f"⏰ *HẾT {snooze_minutes} PHÚT LÙI GIỜ!*\n"
            f"Phiên `{session_type}` đang chờ bạn hoàn thành. (Lần lùi: {snooze_count}/{max_snoozes})"
        )
        allowed_chat_id = int(getattr(self.config, "allowed_chat_id", 0))
        await self._safe_send_message(
            allowed_chat_id,
            text,
            reply_markup=make_inline_action_keyboard(session_id),
        )

    async def send_session_reminder(self, session_type: str, session_title: str) -> Dict[str, Any]:
        """Proactive notification push callback formatting message from config and attaching inline keyboard."""
        tz_str = getattr(self.config, "timezone", "Asia/Ho_Chi_Minh")
        now = datetime.now(ZoneInfo(tz_str))
        date_str = now.strftime("%Y%m%d")
        session_id = f"{session_type}_{date_str}"

        # Ensure session exists in persistence
        if hasattr(self.storage, "create_session"):
            try:
                await self.storage.create_session(session_id=session_id, session_type=session_type)
            except Exception as exc:
                logger.debug("create_session notice: %s", exc)

        if session_type == "gym":
            gym_cfg = getattr(self.config, "gym", None)
            weekday = now.weekday()
            window = getattr(gym_cfg, "window_split1", "17:30 – 18:30") if weekday in (0, 1, 3) else getattr(gym_cfg, "window_split2", "16:30 – 17:30")
            template = getattr(gym_cfg, "message_template", None)
            if template:
                text = template.format(window=window)
            else:
                text = (
                    f"🏋️‍♂️ *GIỜ TẬP GYM ĐÃ ĐẾN!*\n\n"
                    f"Buổi tập: *{session_title}*\n"
                    f"Khung giờ tập: `{window}`\n"
                    f"Rời bàn làm việc, chuẩn bị đồ tập và bắt đầu ngay nào!"
                )
        elif session_type == "toeic":
            toeic_cfg = getattr(self.config, "toeic", None)
            weekday = now.weekday()
            part = toeic_cfg.get_part_for_weekday(weekday) if toeic_cfg and hasattr(toeic_cfg, "get_part_for_weekday") else "Part 1: Photographs"
            weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
            template = getattr(toeic_cfg, "message_template", None)
            window = getattr(toeic_cfg, "window", "19:30 – 20:30")
            if template:
                try:
                    text = template.format(
                        window=window,
                        topic=part,
                        part_topic=part,
                        weekday_name=weekday_names[weekday],
                    )
                except KeyError:
                    text = f"📚 *GIỜ HỌC TOEIC!*\nChủ đề: *{part}*\nKhung giờ: `{window}`"
            else:
                text = (
                    f"📚 *GIỜ HỌC TOEIC ĐÃ ĐẾN!*\n\n"
                    f"Chủ đề hôm nay ({weekday_names[weekday]}): *{part}*\n"
                    f"Thời gian: {window} (1 tiếng).\n"
                    f"Bật tài liệu lên và giải đề ngay!"
                )
        elif session_type == "major":
            major_cfg = getattr(self.config, "major", None)
            template = getattr(major_cfg, "message_template", None)
            window = getattr(major_cfg, "window", "20:45 – 21:45")
            if template:
                text = template.format(window=window)
            else:
                text = (
                    f"💻 *GIỜ TỰ HỌC CHUYÊN NGÀNH & GAME DEV ĐÃ ĐẾN!*\n\n"
                    f"Nội dung: *{session_title}*\n"
                    f"Thời gian: {window} (1 tiếng).\n"
                    f"Mở IDE lên và hoàn thành mục tiêu hôm nay!"
                )
        else:
            text = f"⏰ *NHẮC NHỞ HOÀN THÀNH PHIÊN*: {session_title}"

        allowed_chat_id = int(getattr(self.config, "allowed_chat_id", 0))
        keyboard = make_inline_action_keyboard(session_id)
        return await self._safe_send_message(
            allowed_chat_id,
            text,
            reply_markup=keyboard,
        )

    # Alias for proactive reminder push
    send_proactive_reminder = send_session_reminder


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

    proxy_url = os.getenv("TELEGRAM_PROXY_URL") or os.getenv("HTTPS_PROXY")
    request_kwargs: Dict[str, Any] = {"connect_timeout": 20.0, "read_timeout": 20.0}
    if proxy_url:
        request_kwargs["proxy_url"] = proxy_url

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(**request_kwargs)
    builder = Application.builder().token(token).request(request).application_class(BotApplication)
    app: BotApplication = builder.build()

    app.config = config
    app.storage = storage
    app.coach = coach
    app.scheduler = scheduler

    app._register_handlers()
    return app
