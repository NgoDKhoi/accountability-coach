# Technical Architecture & Library Integration Survey Report

**Project**: Autonomous Telegram Personal Accountability Coach  
**Author**: teamwork_preview_explorer  
**Date**: 2026-10-03  
**Target Milestone**: Survey Phase Deliverable  

---

## 1. Executive Summary & Architecture Overview

The system is an autonomous, asynchronous Telegram personal accountability coach tailored for an IT student and game developer. The core system architecture is divided into five cohesive, decoupled subsystems:

1. **Telegram Bot Layer (`python-telegram-bot` v20+)**: Handles inbound user interactions, Telegram event polling, inline keyboard callbacks, command dispatching, and strict chat ID security filtering.
2. **Proactive Scheduler Layer (`APScheduler` v3 `AsyncIOScheduler`)**: Runs on the same `asyncio` event loop as the Telegram bot, configured to the `Asia/Ho_Chi_Minh` timezone. It manages cron-based baseline push reminders (Gym, TOEIC with 7-day rotation, Major Study) and dynamic one-shot snooze jobs (15-minute intervals, capped at 2 snoozes).
3. **AI Accountability Coach (`google-genai` SDK, `gemini-2.5-flash`)**: Evaluates user excuses, congratulates discipline upon completion, and engages in concise (max 2–3 sentences) sarcastic/firm accountability dialogue via asynchronous streaming or content generation with a sliding context memory window (6–10 messages).
4. **Atomic JSON Persistence Layer**: Manages persistent state in `data/records.json` (daily streaks, session statuses, snooze counts, skip rationales) utilizing cross-platform atomic file writing (`tempfile.NamedTemporaryFile` + `os.replace`) guarded by an in-process `asyncio.Lock`.
5. **Automated Verification Suite (`pytest` + `pytest-asyncio`)**: Comprehensive test suite mocking Telegram bot context and the Google GenAI API to enable 100% offline, deterministic test runs without external network dependencies or token consumption.

### Subsystem Interaction Flow

```
+-----------------------------------------------------------------------------------+
|                                  asyncio Event Loop                                |
|                                                                                   |
|  +--------------------+        +---------------------+      +------------------+  |
|  |  APScheduler       | triggers| Telegram Bot Core   |pushed| User Telegram    |  |
|  |  (AsyncIOScheduler)|-------->| (PTB v20+)          |----->| Chat (ALLOWED_ID)|  |
|  |  Asia/Ho_Chi_Minh  |         | ApplicationBuilder  |<-----|                  |  |
|  +--------------------+         +---------------------+callbacks                  |
|            ^                               |        |       +------------------+  |
|            | schedules                     |        |                             |
|            | dynamic snooze                v        v                             |
|            |                    +---------------------+                           |
|            +--------------------| Security Guard      | (Rejects unknown chats)   |
|                                 +---------------------+                           |
|                                            |                                      |
|                       +--------------------+--------------------+                 |
|                       |                                         |                 |
|                       v                                         v                 |
|           +-----------------------+                 +-----------------------+     |
|           | Two-Way AI Coach      |                 | Atomic Persistence    |     |
|           | (google-genai Client) |                 | (records.json)        |     |
|           | model: gemini-2.5-flash                 | streaks, sessions     |     |
|           | sliding deque(10)     |                 | NamedTempFile+replace |     |
|           +-----------------------+                 +-----------------------+     |
+-----------------------------------------------------------------------------------+
```

---

## 2. Telegram Bot Architecture (`python-telegram-bot` v20+)

### 2.1 Asynchronous Lifecycle (`ApplicationBuilder`)
`python-telegram-bot` v20+ is completely asynchronous and built natively on Python's `asyncio`. The bot application is created via `ApplicationBuilder`:

```python
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

application = (
    ApplicationBuilder()
    .token(TELEGRAM_BOT_TOKEN)
    .post_init(post_init_hook)
    .post_shutdown(post_shutdown_hook)
    .build()
)
```

#### Lifecycle Hooks: `post_init` and `post_shutdown`
- **`post_init(application: Application)`**: Called asynchronously after `application.initialize()` completes, right before polling or webhook begins. This is the optimal entry point to:
  1. Pass the active `application.bot` instance to the scheduler service.
  2. Start the `AsyncIOScheduler`.
  3. Register bot command descriptions via `await application.bot.set_my_commands(...)`.
- **`post_shutdown(application: Application)`**: Called when the application is stopping. Safely shuts down the `AsyncIOScheduler` without blocking or leaking background tasks.

### 2.2 PTB JobQueue vs. Dedicated `AsyncIOScheduler`

PTB offers an optional `application.job_queue` (which internally wraps `AsyncIOScheduler`). However, using a **dedicated `SchedulerService`** that instantiates `apscheduler.schedulers.asyncio.AsyncIOScheduler` directly is strongly recommended for this project:

| Feature / Criteria | PTB Built-in `JobQueue` | Dedicated `SchedulerService` (`AsyncIOScheduler`) |
| :--- | :--- | :--- |
| **API Compatibility** | PTB wrapper methods (`run_daily`, `run_once`, `run_custom`) | Standard `APScheduler` API (`CronTrigger`, `DateTrigger`, `add_job`) |
| **Direct Requirement Compliance** | Partially abstracts APScheduler | Directly satisfies Requirement R2 ("Integrate an async scheduler using APScheduler (AsyncIOScheduler)") |
| **Testability in Pytest** | Requires instantiating/mocking PTB `Application` | Standalone testable without PTB Application or network mocks |
| **Dynamic Snooze Management** | Wrapping triggers through PTB custom jobs | Direct `scheduler.add_job(..., trigger=DateTrigger(...), id=unique_id)` |
| **Timezone Enforcement** | Defaults to `application.defaults.tzinfo` | Explicitly configured `AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))` |

**Architectural Choice**: Use a dedicated `SchedulerService` wrapping `AsyncIOScheduler`. Register its startup and shutdown in PTB's `post_init` and `post_shutdown` hooks.

### 2.3 Strict User Authorization Guard

Requirement R1 mandates: *Only respond to and accept commands from the user matching `ALLOWED_CHAT_ID` configured via `.env`. Any messages or callbacks from unknown chat IDs must be ignored or rejected to protect Gemini API quotas and private schedules.*

#### Implementation Pattern: Authorization Middleware / Decorator
```python
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

def authorized_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id if update.effective_chat else None
        allowed_id = context.bot_data.get("allowed_chat_id")
        
        if chat_id != allowed_id:
            # Reject immediately: do not execute handler logic, do not invoke Gemini
            if update.callback_query:
                await update.callback_query.answer("⛔ Access denied.", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ Truy cập bị từ chối. Bot này được cấu hình riêng tư.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
```
This guarantees zero token consumption and zero state mutations for unauthorized incoming updates.

### 2.4 Interactive UX & Callback Query Management

#### Inline Keyboard Layout
Each proactive reminder presents 3 action buttons:
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_reminder_keyboard(session_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Đã hoàn thành", callback_data=f"done:{session_id}"),
        ],
        [
            InlineKeyboardButton("⏳ Xin lùi 15 phút", callback_data=f"snooze:{session_id}"),
            InlineKeyboardButton("🛑 Hôm nay nghỉ (Có lý do)", callback_data=f"skip:{session_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
```
*Note on Callback Data Limit*: Telegram strictly enforces a 64-byte limit on `callback_data`. Using concise prefixes like `done:gym`, `snooze:toeic`, `skip:major` uses only 8–15 bytes, safely within limits.

#### Handling Button Presses
1. **`await update.callback_query.answer()`**: Must always be awaited immediately to prevent the client-side loading clock from spinning indefinitely.
2. **`await update.callback_query.edit_message_text(...)`**: Prevents button spam and provides immediate visual feedback of the session status change.

---

## 3. Proactive Scheduler Architecture (`APScheduler` v3)

### 3.1 Timezone & Scheduler Configuration
APScheduler 3.x works seamlessly with Python's standard `zoneinfo` module:
```python
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

HO_CHI_MINH_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
scheduler = AsyncIOScheduler(timezone=HO_CHI_MINH_TZ)
```
*Windows/Docker Note*: In Python on Windows and slim Linux Docker images, ensure `tzdata` is installed in `requirements.txt` so `ZoneInfo("Asia/Ho_Chi_Minh")` resolves without missing timezone database errors.

### 3.2 Baseline CronTrigger Schedules (from `config.yaml`)

According to Requirement R2, three baseline jobs must be configured:

1. **Gym Session (1 hour)**:
   - Monday, Tuesday, Thursday at 17:15 (window: 17:30 – 18:30)
   - Wednesday, Saturday at 16:15 (window: 16:30 – 17:30)
   - *APScheduler note*: Weekdays in APScheduler 3.x can be specified as strings `'mon,tue,thu'` and `'wed,sat'`.
2. **TOEIC Study Session (1 hour)**:
   - Daily at 19:25 (window: 19:30 – 20:30)
   - *Dynamic 7-Day Syllabus Rotation*: When the job triggers, calculate the current day of the week in `Asia/Ho_Chi_Minh` (`now.weekday()`: 0=Mon, ..., 6=Sun) and dynamically extract the syllabus item from `config.yaml`:
     - Mon: Part 1 - Photographs
     - Tue: Part 2 - Question-Response
     - Wed: Part 3 - Short Conversations
     - Thu: Part 4 - Short Talks
     - Fri: Part 5 - Incomplete Sentences
     - Sat: Part 6 - Text Completion
     - Sun: Part 7 - Reading Comprehension & Full Review
3. **Major Subject Study & Preparation (1 hour)**:
   - Daily at 20:40 (window: 20:45 – 21:45)

#### Registration Implementation:
```python
def register_baseline_jobs(scheduler: AsyncIOScheduler, config: dict, bot, allowed_chat_id: int):
    # 1. Gym Mon, Tue, Thu
    scheduler.add_job(
        send_gym_reminder,
        trigger=CronTrigger(day_of_week='mon,tue,thu', hour=17, minute=15, timezone=HO_CHI_MINH_TZ),
        id="cron_gym_mon_tue_thu",
        replace_existing=True,
        kwargs={"bot": bot, "chat_id": allowed_chat_id}
    )
    # 2. Gym Wed, Sat
    scheduler.add_job(
        send_gym_reminder,
        trigger=CronTrigger(day_of_week='wed,sat', hour=16, minute=15, timezone=HO_CHI_MINH_TZ),
        id="cron_gym_wed_sat",
        replace_existing=True,
        kwargs={"bot": bot, "chat_id": allowed_chat_id}
    )
    # 3. TOEIC Daily
    scheduler.add_job(
        send_toeic_reminder,
        trigger=CronTrigger(day_of_week='*', hour=19, minute=25, timezone=HO_CHI_MINH_TZ),
        id="cron_toeic_daily",
        replace_existing=True,
        kwargs={"bot": bot, "chat_id": allowed_chat_id, "syllabus": config.get("toeic_syllabus")}
    )
    # 4. Major Subject Daily
    scheduler.add_job(
        send_major_reminder,
        trigger=CronTrigger(day_of_week='*', hour=20, minute=40, timezone=HO_CHI_MINH_TZ),
        id="cron_major_daily",
        replace_existing=True,
        kwargs={"bot": bot, "chat_id": allowed_chat_id}
    )
```

### 3.3 Dynamic Snooze Job Scheduling & Snooze Cap Enforcement

When the user clicks `[⏳ Xin lùi 15 phút]`:
1. Check persistence layer for current session's `snooze_count`.
2. **Enforce Cap (Max 2 Snoozes)**:
   - If `snooze_count >= 2`: Reject additional snooze. Edit message to escalate firmness:
     *"🛑 Bạn đã lùi 2 lần tối đa (30 phút) cho buổi này! Không có lần thứ 3. Bắt đầu ngay hoặc chấp nhận đối mặt với lý do trốn tránh!"*
   - If `snooze_count < 2`: Increment `snooze_count` by 1.
3. **Schedule Dynamic DateTrigger Job**:
   ```python
   from datetime import datetime, timedelta

   snooze_time = datetime.now(HO_CHI_MINH_TZ) + timedelta(minutes=15)
   job_id = f"snooze_{session_id}_{date_str}_{snooze_count}"

   scheduler.add_job(
       send_snooze_reminder,
       trigger=DateTrigger(run_date=snooze_time, timezone=HO_CHI_MINH_TZ),
       id=job_id,
       replace_existing=True,
       kwargs={
           "bot": bot,
           "chat_id": allowed_chat_id,
           "session_id": session_id,
           "snooze_count": snooze_count,
       }
   )
   ```
4. Update message to indicate snoozed state and next reminder time.

---

## 4. Two-Way AI Accountability Coach (`google-genai` SDK)

### 4.1 Modern SDK & Model Initialization
The official Google GenAI library is `google-genai` (replaces legacy `google-generativeai`).
- Module imports: `from google import genai` and `from google.genai import types`
- Model: `gemini-2.5-flash`
- Asynchronous interface: `client.aio.models.generate_content(...)`

```python
from google import genai
from google.genai import types

class GeminiCoachService:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.system_instruction = (
            "Bạn là một huấn luyện viên kỷ luật cá nhân tự chủ (Accountability Coach) "
            "dành cho một sinh viên IT kiêm lập trình viên game. "
            "Tính cách: Thẳng thắn, ngắn gọn, tư duy thực tế/kỹ thuật, châm biếm nhẹ nhàng đối với sự trì hoãn và lý do lười biếng, "
            "nhưng ghi nhận và khen ngợi sự kỷ luật khi hoàn thành công việc. "
            "QUY TẮC CỐT LÕI: Phản hồi cực kỳ súc tích, tối đa 2 đến 3 câu. Không dài dòng triết lý."
        )
```

### 4.2 In-Memory Sliding Context Window
Requirement R4 specifies: *Maintain a short-term sliding context window (recent 6–10 messages) in memory so the AI understands ongoing dialogue context.*

#### Data Structure & Trimming
Using `collections.deque(maxlen=10)` ensures automatic eviction of older dialogue while keeping memory bounded.

```python
from collections import deque

class SlidingHistory:
    def __init__(self, maxlen: int = 10):
        self.history = deque(maxlen=maxlen)

    def add_message(self, role: str, text: str):
        # role: "user" or "model"
        self.history.append({"role": role, "text": text})

    def get_contents(self) -> list[types.Content]:
        # Google Gemini API requires conversation history to begin with a 'user' turn
        messages = list(self.history)
        while messages and messages[0]["role"] != "user":
            messages.pop(0)

        contents = []
        for msg in messages:
            contents.append(
                types.Content(
                    role=msg["role"],
                    parts=[types.Part.from_text(text=msg["text"])]
                )
            )
        return contents
```

### 4.3 Excuse Evaluation Flow (`[🛑 Hôm nay nghỉ]` Flow)
When the user requests to skip, the bot captures the justification text and forwards it to Gemini with an evaluation prompt:

```python
async def evaluate_skip_reason(self, session_title: str, user_reason: str) -> dict:
    prompt = f"""
Nhiệm vụ: Phân tích lý do người dùng xin nghỉ buổi: '{session_title}'.
Lý do người dùng đưa ra: '{user_reason}'.

Tiêu chí:
1. Đánh giá xem đây là lý do chính đáng (bệnh nặng, sự cố khẩn cấp bất khả kháng) hay lý do trì hoãn/lười biếng (mệt nhẹ, lướt web, chơi game, ngại làm).
2. Nếu là trì hoãn: Châm biếm nhẹ, bẻ gãy lý do và ép buộc một vi thói quen 2 phút (2-minute micro-habit).
3. Nếu chính đáng: Đồng cảm ngắn gọn, ghi nhận nghỉ và nhắc phục hồi thể lực/tinh thần.
4. Trả lời trực tiếp người dùng bằng tiếng Việt, tối đa 2-3 câu.
"""
    # Generates response using async client
    response_text = await self.generate_response(prompt)
    return response_text
```

### 4.4 Resilient Error Handling & Fallbacks
If the Gemini API encounters timeouts, quota limits, or network disconnection, the bot must catch errors gracefully so operations are never disrupted:

```python
try:
    response = await self.client.aio.models.generate_content(
        model=self.model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            temperature=0.7,
            max_output_tokens=250,
        )
    )
    return response.text.strip()
except Exception as e:
    logger.error(f"Gemini API invocation error: {e}")
    # Deterministic fallback response preserving persona
    return "Hệ thống AI tạm thời gián đoạn kết nối, nhưng kỷ luật của bạn thì không được phép gián đoạn! Hãy bắt đầu nhiệm vụ ngay."
```

---

## 5. Lightweight Atomic JSON Persistence

### 5.1 Data Schema (`data/records.json`)

```json
{
  "streak": {
    "current_streak": 5,
    "longest_streak": 12,
    "last_completed_date": "2026-10-02"
  },
  "sessions": {
    "2026-10-03": {
      "gym": {
        "status": "completed",
        "snooze_count": 1,
        "completed_at": "2026-10-03T17:45:10+07:00",
        "skip_reason": null
      },
      "toeic": {
        "status": "snoozed",
        "snooze_count": 1,
        "completed_at": null,
        "skip_reason": null
      },
      "major": {
        "status": "pending",
        "snooze_count": 0,
        "completed_at": null,
        "skip_reason": null
      }
    }
  }
}
```

### 5.2 Streak Calculation Logic
- When a session is marked `completed`:
  - Calculate `today = datetime.now(HO_CHI_MINH_TZ).date()`.
  - Let `last_date = streak["last_completed_date"]`.
  - If `last_date == today`: current streak already credited for today.
  - If `last_date == today - timedelta(days=1)`: `current_streak += 1`.
  - If `last_date < today - timedelta(days=1)` or `last_date is None`: `current_streak = 1` (streak reset).
  - Update `longest_streak = max(longest_streak, current_streak)`.
  - Update `last_completed_date = today.isoformat()`.

### 5.3 Cross-Platform Atomic File Writing (`os.replace`)

#### The Windows File Locking Trap
On Windows, attempting to rename or replace an open file yields:
`PermissionError: [WinError 32] The process cannot access the file because it is being used by another process.`

In Python, standard `tempfile.NamedTemporaryFile` on Windows opens the file with exclusive access. Therefore, code **must close the file handle before invoking `os.replace`**.

#### The Atomic Replace Solution:
```python
import os
import json
import tempfile
import asyncio

class AtomicJsonStore:
    def __init__(self, file_path: str):
        self.file_path = os.path.abspath(file_path)
        self.dir_name = os.path.dirname(self.file_path)
        self._lock = asyncio.Lock()
        self._ensure_directory()

    def _ensure_directory(self):
        os.makedirs(self.dir_name, exist_ok=True)

    async def write_data(self, data: dict):
        async with self._lock:
            # Run file I/O in threadpool or direct sync within lock
            await asyncio.to_thread(self._sync_atomic_write, data)

    def _sync_atomic_write(self, data: dict):
        self._ensure_directory()
        # CRITICAL: Create temporary file in the EXACT SAME directory
        # to ensure it resides on the same filesystem/drive volume for os.replace()
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.dir_name,
            delete=False,
            encoding="utf-8"
        )
        temp_path = temp_file.name
        try:
            json.dump(data, temp_file, indent=2, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()  # MUST CLOSE BEFORE os.replace on Windows!

            # Atomic rename / replace
            os.replace(temp_path, self.file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
```

#### Why this guarantees data integrity:
1. **Same-filesystem volume**: Placing the temp file in `dir=self.dir_name` prevents `EXDEV` (Cross-device link) errors on Linux and `WinError 17` on Windows.
2. **Crash resistance**: If the system crashes mid-write, `data/records.json` remains intact; the partial write only exists in an unlinked temporary file.
3. **In-process concurrency**: `asyncio.Lock()` eliminates race conditions between simultaneous coroutine updates (e.g. quick button double-clicks or concurrent job fires).

---

## 6. Automated Test Suite Architecture (`pytest` + `pytest-asyncio`)

### 6.1 Pytest Configuration (`pytest.ini`)
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```
With `asyncio_mode = auto`, every `async def test_...()` is natively executed on an event loop without needing manual `@pytest.mark.asyncio` annotations.

### 6.2 Mocking Strategy: Telegram Objects

Unit testing PTB handlers does not require spinning up a live Telegram polling bot. We construct mock `Update` and `Context` instances:

```python
from unittest.mock import AsyncMock, MagicMock
from telegram import Update
from telegram.ext import ContextTypes

def create_mock_command_update(chat_id: int, text: str = "/start") -> Update:
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_user = MagicMock()
    update.effective_user.id = chat_id
    update.message = MagicMock()
    update.message.chat_id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update

def create_mock_callback_update(chat_id: int, callback_data: str) -> Update:
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    update.message = None
    
    cb = MagicMock()
    cb.id = "cb_test_id"
    cb.data = callback_data
    cb.from_user = MagicMock()
    cb.from_user.id = chat_id
    cb.answer = AsyncMock()
    cb.edit_message_text = AsyncMock()
    update.callback_query = cb
    return update

def create_mock_context(allowed_chat_id: int) -> ContextTypes.DEFAULT_TYPE:
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {"allowed_chat_id": allowed_chat_id}
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()
    return context
```

### 6.3 Mocking Strategy: `google-genai` Client

To test the coach and excuse evaluation without real API keys:
```python
def create_mock_gemini_service(canned_response: str = "Tập trung làm ngay đi!"):
    mock_service = MagicMock()
    mock_service.generate_response = AsyncMock(return_value=canned_response)
    mock_service.evaluate_skip_reason = AsyncMock(return_value=canned_response)
    return mock_service
```
Or at the SDK level:
```python
mock_client = MagicMock()
mock_response = MagicMock()
mock_response.text = "Tập trung làm ngay đi!"
mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)
```

### 6.4 Verification Coverage Matrix

| Test Module | Test Case | Expected Behavior |
| :--- | :--- | :--- |
| `test_security.py` | Unauthorized `/start` | Request ignored or rejected; 0 Gemini calls, 0 store mutations. |
| `test_security.py` | Unauthorized callback | `callback_query.answer("⛔ Access denied")`; no action performed. |
| `test_scheduler.py` | Baseline schedule registration | `get_jobs()` contains gym, toeic, major with correct CronTriggers in `Asia/Ho_Chi_Minh`. |
| `test_scheduler.py` | TOEIC dynamic rotation | Day 0 -> Part 1, Day 1 -> Part 2, ..., Day 6 -> Part 7. |
| `test_callbacks.py` | Mark Done (`done:gym`) | Store marked completed, streak incremented, congratulations sent. |
| `test_callbacks.py` | Snooze 1 & 2 (`snooze:gym`) | DateTrigger job created (+15m), `snooze_count` incremented. |
| `test_callbacks.py` | Snooze 3 (exceeds cap) | No new snooze job scheduled; firm warning message returned. |
| `test_callbacks.py` | Skip reason flow (`skip:gym`) | State awaits reason -> Text processed by Gemini evaluator -> Status saved. |
| `test_storage.py` | Atomic JSON writing | Temp file replaced atomically; corrupted writes prevented; dir created. |
| `test_storage.py` | Streak logic | Streak increments on consecutive days, resets on gap days. |
| `test_gemini.py` | Error fallback | Network exception in Gemini client triggers graceful fallback string without crashing. |

---

## 7. Recommended Project Layout & Operational Templates

### 7.1 Recommended Directory Tree
```
serene-bohr/
├── .env.example
├── .gitignore
├── config.yaml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── start.bat
├── start.sh
├── pytest.ini
├── data/
│   └── records.json            # Created dynamically if missing
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entrypoint & signal handling
│   ├── config.py               # Settings loader (.env + config.yaml)
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── app.py              # PTB ApplicationBuilder & lifecycle hooks
│   │   ├── handlers.py         # Commands & MessageHandlers
│   │   ├── callbacks.py        # CallbackQueryHandlers (done, snooze, skip)
│   │   └── security.py         # Authorization guard decorator
│   ├── scheduler/
│   │   ├── __init__.py
│   │   ├── service.py          # APScheduler AsyncIOScheduler management
│   │   ├── triggers.py         # Baseline Cron and dynamic Date triggers
│   │   └── jobs.py             # Push notification routines
│   ├── coach/
│   │   ├── __init__.py
│   │   ├── gemini.py           # google-genai Client wrapper & sliding context
│   │   └── prompts.py          # Prompt templates & persona instructions
│   └── storage/
│       ├── __init__.py
│       ├── atomic_store.py     # Atomic JSON file I/O & asyncio.Lock
│       └── models.py           # Dataclasses / schemas for sessions & streaks
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures (mocks, temp stores)
    ├── test_security.py
    ├── test_scheduler.py
    ├── test_callbacks.py
    ├── test_coach.py
    └── test_storage.py
```

### 7.2 Configuration Templates

#### `.env.example`
```bash
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
GEMINI_API_KEY="your_gemini_api_key_here"
ALLOWED_CHAT_ID="123456789"
```

#### `config.yaml`
```yaml
timezone: "Asia/Ho_Chi_Minh"

schedules:
  gym:
    title: "Gym Session (1 giờ)"
    window: "17:30 - 18:30"
    triggers:
      - days: "mon,tue,thu"
        time: "17:15"
      - days: "wed,sat"
        time: "16:15"
  toeic:
    title: "TOEIC Study Session (1 giờ)"
    window: "19:30 - 20:30"
    triggers:
      - days: "*"
        time: "19:25"
  major:
    title: "Major Subject Study & Preparation (1 giờ)"
    window: "20:45 - 21:45"
    triggers:
      - days: "*"
        time: "20:40"

toeic_syllabus:
  0: "Part 1 - Photographs (Nghe tranh)"
  1: "Part 2 - Question-Response (Hỏi đáp)"
  2: "Part 3 - Short Conversations (Hội thoại ngắn)"
  3: "Part 4 - Short Talks (Bài nói ngắn)"
  4: "Part 5 - Incomplete Sentences (Điền câu - Ngữ pháp/Từ vựng)"
  5: "Part 6 - Text Completion (Điền đoạn văn)"
  6: "Part 7 - Reading Comprehension & Full Review (Đọc hiểu & Tổng ôn)"

snooze:
  duration_minutes: 15
  max_snoozes: 2

coach:
  model: "gemini-2.5-flash"
  temperature: 0.7
  max_context_messages: 10
```

#### `requirements.txt`
```text
python-telegram-bot>=20.8,<22.0
APScheduler>=3.10.4,<4.0.0
google-genai>=1.0.0
PyYAML>=6.0.1
python-dotenv>=1.0.1
tzdata>=2024.1
pytest>=8.0.0
pytest-asyncio>=0.23.5
```

### 7.3 Containerization & Startup Scripts

#### `Dockerfile`
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY . .

# Run bot
CMD ["python", "src/main.py"]
```

#### `docker-compose.yml`
```yaml
version: '3.8'

services:
  accountability_bot:
    build: .
    container_name: telegram_coach_bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
```

#### `start.bat` (Windows)
```bat
@echo off
setlocal
echo Starting Accountability Coach Bot...

if not exist .env (
    echo Error: .env file not found. Please copy .env.example to .env and configure secrets.
    exit /b 1
)

python -m pip install -r requirements.txt
python src/main.py
```

#### `start.sh` (Linux / macOS)
```bash
#!/bin/bash
set -e
echo "Starting Accountability Coach Bot..."

if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and configure secrets."
    exit 1
fi

pip install -r requirements.txt
python src/main.py
```

---

## 8. Summary of Downstream Implementation Directives

1. **Keep `SchedulerService` autonomous**: Wrap `AsyncIOScheduler` directly; wire it to PTB via `post_init` and `post_shutdown`.
2. **Close before replacing on Windows**: In `atomic_store.py`, ensure temporary files are explicitly closed before calling `os.replace`.
3. **Guard every Telegram handler**: Apply `@authorized_only` to all handlers (`CommandHandler`, `CallbackQueryHandler`, `MessageHandler`).
4. **Enforce 2-3 sentences**: Configure `types.GenerateContentConfig(system_instruction=...)` for `gemini-2.5-flash` with explicit brevity constraints.
5. **Decouple testing from network**: Use pure unit test mocks for Telegram updates and the `google-genai` client, enabling fast, repeatable offline CI testing.
