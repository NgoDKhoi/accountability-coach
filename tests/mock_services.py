"""Offline Test Doubles and Interface Contract Implementations.

Provides mock clients, simulated Telegram bots, Gemini AI service doubles,
and APScheduler simulation adhering to PROJECT.md interface contracts.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.config import AppConfig
from src.storage import AtomicJsonStore, StreakData, SessionStatus


# =====================================================================
# 1. Mock Telegram Bot & Update Factory
# =====================================================================

class MockTelegramBot:
    """Zero-network mock Telegram Bot capturing all outbound operations."""

    def __init__(self, token: str = "mock-token:123456"):
        self.token = token
        self.sent_messages: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []
        self.answered_callbacks: List[Dict[str, Any]] = []
        self.deleted_messages: List[Dict[str, Any]] = []
        self._next_message_id = 1000

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: Optional[Any] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        self._next_message_id += 1
        record = {
            "message_id": self._next_message_id,
            "chat_id": int(chat_id),
            "text": text,
            "reply_markup": reply_markup,
            "parse_mode": parse_mode,
            "kwargs": kwargs,
        }
        self.sent_messages.append(record)
        return record

    async def edit_message_text(
        self,
        text: str,
        chat_id: Optional[int | str] = None,
        message_id: Optional[int] = None,
        reply_markup: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        record = {
            "message_id": message_id,
            "chat_id": int(chat_id) if chat_id is not None else None,
            "text": text,
            "reply_markup": reply_markup,
            "kwargs": kwargs,
        }
        self.edited_messages.append(record)
        return record

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        record = {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
            "kwargs": kwargs,
        }
        self.answered_callbacks.append(record)
        return record

    async def delete_message(
        self,
        chat_id: int | str,
        message_id: int,
        **kwargs: Any,
    ) -> bool:
        self.deleted_messages.append({"chat_id": int(chat_id), "message_id": message_id})
        return True


class MockChat:
    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type


class MockUser:
    def __init__(self, user_id: int, username: str = "testuser", first_name: str = "Test"):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.is_bot = False


class MockMessage:
    def __init__(
        self,
        message_id: int,
        chat: MockChat,
        from_user: MockUser,
        text: str,
        bot: Optional[MockTelegramBot] = None,
        reply_markup: Optional[Any] = None,
    ):
        self.message_id = message_id
        self.chat = chat
        self.chat_id = chat.id
        self.from_user = from_user
        self.text = text
        self.bot = bot
        self.reply_markup = reply_markup
        self.date = datetime.now(timezone.utc)

    async def reply_text(self, text: str, reply_markup: Optional[Any] = None, **kwargs: Any) -> Dict[str, Any]:
        if self.bot:
            return await self.bot.send_message(self.chat.id, text, reply_markup=reply_markup, **kwargs)
        return {"chat_id": self.chat.id, "text": text, "reply_markup": reply_markup}

    async def edit_text(self, text: str, reply_markup: Optional[Any] = None, **kwargs: Any) -> Dict[str, Any]:
        if self.bot:
            return await self.bot.edit_message_text(text, chat_id=self.chat.id, message_id=self.message_id, reply_markup=reply_markup, **kwargs)
        return {"chat_id": self.chat.id, "message_id": self.message_id, "text": text, "reply_markup": reply_markup}


class MockCallbackQuery:
    def __init__(
        self,
        query_id: str,
        from_user: MockUser,
        message: MockMessage,
        data: str,
        bot: Optional[MockTelegramBot] = None,
    ):
        self.id = query_id
        self.from_user = from_user
        self.message = message
        self.data = data
        self.bot = bot

    async def answer(self, text: Optional[str] = None, show_alert: bool = False, **kwargs: Any) -> Dict[str, Any]:
        if self.bot:
            return await self.bot.answer_callback_query(self.id, text=text, show_alert=show_alert, **kwargs)
        return {"callback_query_id": self.id, "text": text, "show_alert": show_alert}

    async def edit_message_text(self, text: str, reply_markup: Optional[Any] = None, **kwargs: Any) -> Dict[str, Any]:
        if self.bot:
            return await self.bot.edit_message_text(text, chat_id=self.message.chat.id, message_id=self.message.message_id, reply_markup=reply_markup, **kwargs)
        return {"chat_id": self.message.chat.id, "message_id": self.message.message_id, "text": text, "reply_markup": reply_markup}


class MockUpdate:
    def __init__(
        self,
        update_id: int,
        message: Optional[MockMessage] = None,
        callback_query: Optional[MockCallbackQuery] = None,
    ):
        self.update_id = update_id
        self.message = message
        self.callback_query = callback_query

    @property
    def effective_chat(self) -> Optional[MockChat]:
        if self.message:
            return self.message.chat
        if self.callback_query and self.callback_query.message:
            return self.callback_query.message.chat
        return None

    @property
    def effective_user(self) -> Optional[MockUser]:
        if self.message:
            return self.message.from_user
        if self.callback_query:
            return self.callback_query.from_user
        return None


def make_text_update(
    chat_id: int,
    text: str,
    user_id: Optional[int] = None,
    update_id: int = 1,
    bot: Optional[MockTelegramBot] = None,
) -> MockUpdate:
    uid = user_id if user_id is not None else chat_id
    chat = MockChat(chat_id)
    user = MockUser(uid)
    msg = MockMessage(message_id=update_id * 10, chat=chat, from_user=user, text=text, bot=bot)
    return MockUpdate(update_id=update_id, message=msg)


def make_callback_update(
    chat_id: int,
    callback_data: str,
    original_text: str = "Scheduled Reminder",
    user_id: Optional[int] = None,
    update_id: int = 2,
    bot: Optional[MockTelegramBot] = None,
) -> MockUpdate:
    uid = user_id if user_id is not None else chat_id
    chat = MockChat(chat_id)
    user = MockUser(uid)
    msg = MockMessage(message_id=update_id * 10, chat=chat, from_user=user, text=original_text, bot=bot)
    cb = MockCallbackQuery(query_id=f"cb_{update_id}", from_user=user, message=msg, data=callback_data, bot=bot)
    return MockUpdate(update_id=update_id, callback_query=cb)


def make_inline_action_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Builds standard 3-button keyboard for session."""
    keyboard = [
        [InlineKeyboardButton("✅ Đã hoàn thành", callback_data=f"done:{session_id}")],
        [InlineKeyboardButton("⏳ Xin lùi 15 phút", callback_data=f"snooze:{session_id}")],
        [InlineKeyboardButton("🛑 Hôm nay nghỉ (Có lý do)", callback_data=f"skip:{session_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


# =====================================================================
# 2. Mock Gemini AI Client
# =====================================================================

class MockGenerateContentResponse:
    def __init__(self, text: str):
        self.text = text


class MockGeminiModels:
    def __init__(self, error_mode: Optional[str] = None):
        self.error_mode = error_mode
        self.call_history: List[Dict[str, Any]] = []

    async def generate_content(
        self,
        model: str,
        contents: Any,
        config: Optional[Any] = None,
    ) -> MockGenerateContentResponse:
        self.call_history.append({"model": model, "contents": contents, "config": config})

        if self.error_mode == "timeout":
            raise asyncio.TimeoutError("Gemini API call timed out")
        elif self.error_mode == "api_error":
            raise RuntimeError("503 Service Unavailable: Gemini overloaded")
        elif self.error_mode == "empty":
            return MockGenerateContentResponse("")

        prompt_str = str(contents)
        if "hoàn thành" in prompt_str.lower() or "streak" in prompt_str.lower() or "khen ngợi" in prompt_str.lower():
            return MockGenerateContentResponse(
                "Đúng chất kỹ sư game: kỷ luật tạo ra kết quả! Giữ vững streak và duy trì phong độ này."
            )
        elif "lý do" in prompt_str.lower() or "skip" in prompt_str.lower() or "nghỉ" in prompt_str.lower():
            if any(w in prompt_str.lower() for w in ["sốt", "cấp cứu", "bệnh", "tai nạn", "bệnh viện"]):
                return MockGenerateContentResponse(
                    "[LEGITIMATE] Lý do sức khỏe bất khả kháng được duyệt. Nghỉ ngơi trọn vẹn và ngày mai tiếp tục."
                )
            else:
                return MockGenerateContentResponse(
                    "[EXCUSE] Lý do trì hoãn điển hình của lập trình viên! Thực hiện ngay micro-habit 2 phút: đọc 1 trang tài liệu hoặc chống đẩy 5 cái trước khi tắt máy."
                )
        else:
            return MockGenerateContentResponse(
                "Kỷ luật là cầu nối giữa ý tưởng và sản phẩm hoàn thiện. Tập trung xử lý bug tiếp theo đi!"
            )


class MockGeminiAsyncClient:
    def __init__(self, error_mode: Optional[str] = None):
        self.models = MockGeminiModels(error_mode=error_mode)


class MockGeminiClient:
    def __init__(self, api_key: str = "fake-key", error_mode: Optional[str] = None):
        self.api_key = api_key
        self.aio = MockGeminiAsyncClient(error_mode=error_mode)


# =====================================================================
# 3. Contract Service Implementations (AICoachService, SchedulerService, BotApp)
# =====================================================================

class DefaultAICoachService:
    """Offline AICoachService implementing PROJECT.md contract."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        config: Optional[dict] = None,
        client: Optional[Any] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.config = config or {}
        self.client = client or MockGeminiClient(api_key=api_key)
        self.context_window: deque[Tuple[str, str]] = deque(maxlen=10)
        self.fallbacks = self.config.get("fallbacks", {})
        self.prompts = self.config.get("prompts", {})

    async def get_congratulation(self, session_type: str, streak: int) -> str:
        try:
            prompt = self.prompts.get(
                "completion_praise",
                f"Người dùng vừa hoàn thành phiên {session_type}. Streak: {streak}.",
            ).format(session_name=session_type, detail=session_type, streak=streak)
            resp = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            if resp and resp.text.strip():
                return resp.text.strip()
            return self.fallbacks.get("offline_praise", "✅ Đã ghi nhận hoàn thành! Tiếp tục giữ chuỗi.")
        except Exception:
            return self.fallbacks.get("offline_praise", "✅ Đã ghi nhận hoàn thành! Tiếp tục giữ chuỗi.")

    async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]:
        try:
            template = self.prompts.get("skip_evaluator", "")
            if "{reason}" in template:
                prompt = template.format(session_name=session_type, detail=session_type, reason=reason)
            else:
                prompt = f"{template}\nPhiên: {session_type}. Lý do: {reason}"
            resp = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            raw = resp.text.strip() if resp and resp.text else ""
            if "[LEGITIMATE]" in raw:
                clean_text = raw.replace("[LEGITIMATE]", "").strip()
                return "LEGITIMATE", clean_text or self.fallbacks.get("offline_skip_legitimate", "Đã duyệt nghỉ có lý do.")
            elif "[EXCUSE]" in raw:
                clean_text = raw.replace("[EXCUSE]", "").strip()
                return "EXCUSE", clean_text or self.fallbacks.get("offline_skip_excuse", "Lý do chưa thuyết phục!")
            else:
                if any(w in reason.lower() for w in ["sốt", "cấp cứu", "bệnh", "tai nạn", "bệnh viện"]):
                    return "LEGITIMATE", self.fallbacks.get("offline_skip_legitimate", "Đã duyệt nghỉ có lý do chính đáng.")
                return "EXCUSE", self.fallbacks.get("offline_skip_excuse", "Lý do chưa thuyết phục! Hãy làm micro-habit 2 phút.")
        except Exception:
            if any(w in reason.lower() for w in ["sốt", "cấp cứu", "bệnh", "tai nạn", "bệnh viện"]):
                return "LEGITIMATE", self.fallbacks.get("offline_skip_legitimate", "Đã duyệt nghỉ có lý do chính đáng.")
            return "EXCUSE", self.fallbacks.get("offline_skip_excuse", "Lý do chưa thuyết phục! Hãy làm micro-habit 2 phút.")

    async def chat(self, user_message: str) -> str:
        self.context_window.append(("user", user_message))
        try:
            history_prompt = "\n".join(f"{role}: {msg}" for role, msg in self.context_window)
            resp = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=history_prompt,
            )
            if resp and resp.text.strip():
                reply = resp.text.strip()
                self.context_window.append(("coach", reply))
                return reply
            fallback = self.fallbacks.get("offline_coach", "AI tạm thời gián đoạn, kỷ luật của bạn thì không!")
            self.context_window.append(("coach", fallback))
            return fallback
        except Exception:
            fallback = self.fallbacks.get("offline_coach", "AI tạm thời gián đoạn, kỷ luật của bạn thì không!")
            self.context_window.append(("coach", fallback))
            return fallback

    def clear_context(self) -> None:
        self.context_window.clear()


class DefaultSchedulerService:
    """Offline SchedulerService simulation implementing PROJECT.md contract."""

    def __init__(self, timezone_str: str = "Asia/Ho_Chi_Minh"):
        self.timezone_str = timezone_str
        self.timezone = ZoneInfo(timezone_str)
        self.registered_jobs: Dict[str, Dict[str, Any]] = {}
        self.snooze_jobs: Dict[str, Dict[str, Any]] = {}
        self.is_running = False

    def register_scheduled_jobs(
        self,
        config: Any,
        trigger_callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        self.registered_jobs["gym_split1"] = {
            "type": "gym",
            "name": config.gym.name,
            "days": config.gym.cron_days_split1,
            "time": config.gym.time_split1,
            "callback": trigger_callback,
        }
        self.registered_jobs["gym_split2"] = {
            "type": "gym",
            "name": config.gym.name,
            "days": config.gym.cron_days_split2,
            "time": config.gym.time_split2,
            "callback": trigger_callback,
        }
        self.registered_jobs["toeic"] = {
            "type": "toeic",
            "name": config.toeic.name,
            "days": "daily",
            "time": config.toeic.time,
            "callback": trigger_callback,
        }
        self.registered_jobs["major"] = {
            "type": "major",
            "name": config.major.name,
            "days": "daily",
            "time": config.major.time,
            "callback": trigger_callback,
        }

    def schedule_snooze_job(
        self,
        session_id: str,
        session_type: str,
        snooze_count: int,
        delay_minutes: int,
        callback: Callable[[str, str, int], Coroutine[Any, Any, None]],
    ) -> str:
        job_id = f"snooze_{session_id}_{snooze_count}"
        run_at = datetime.now(self.timezone) + timedelta(minutes=delay_minutes)
        self.snooze_jobs[job_id] = {
            "session_id": session_id,
            "session_type": session_type,
            "snooze_count": snooze_count,
            "delay_minutes": delay_minutes,
            "run_at": run_at,
            "callback": callback,
        }
        return job_id

    def cancel_job(self, job_id: str) -> bool:
        if job_id in self.snooze_jobs:
            del self.snooze_jobs[job_id]
            return True
        if job_id in self.registered_jobs:
            del self.registered_jobs[job_id]
            return True
        return False

    async def trigger_job(self, job_id: str) -> None:
        if job_id in self.snooze_jobs:
            job = self.snooze_jobs[job_id]
            await job["callback"](job["session_id"], job["session_type"], job["snooze_count"])
            del self.snooze_jobs[job_id]
        elif job_id in self.registered_jobs:
            job = self.registered_jobs[job_id]
            await job["callback"](job["type"], job["name"])

    def start(self) -> None:
        self.is_running = True

    def shutdown(self) -> None:
        self.is_running = False
        self.snooze_jobs.clear()


class DefaultBotApplication:
    """Full-fidelity Telegram Bot Dispatcher simulating PTB Application."""

    def __init__(
        self,
        config: AppConfig,
        storage: AtomicJsonStore,
        coach: Any,
        scheduler: Any,
        bot: Optional[MockTelegramBot] = None,
    ):
        self.config = config
        self.storage = storage
        self.coach = coach
        self.scheduler = scheduler
        self.bot = bot or MockTelegramBot(token=config.bot_token)
        self.active_session_awaiting_reason: Optional[Dict[str, str]] = None

    async def process_update(self, update: MockUpdate) -> Optional[Dict[str, Any]]:
        """Processes incoming Update adhering to whitelist security & workflow."""
        chat = update.effective_chat
        user = update.effective_user
        if not chat:
            return None

        # Feature 1: Whitelist Security Gate
        if chat.id != self.config.allowed_chat_id:
            if update.message:
                return await self.bot.send_message(
                    chat.id,
                    "⛔ Truy cập bị từ chối! Bot chỉ phục vụ người dùng được ủy quyền.",
                )
            elif update.callback_query:
                return await update.callback_query.answer(
                    "⛔ Truy cập bị từ chối!", show_alert=True
                )
            return None

        # Callback queries handling
        if update.callback_query:
            return await self._handle_callback(update.callback_query)

        # Message command / text handling
        if update.message and update.message.text:
            text = update.message.text.strip()
            if text.startswith("/start"):
                return await self._handle_start(update.message)
            elif text.startswith("/help"):
                return await self._handle_help(update.message)
            elif text.startswith("/status"):
                return await self._handle_status(update.message)
            else:
                return await self._handle_text(update.message)

        return None

    async def _handle_start(self, message: MockMessage) -> Dict[str, Any]:
        text = (
            "🚀 *Chào mừng bạn đến với Huấn Luyện Viên Kỷ Luật Cá Nhân!*\n\n"
            "Tôi là bot giám sát tiến độ thực chiến dành cho kỹ sư IT & game dev.\n"
            "Các lệnh khả dụng:\n"
            "• `/status` - Xem chuỗi streak và lịch sử check-in\n"
            "• `/help` - Xem hướng dẫn chi tiết\n"
        )
        return await self.bot.send_message(message.chat.id, text)

    async def _handle_help(self, message: MockMessage) -> Dict[str, Any]:
        text = (
            "📖 *HƯỚNG DẪN SỬ DỤNG:*\n\n"
            "1. Bot sẽ chủ động gửi thông báo theo lịch đã cài đặt.\n"
            "2. Khi nhận thông báo, chọn 1 trong 3 nút:\n"
            "   - `[✅ Đã hoàn thành]`: Ghi nhận hoàn thành và tăng streak.\n"
            "   - `[⏳ Xin lùi 15 phút]`: Lùi tối đa 2 lần.\n"
            "   - `[🛑 Hôm nay nghỉ (Có lý do)]`: Nhập lý do để AI đánh giá.\n"
        )
        return await self.bot.send_message(message.chat.id, text)

    async def _handle_status(self, message: MockMessage) -> Dict[str, Any]:
        streak_data = await self.storage.get_streak()
        today_str = datetime.now(ZoneInfo(self.config.timezone)).strftime("%Y-%m-%d")
        effective_streak = streak_data.get_effective_streak(today_str)
        text = (
            f"📊 *BÁO CÁO KỶ LUẬT THỰC CHIẾN*\n\n"
            f"🔥 Chuỗi streak hiện tại: *{effective_streak}* ngày\n"
            f"🏆 Kỷ lục streak tốt nhất: *{streak_data.best_streak}* ngày\n"
            f"✅ Tổng số phiên hoàn thành: *{streak_data.total_completions}*\n"
            f"📅 Lần cuối hoàn thành: `{streak_data.last_completed_date or 'Chưa có'}`"
        )
        return await self.bot.send_message(message.chat.id, text)

    async def _handle_callback(self, query: MockCallbackQuery) -> Dict[str, Any]:
        data = query.data
        parts = data.split(":", 1)
        action = parts[0]
        session_id = parts[1] if len(parts) > 1 else "default_session"

        if action == "done":
            await query.answer("Ghi nhận hoàn thành!")
            today_str = datetime.now(ZoneInfo(self.config.timezone)).strftime("%Y-%m-%d")
            streak_data = await self.storage.record_completion(session_id, "session", today_str)
            praise = await self.coach.get_congratulation("session", streak_data.current_streak)
            text = (
                f"✅ *HOÀN THÀNH XUẤT SẮC!*\n"
                f"Chuỗi streak: *{streak_data.current_streak}* ngày liên tiếp.\n\n"
                f"🤖 Coach: _{praise}_"
            )
            return await query.edit_message_text(text)

        elif action == "snooze":
            status = await self.storage.get_session_status(session_id)
            curr_count = status.get("snooze_count", 0) if status else 0
            new_count = curr_count + 1

            if new_count > self.config.max_snoozes:
                await query.answer("Đã đạt giới hạn lùi giờ!", show_alert=True)
                warning_2 = self.config.prompts.get(
                    "snooze_warning_2",
                    "⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!",
                )
                return await query.edit_message_text(f"⚠️ *HẾT QUYỀN LÙI GIỜ!*\n\n{warning_2}")

            await self.storage.record_snooze(session_id, new_count)
            self.scheduler.schedule_snooze_job(
                session_id=session_id,
                session_type="session",
                snooze_count=new_count,
                delay_minutes=self.config.snooze_minutes,
                callback=self._snooze_job_callback,
            )
            await query.answer(f"Đã lùi 15 phút (Lần {new_count}/{self.config.max_snoozes})")

            warning = (
                self.config.fallbacks.get("offline_snooze_1", "Đã lùi 15 phút (Lần 1/2).")
                if new_count == 1
                else self.config.fallbacks.get("offline_snooze_2", "Đã lùi 15 phút (Lần 2/2).")
            )
            return await query.edit_message_text(
                f"⏳ *ĐÃ LÙI 15 PHÚT (Lần {new_count}/{self.config.max_snoozes})*\n\n{warning}",
                reply_markup=make_inline_action_keyboard(session_id),
            )

        elif action == "skip":
            await query.answer("Nhập lý do xin nghỉ.")
            self.active_session_awaiting_reason = {"session_id": session_id, "session_type": "session"}
            data_dict = await self.storage.load_data()
            data_dict["awaiting_reason"] = {"session_id": session_id, "session_type": "session"}
            await self.storage.save_data(data_dict)
            return await query.edit_message_text(
                "🛑 *XIN NGHỈ CÓ LÝ DO*\n\n"
                "Hãy gửi tin nhắn giải trình lý do bạn không thể hoàn thành phiên này. "
                "AI Coach sẽ đánh giá xem đây là lý do chính đáng hay sự trì hoãn!"
            )

        return await query.answer("Không nhận diện được thao tác.")

    async def _handle_text(self, message: MockMessage) -> Dict[str, Any]:
        data_dict = await self.storage.load_data()
        awaiting = data_dict.get("awaiting_reason") or self.active_session_awaiting_reason

        if awaiting:
            session_id = awaiting.get("session_id", "session")
            session_type = awaiting.get("session_type", "session")
            reason_text = message.text

            classification, response_text = await self.coach.evaluate_skip_reason(session_type, reason_text)
            timestamp_str = datetime.now(ZoneInfo(self.config.timezone)).isoformat()
            await self.storage.record_skip(session_id, reason_text, classification, timestamp_str)

            data_dict["awaiting_reason"] = None
            self.active_session_awaiting_reason = None
            await self.storage.save_data(data_dict)

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
            return await self.bot.send_message(message.chat.id, reply)

        # Reactive free-form coaching chat
        coach_reply = await self.coach.chat(message.text)
        return await self.bot.send_message(message.chat.id, f"🤖 *Coach*: {coach_reply}")

    async def _snooze_job_callback(self, session_id: str, session_type: str, snooze_count: int) -> None:
        text = (
            f"⏰ *HẾT 15 PHÚT LÙI GIỜ!*\n"
            f"Phiên `{session_type}` đang chờ bạn hoàn thành. (Lần lùi: {snooze_count}/{self.config.max_snoozes})"
        )
        await self.bot.send_message(
            self.config.allowed_chat_id,
            text,
            reply_markup=make_inline_action_keyboard(session_id),
        )


# =====================================================================
# 4. Service Resolvers (Dynamic Resolution to src.* or Fallback to Reference)
# =====================================================================

def get_ai_coach_class() -> Any:
    try:
        from src.coach import AICoachService
        return AICoachService
    except ImportError:
        return DefaultAICoachService


def get_scheduler_class() -> Any:
    try:
        from src.scheduler import SchedulerService
        return SchedulerService
    except ImportError:
        return DefaultSchedulerService


def get_build_application_fn() -> Any:
    try:
        from src.bot import build_application
        return build_application
    except ImportError:
        def _build_app(config: Any, storage: Any, coach: Any, scheduler: Any) -> DefaultBotApplication:
            return DefaultBotApplication(config, storage, coach, scheduler)
        return _build_app
