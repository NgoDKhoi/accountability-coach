# Interface Boundaries, Schemas & Lifecycle Architecture Analysis

**Author:** `teamwork_preview_explorer` (Survey Phase - Explorer 2)  
**Target Project:** Autonomous Telegram Personal Accountability Coach (`serene-bohr`)  
**Date:** 2026-10-03  
**Status:** Approved Architectural Specification  

---

## 1. Executive Summary & Architecture Overview

The system is an autonomous, proactive Telegram personal accountability coach tailored for an IT student and game developer. It pairs proactive time-based push notifications (`APScheduler`) with Telegram inline interaction buttons (`python-telegram-bot` v20+), an AI accountability coach powered by Google Gemini (`google-genai` using `gemini-2.5-flash`), and atomic local JSON persistence (`data/records.json`).

### 1.1 System Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                                Telegram Cloud API                                 |
+-----------------------------------------------------------------------------------+
               ^                                           |
               | Push Notifications / Replies              | Incoming Updates (Poll)
               v                                           v
+-----------------------------------------------------------------------------------+
| src/bot.py (Telegram Bot Core, Security Filter & Handlers)                        |
|   - Security Guard: Enforces ALLOWED_CHAT_ID (rejects unauthorized users silently) |
|   - UI Builder: Generates Inline Keyboards (Done / Snooze 15m / Skip with Reason) |
|   - Handlers: Commands (/start, /status, /streak), Callbacks, Reason Capture      |
+-----------------------------------------------------------------------------------+
         |                            |                               |
         | Invokes                    | Queries / Updates             | Schedules One-Shot
         v                            v                               v
+------------------+         +--------------------+         +-----------------------+
|   src/coach.py   |         |   src/storage.py   |         |   src/scheduler.py    |
| (Gemini 2.5 AI)  |         | (Atomic Storage)   |         | (APScheduler Async)   |
| - Persona Coach  |         | - records.json     |         | - Asia/Ho_Chi_Minh    |
| - Sliding Window |         | - Atomic rename    |         | - Gym, TOEIC, Major   |
| - Excuse Eval    |         | - Streak tracker   |         | - 15-min Snooze jobs  |
| - Fallback engine|         | - Session states   |         +-----------------------+
+------------------+         +--------------------+                     |
         |                            ^                                 |
         | Calls                      |                                 | Fires Reminder
         v                            +---------------------------------+
+-----------------------------------------------------------------------------------+
| src/config.py (Unified Configuration Engine)                                      |
| - .env (Secrets: TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, ALLOWED_CHAT_ID)             |
| - config.yaml (Schedules, TOEIC 7-day rotation, Prompts, Timezone, Limits)        |
+-----------------------------------------------------------------------------------+
```

---

## 2. Configuration Specifications

Configuration is strictly bifurcated:
1. **Secrets & Environment Variables (`.env`)**: Sensitive tokens and machine-specific IDs.
2. **Operational Parameters (`config.yaml`)**: Schedules, syllabus rotation, AI prompts, timeouts, and limits.

### 2.1 `.env` and `.env.example` Specification

The project must provide a checked-in template `.env.example`. The live `.env` is ignored by `.gitignore`.

#### `.env.example`
```env
# =================================================================
# Telegram Personal Accountability Coach - Environment Configuration
# =================================================================

# Telegram Bot API Token obtained from @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi

# Google Gemini API Key from Google AI Studio (https://aistudio.google.com/)
GEMINI_API_KEY=AIzaSyYourGeminiApiKeyHere1234567890

# Authorized Telegram Chat ID (Strict authorization: integer only)
# Find your Chat ID by messaging @userinfobot or checking bot updates
ALLOWED_CHAT_ID=123456789

# Optional Application Overrides
CONFIG_PATH=config.yaml
LOG_LEVEL=INFO
```

#### Environment Variable Validation Rules
| Variable | Type | Required | Validation Rule | On Failure Action |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | string | Yes | Format `^\d+:[A-Za-z0-9_-]{35,}$` | Raise `ValueError("Invalid TELEGRAM_BOT_TOKEN")`, abort startup |
| `GEMINI_API_KEY` | string | Yes | Non-empty string (`len > 10`) | Raise `ValueError("Invalid GEMINI_API_KEY")`, abort startup |
| `ALLOWED_CHAT_ID` | integer | Yes | Parseable integer (`int(val) != 0`) | Raise `ValueError("ALLOWED_CHAT_ID must be a non-zero integer")`, abort startup |
| `CONFIG_PATH` | string | No | Path exists on filesystem, defaults to `config.yaml` | Raise `FileNotFoundError` if custom path invalid |
| `LOG_LEVEL` | string | No | One of `DEBUG, INFO, WARNING, ERROR, CRITICAL`, default `INFO` | Fallback to `INFO` |

---

### 2.2 `config.yaml` Exact Specification

The `config.yaml` manages operational behavior without requiring code changes.

```yaml
app:
  timezone: "Asia/Ho_Chi_Minh"
  history_limit: 10
  data_dir: "data"
  records_file: "data/records.json"

limits:
  snooze_duration_minutes: 15
  max_snoozes: 2
  micro_habit_duration_minutes: 2

schedules:
  gym:
    name: "Gym Session"
    enabled: true
    window: "1 hour"
    triggers:
      - days: ["mon", "tue", "thu"]
        time: "17:15"
        window_display: "17:30 – 18:30"
      - days: ["wed", "sat"]
        time: "16:15"
        window_display: "16:30 – 17:30"
    message_template: "🏋️‍♂️ *GIỜ TẬP GYM ĐÃ ĐẾN!*\nKhung giờ tập: `{window}`\nChuẩn bị đồ tập, nạp năng lượng và rời bàn làm việc ngay nào!"

  toeic:
    name: "TOEIC Study Session"
    enabled: true
    window: "19:30 – 20:30"
    trigger_time: "19:25"
    message_template: "📚 *GIỜ HỌC TOEIC!*\nChủ đề hôm nay: *{topic}*\nKhung giờ học: `{window}`\nBật Pomodoro 25/5 và tập trung cao độ, không lướt mạng xã hội!"
    rotation:
      mon: "Part 1 - Photographs (Mô tả hình ảnh)"
      tue: "Part 2 - Question-Response (Hỏi & Đáp)"
      wed: "Part 3 - Short Conversations (Đối thoại ngắn)"
      thu: "Part 4 - Short Talks (Bài nói ngắn)"
      fri: "Part 5 - Incomplete Sentences (Ngữ pháp & Từ vựng)"
      sat: "Part 6 - Text Completion (Điền đoạn văn)"
      sun: "Part 7 - Reading Comprehension & Full Mock Review"

  major:
    name: "Major Subject Study & Game Dev"
    enabled: true
    window: "20:45 – 21:45"
    trigger_time: "20:40"
    message_template: "💻 *GIỜ CÀY CHUYÊN NGÀNH & GAME DEV!*\nKhung giờ: `{window}`\nĐào sâu kiến trúc game engine, tối ưu thuật toán và commit code chất lượng!"

ai_coach:
  model: "gemini-2.5-flash"
  temperature: 0.7
  max_output_tokens: 256
  system_prompt: >
    Bạn là Huấn Luyện Viên Kỷ Luật Cá Nhân (AI Accountability Coach) dành riêng cho một sinh viên IT kiêm lập trình viên game.
    Phong cách: Trực tiếp, súc tích, mang tư duy kỹ thuật/thực tế, hơi mỉa mai và châm biếm sắc sảo trước sự trì hoãn/lý do bao biện, nhưng nhiệt tình ghi nhận và tôn trọng kỷ luật hành động thực chất.
    QUY TẮC BẮT BUỘC: Mỗi câu trả lời KHÔNG ĐƯỢC QUÁ 2-3 câu ngắn gọn. Không dài dòng, không nói đạo lý sáo rỗng. Luôn thúc đẩy hành động ngay lập tức.

  prompts:
    completion_praise: >
      Người dùng vừa hoàn thành phiên {session_name} ({detail}). Streak hiện tại: {streak} ngày liên tiếp.
      Hãy gửi một câu khen ngợi ngắn gọn (tối đa 2 câu), ghi nhận tính kỷ luật thực chiến của một kỹ sư.

    snooze_warning_1: >
      Người dùng vừa xin lùi 15 phút lần thứ 1 cho phiên {session_name}.
      Hãy cảnh báo ngắn gọn (tối đa 2 câu) theo phong cách mỉa mai nhẹ về việc trì hoãn, nhắc nhở họ chỉ còn đúng 1 lần lùi nữa.

    snooze_warning_2: >
      Người dùng đã lùi 15 phút lần thứ 2 (ĐÃ ĐẠT GIỚI HẠN TỐI ĐA) cho phiên {session_name}.
      Hãy ra lệnh dứt khoát, gay gắt (tối đa 2 câu): Hết giờ dây dưa, dẹp điện thoại và bắt tay vào việc ngay lập tức!

    skip_evaluator: >
      Người dùng muốn bỏ phiên {session_name} ({detail}) với lý do: "{reason}".
      Nhiệm vụ:
      1. Đánh giá xem đây là lý do bất khả kháng chính đáng (bệnh tật, cấp cứu, sự cố khẩn cấp) hay chỉ là lý do bao biện/lười biếng/trì hoãn.
      2. Nếu là BAO BIỆN: Bóc trần lý do bằng 1 câu châm biếm sắc bén, và ép thực hiện 'micro-habit 2 phút' (ví dụ: mở sách đọc 2 phút hoặc làm 5 cái chống đẩy) để không đứt chuỗi. Bắt đầu bằng [EXCUSE].
      3. Nếu là CHÍNH ĐÁNG: Đồng ý cho nghỉ ngơi phục hồi, yêu cầu ngày mai quay lại với 200% năng lượng. Bắt đầu bằng [LEGITIMATE].
      Quy tắc: Tối đa 2-3 câu ngắn gọn.

  fallbacks:
    offline_praise: "✅ Đã ghi nhận hoàn thành! Kỷ luật tạo nên bản lĩnh. Tiếp tục giữ vững chuỗi streak nhé!"
    offline_snooze_1: "⏳ Đã lùi 15 phút (Lần 1/2). Bạn còn đúng một cơ hội lùi giờ nữa. Đừng để sự trì hoãn chiến thắng!"
    offline_snooze_2: "⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!"
    offline_skip_excuse: "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu hoặc hít đất 5 cái trước khi nghỉ!"
    offline_skip_legitimate: "🛑 Đã ghi nhận nghỉ có lý do chính đáng. Nghỉ ngơi phục hồi và ngày mai quay lại với 200% kỷ luật!"
    offline_error: "🤖 AI Coach tạm thời mất kết nối mạng, nhưng kỷ luật của bạn thì không được ngắt quãng. Bắt tay vào việc ngay đi!"
```

---

## 3. Lightweight Atomic JSON Persistence (`data/records.json`)

### 3.1 JSON Data Schema

```json
{
  "version": 1,
  "user_id": 123456789,
  "streak": {
    "current_streak": 5,
    "longest_streak": 14,
    "last_completed_date": "2026-10-03",
    "total_completions": 42
  },
  "active_sessions": {
    "gym_2026-10-03_1715": {
      "session_id": "gym_2026-10-03_1715",
      "session_type": "gym",
      "title": "Gym Session",
      "status": "pending",
      "snooze_count": 0,
      "max_snoozes": 2,
      "scheduled_time": "2026-10-03T17:15:00+07:00",
      "created_at": "2026-10-03T17:15:00+07:00",
      "updated_at": "2026-10-03T17:15:00+07:00",
      "chat_id": 123456789,
      "message_id": 1054,
      "metadata": {
        "window_display": "17:30 – 18:30"
      }
    }
  },
  "awaiting_reason": {
    "session_id": null,
    "prompted_at": null
  },
  "history": [
    {
      "event_id": "evt_20261003_192500_abc123",
      "session_id": "toeic_2026-10-03_1925",
      "session_type": "toeic",
      "title": "TOEIC Study Session",
      "action": "completed",
      "timestamp": "2026-10-03T19:30:12+07:00",
      "snooze_count": 0,
      "reason": null,
      "evaluation": null,
      "metadata": {
        "topic": "Part 1 - Photographs (Mô tả hình ảnh)"
      }
    }
  ]
}
```

### 3.2 Field Definitions & Constraints

| Field Path | Type | Constraint | Description |
|---|---|---|---|
| `version` | integer | Fixed `1` | Schema migration version |
| `user_id` | integer | Matches `ALLOWED_CHAT_ID` | Owner of the persistence store |
| `streak.current_streak` | integer | `>= 0` | Consecutive days with completed sessions |
| `streak.longest_streak` | integer | `>= current_streak` | All-time highest streak recorded |
| `streak.last_completed_date` | string / null | ISO date `YYYY-MM-DD` | Date of the latest completion in `Asia/Ho_Chi_Minh` |
| `streak.total_completions` | integer | `>= 0` | Lifetime count of completed sessions |
| `active_sessions.<id>.status` | string | Enum: `pending`, `snoozed`, `completed`, `skipped` | Current operational state of the session |
| `active_sessions.<id>.snooze_count` | integer | `0 <= val <= 2` | Count of 15-minute snoozes used |
| `awaiting_reason.session_id` | string / null | Non-empty string or `null` | Tracks active session awaiting user justification text |
| `history[].action` | string | Enum: `completed`, `snoozed`, `skipped` | Action recorded in persistent audit log |

### 3.3 Streak Calculation Rules (Calendar Day Boundaries)

All dates are evaluated in the configured timezone (`Asia/Ho_Chi_Minh`):
1. Let `today` be current date string `YYYY-MM-DD` in `Asia/Ho_Chi_Minh`.
2. Let `last_date` be `streak.last_completed_date`.
3. When `mark_completed(session_id)` is invoked:
   - Case A: `last_date == today` (user already completed another session today, e.g. Gym done earlier, now TOEIC done):
     - `current_streak` remains unchanged.
     - `total_completions += 1`.
   - Case B: `last_date == today - 1 day` (consecutive day completion):
     - `current_streak += 1`.
     - `last_completed_date = today`.
     - `longest_streak = max(longest_streak, current_streak)`.
     - `total_completions += 1`.
   - Case C: `last_date < today - 1 day` or `last_date is null` (streak broken or first session):
     - `current_streak = 1`.
     - `last_completed_date = today`.
     - `longest_streak = max(longest_streak, current_streak)`.
     - `total_completions += 1`.
4. When querying streak via `/streak`:
   - If `last_date < today - 1 day` (yesterday had no completion), the effective current streak is `0`. Upon the next completion, it resets to `1`.

### 3.4 Atomic Write Implementation Specification

To prevent file corruption during sudden system crashes, power cuts, or process interruptions:
1. Ensure target directory `data/` exists (`os.makedirs(dir_path, exist_ok=True)`).
2. Generate a temporary file path on the same directory: `f"{file_path}.tmp.{os.getpid()}_{uuid.uuid4().hex[:8]}"`.
3. Open temporary file with `utf-8` encoding and write formatted JSON (`indent=2, ensure_ascii=False`).
4. Force disk sync via `f.flush()` followed by `os.fsync(f.fileno())`.
5. Close file.
6. Perform atomic replacement: `os.replace(temp_file_path, file_path)`. (On POSIX and modern Windows NTFS, `os.replace` is atomic when source and destination reside on the same volume).
7. If any exception occurs during steps 2-5, safely delete temporary file if it exists.

---

## 4. Module Interface Contracts

The system is decomposed into 5 core modules within `src/`:
- `src/config.py`
- `src/storage.py`
- `src/coach.py`
- `src/scheduler.py`
- `src/bot.py`
- `src/main.py`

### 4.1 Config Module (`src/config.py`)

#### Data Classes
```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass(frozen=True)
class EnvConfig:
    telegram_bot_token: str
    gemini_api_key: str
    allowed_chat_id: int
    config_path: str = "config.yaml"
    log_level: str = "INFO"

@dataclass(frozen=True)
class AppConfig:
    timezone: str
    history_limit: int
    data_dir: str
    records_file: str

@dataclass(frozen=True)
class LimitsConfig:
    snooze_duration_minutes: int
    max_snoozes: int
    micro_habit_duration_minutes: int

@dataclass(frozen=True)
class GymTrigger:
    days: List[str]          # ["mon", "tue", "thu"]
    time: str                # "17:15"
    window_display: str      # "17:30 – 18:30"

@dataclass(frozen=True)
class GymSchedule:
    name: str
    enabled: bool
    window: str
    triggers: List[GymTrigger]
    message_template: str

@dataclass(frozen=True)
class ToeicSchedule:
    name: str
    enabled: bool
    window: str
    trigger_time: str
    message_template: str
    rotation: Dict[str, str] # {"mon": "Part 1 - ...", ...}

@dataclass(frozen=True)
class MajorSchedule:
    name: str
    enabled: bool
    window: str
    trigger_time: str
    message_template: str

@dataclass(frozen=True)
class AiCoachConfig:
    model: str
    temperature: float
    max_output_tokens: int
    system_prompt: str
    prompts: Dict[str, str]
    fallbacks: Dict[str, str]

@dataclass(frozen=True)
class Config:
    env: EnvConfig
    app: AppConfig
    limits: LimitsConfig
    gym: GymSchedule
    toeic: ToeicSchedule
    major: MajorSchedule
    ai_coach: AiCoachConfig
```

#### Public Functions
```python
def load_config(config_path: Optional[str] = None) -> Config:
    """Loads environment variables via python-dotenv and operational config from YAML.
    Validates all mandatory keys, types, and constraints.
    Raises ValueError or FileNotFoundError if invalid.
    """
    ...

def mask_secret(secret: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """Returns masked secret string for secure logging (e.g., '1234...wxyz')."""
    ...
```

---

### 4.2 Storage Module (`src/storage.py`)

#### Data Classes
```python
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple

@dataclass
class StreakInfo:
    current_streak: int
    longest_streak: int
    last_completed_date: Optional[str]
    total_completions: int

@dataclass
class ActiveSession:
    session_id: str
    session_type: str         # "gym", "toeic", "major"
    title: str
    status: str               # "pending", "snoozed", "completed", "skipped"
    snooze_count: int
    max_snoozes: int
    scheduled_time: str       # ISO 8601
    created_at: str           # ISO 8601
    updated_at: str           # ISO 8601
    chat_id: int
    message_id: int
    metadata: Dict[str, Any]

@dataclass
class HistoryRecord:
    event_id: str
    session_id: str
    session_type: str
    title: str
    action: str               # "completed", "snoozed", "skipped"
    timestamp: str            # ISO 8601
    snooze_count: int
    reason: Optional[str]
    evaluation: Optional[str]
    metadata: Dict[str, Any]
```

#### Class `StorageManager`
```python
class StorageManager:
    def __init__(self, file_path: str = "data/records.json", user_id: int = 0):
        ...

    def load_data(self) -> Dict[str, Any]:
        """Loads and returns the raw dictionary from file. Initializes default if file absent."""
        ...

    def save_data(self, data: Dict[str, Any]) -> None:
        """Atomically persists the data dictionary using temp file + os.replace."""
        ...

    def create_session(
        self,
        session_id: str,
        session_type: str,
        title: str,
        chat_id: int,
        message_id: int,
        scheduled_time: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_snoozes: int = 2
    ) -> ActiveSession:
        """Creates and stores a new pending active session."""
        ...

    def get_session(self, session_id: str) -> Optional[ActiveSession]:
        """Retrieves session by session_id, or None if not found."""
        ...

    def increment_snooze(self, session_id: str) -> Tuple[ActiveSession, bool]:
        """Increments snooze_count for the session.
        Returns: (updated_session, is_max_reached)
        Raises: ValueError if session not found or already completed/skipped.
        """
        ...

    def mark_completed(
        self,
        session_id: str,
        tz_name: str = "Asia/Ho_Chi_Minh"
    ) -> Tuple[ActiveSession, StreakInfo]:
        """Marks session as 'completed', recalculates daily streak, records history.
        Returns: (updated_session, updated_streak)
        """
        ...

    def mark_skipped(
        self,
        session_id: str,
        reason: str,
        evaluation: str
    ) -> ActiveSession:
        """Marks session as 'skipped', records reason and AI evaluation in history."""
        ...

    def set_awaiting_reason(self, session_id: str) -> None:
        """Sets the state machine to await user text justification for session_id."""
        ...

    def get_awaiting_reason_session_id(self) -> Optional[str]:
        """Returns session_id currently awaiting reason, or None."""
        ...

    def clear_awaiting_reason(self) -> None:
        """Clears the awaiting reason state."""
        ...

    def get_streak_info(self, tz_name: str = "Asia/Ho_Chi_Minh") -> StreakInfo:
        """Calculates and returns current streak state, adjusting for broken streak if yesterday missed."""
        ...

    def get_recent_history(self, limit: int = 10) -> List[HistoryRecord]:
        """Returns the most recent N history records."""
        ...
```

---

### 4.3 AI Coach Module (`src/coach.py`)

Powered by Google Gemini via `google-genai` using model `gemini-2.5-flash`.

#### Class `AICoach`
```python
from typing import Tuple, List, Dict, Optional
from google import genai
from google.genai import types

class AICoach:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        system_prompt: str = "",
        prompts: Optional[Dict[str, str]] = None,
        fallbacks: Optional[Dict[str, str]] = None,
        history_limit: int = 10,
        temperature: float = 0.7,
        max_output_tokens: int = 256
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.prompts = prompts or {}
        self.fallbacks = fallbacks or {}
        self.history_limit = history_limit
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        
        # Async GenAI client initialization
        self.client = genai.Client(api_key=api_key)
        
        # Short-term in-memory sliding dialogue context: List[Dict[str, str]]
        # e.g. [{"role": "user", "text": "..."}, {"role": "model", "text": "..."}]
        self.chat_history: List[Dict[str, str]] = []

    async def generate_congratulations(
        self,
        session_name: str,
        detail: str,
        streak: int
    ) -> str:
        """Generates a 1-2 sentence crisp congratulatory message acknowledging discipline."""
        ...

    async def generate_snooze_warning(
        self,
        session_name: str,
        snooze_count: int,
        max_snoozes: int = 2
    ) -> str:
        """Generates a firm warning on snooze:
        - 1st snooze: light sarcastic warning
        - 2nd snooze (limit reached): harsh, decisive command to execute
        """
        ...

    async def evaluate_skip_reason(
        self,
        session_name: str,
        detail: str,
        reason: str
    ) -> Tuple[bool, str]:
        """Evaluates whether the user's skip reason is an excuse or legitimate obstacle.
        Returns:
            is_excuse: bool (True if procrastination/excuse, False if legitimate)
            response_text: str (AI coach response enforcing 2-min habit or accepting)
        """
        ...

    async def chat(self, user_message: str) -> str:
        """Two-way interactive accountability chat with sliding memory window (6-10 messages)."""
        ...

    def clear_history(self) -> None:
        """Clears short-term conversational context."""
        ...

    def _trim_history(self) -> None:
        """Ensures chat_history does not exceed history_limit."""
        ...
```

#### Graceful Offline Fallback Contract
Whenever an API call fails due to `APIError`, network timeout, or rate limiting:
- Never raise uncaught exceptions to Telegram handlers.
- Log error with details (`logger.warning("Gemini API call failed: %s", exc)`).
- Return corresponding pre-configured string from `config.ai_coach.fallbacks`.
- Keep bot responsive and stable.

---

### 4.4 Scheduler Module (`src/scheduler.py`)

Built with `apscheduler.schedulers.asyncio.AsyncIOScheduler` configured for `Asia/Ho_Chi_Minh`.

#### Class `NotificationScheduler`
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import zoneinfo
from telegram.ext import Application

class NotificationScheduler:
    def __init__(
        self,
        config: Config,
        storage: StorageManager,
        telegram_app: Application,
        tz_name: str = "Asia/Ho_Chi_Minh"
    ):
        self.config = config
        self.storage = storage
        self.telegram_app = telegram_app
        self.tz = zoneinfo.ZoneInfo(tz_name)
        self.scheduler = AsyncIOScheduler(timezone=self.tz)

    def start(self) -> None:
        """Initializes jobs and starts the async scheduler."""
        ...

    def shutdown(self) -> None:
        """Shuts down scheduler and clears jobs cleanly."""
        ...

    def register_scheduled_jobs(self) -> None:
        """Registers Gym, TOEIC, and Major schedule triggers into APScheduler:
        1. Gym:
           - Mon, Tue, Thu at 17:15
           - Wed, Sat at 16:15
        2. TOEIC:
           - Daily at 19:25 (resolves topic dynamically from 7-day rotation)
        3. Major:
           - Daily at 20:40
        """
        ...

    async def trigger_gym_reminder(self, window_display: str) -> None:
        """Creates session and sends push message with inline buttons."""
        ...

    async def trigger_toeic_reminder(self) -> None:
        """Resolves today's day-of-week, looks up TOEIC rotation, creates session and pushes."""
        ...

    async def trigger_major_reminder(self) -> None:
        """Creates session and pushes major study reminder."""
        ...

    def schedule_snooze_reminder(
        self,
        session_id: str,
        delay_minutes: int = 15
    ) -> str:
        """Schedules a one-shot DateTrigger job to run after delay_minutes.
        Returns job_id for tracking.
        """
        ...

    async def trigger_snooze_reminder(self, session_id: str) -> None:
        """Fires the one-shot snooze reminder, updates session, displays escalating warning."""
        ...
```

---

### 4.5 Bot Handlers & UI Module (`src/bot.py`)

#### Security Filter & Middleware
Every handler must check authorization against `ALLOWED_CHAT_ID`:
```python
def is_authorized(chat_id: int, allowed_chat_id: int) -> bool:
    return chat_id == allowed_chat_id
```
- If unauthorized:
  - If a command or text is sent: reply with a standard permission denied notice or drop silently:
    `"⛔ Truy cập bị từ chối. Bạn không có quyền sử dụng bot này."`
  - Do NOT invoke Gemini API. Do NOT record session or streak.

#### UI Keyboards
```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_session_inline_keyboard(session_id: str, snooze_count: int = 0) -> InlineKeyboardMarkup:
    """Generates the 3 mandatory action buttons:
    [✅ Đã hoàn thành]
    [⏳ Xin lùi 15 phút (X/2)]
    [🛑 Hôm nay nghỉ (Có lý do)]
    """
    snooze_label = f"⏳ Xin lùi 15 phút ({snooze_count}/2)" if snooze_count > 0 else "⏳ Xin lùi 15 phút"
    keyboard = [
        [InlineKeyboardButton("✅ Đã hoàn thành", callback_data=f"done:{session_id}")],
        [InlineKeyboardButton(snooze_label, callback_data=f"snooze:{session_id}")],
        [InlineKeyboardButton("🛑 Hôm nay nghỉ (Có lý do)", callback_data=f"skip:{session_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)
```

#### Bot Handlers Specification
| Handler Type | Trigger / Pattern | Action |
|---|---|---|
| Command | `/start` | Welcome message, user status, explanation of proactive schedules |
| Command | `/status` | Active sessions today, pending tasks, recent completion logs |
| Command | `/streak` | Current streak, longest streak, total completions display |
| Command | `/help` | List commands and accountability principles |
| CallbackQuery | `^done:(.+)` | Mark completed, update streak, edit message with checkmark, AI praise |
| CallbackQuery | `^snooze:(.+)` | Increment snooze, check cap `<= 2`, schedule 15m job, AI warning |
| CallbackQuery | `^skip:(.+)` | Set `awaiting_reason` state, prompt user for justification text |
| Message | `filters.TEXT & ~filters.COMMAND` | If awaiting reason -> evaluate via AI, enforce micro-habit or accept. Else -> interactive AI coaching chat |

---

### 4.6 Application Lifecycle (`src/main.py`)

```python
import asyncio
import logging
from src.config import load_config
from src.storage import StorageManager
from src.coach import AICoach
from src.scheduler import NotificationScheduler
from src.bot import create_bot_application

async def main():
    config = load_config()
    setup_logging(config.env.log_level)
    
    storage = StorageManager(config.app.records_file, config.env.allowed_chat_id)
    coach = AICoach(...)
    
    # Initialize PTB Application
    bot_app = create_bot_application(config, storage, coach)
    
    # Initialize Scheduler
    scheduler = NotificationScheduler(config, storage, bot_app)
    
    # Start scheduler
    scheduler.start()
    
    # Run Telegram Bot polling
    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling()
        # Keep running until cancelled
        ...
        # Shutdown cleanly
        scheduler.shutdown()
        await bot_app.updater.stop()
        await bot_app.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. End-to-End Data Flow & Lifecycle State Machine

### 5.1 Session State Machine

```
                  +--------------------------------+
                  | Scheduled Push Notification    |
                  | (status: PENDING, snooze: 0)   |
                  +--------------------------------+
                               |
         +---------------------+---------------------+
         | [✅ Đã hoàn thành]   | [⏳ Xin lùi 15 phút] | [🛑 Hôm nay nghỉ]
         v                     v                     v
+------------------+   +-------------------+   +-------------------------+
| status:          |   | status: SNOOZED   |   | Set awaiting_reason     |
| COMPLETED        |   | snooze_count: 1/2 |   | Prompt text justification|
| - Recalc streak  |   | Schedule 15m job  |   +-------------------------+
| - AI praise msg  |   +-------------------+                |
+------------------+             |                          | User sends reason text
                                 | 15 mins fires            v
                                 v             +-------------------------+
                       +-------------------+   | AI evaluates reason:    |
                       | Send 15m reminder |   | [EXCUSE] vs [LEGIT]     |
                       | Buttons active    |   +-------------------------+
                       +-------------------+                |
                                 |                          v
                   +-------------+-------------+   +-------------------------+
                   | snooze < 2  | snooze == 2 |   | status: SKIPPED         |
                   v             v             | - If EXCUSE: 2-min habit|
             Allow snooze   Enforce limit      | - If LEGIT: rest        |
             (escalates)    (Lock button)      +-------------------------+
```

### 5.2 Callback & Event Flows

#### Flow 1: [✅ Đã hoàn thành]
1. User clicks `[✅ Đã hoàn thành]`.
2. Bot receives `CallbackQuery` (`done:<session_id>`).
3. Verification: Checks `session_id` in `active_sessions`.
4. Update: `storage.mark_completed(session_id)`:
   - Updates session status to `completed`.
   - Computes streak update (`current_streak`, `last_completed_date`).
   - Writes updated data atomically to `records.json`.
5. UI Response: Edits original Telegram push message to display `✅ ĐÃ HOÀN THÀNH`.
6. AI Coach Response: Calls `coach.generate_congratulations()`. Bot sends the congratulatory message to the user.

#### Flow 2: [⏳ Xin lùi 15 phút]
1. User clicks `[⏳ Xin lùi 15 phút]`.
2. Bot receives `CallbackQuery` (`snooze:<session_id>`).
3. Verification: `storage.increment_snooze(session_id)`.
   - If `snooze_count <= 2`:
     - Schedules one-shot APScheduler job for `now + 15 minutes`.
     - Updates message inline keyboard to reflect `(1/2)` or `(2/2)`.
     - Calls `coach.generate_snooze_warning(session_name, count)`.
     - Bot replies with firm warning.
   - If `snooze_count > 2`:
     - Denies further snooze: `"⚠️ ĐÃ ĐẠT GIỚI HẠN 2 LẦN LÙI! Không thể lùi thêm. Bắt tay vào việc ngay lập tức!"`.

#### Flow 3: [🛑 Hôm nay nghỉ (Có lý do)]
1. User clicks `[🛑 Hôm nay nghỉ (Có lý do)]`.
2. Bot receives `CallbackQuery` (`skip:<session_id>`).
3. Bot calls `storage.set_awaiting_reason(session_id)`.
4. Bot sends message: `"🛑 Hãy nhập lý do bạn muốn nghỉ phiên này (lý do cụ thể):"`.
5. User sends text message (e.g. *"Em hơi mệt nên muốn lướt TikTok"* or *"Em bị sốt 39 độ phải đi viện"*).
6. Bot receives text message, detects `storage.get_awaiting_reason_session_id() == session_id`.
7. Bot sends reason to `coach.evaluate_skip_reason(session_name, detail, reason)`.
8. AI Evaluates:
   - If `[EXCUSE]`: Sarcastic breakdown, enforces 2-minute micro-habit.
   - If `[LEGITIMATE]`: Accepts skip, encourages recovery for tomorrow.
9. Storage: `storage.mark_skipped(session_id, reason, evaluation)`.
10. `storage.clear_awaiting_reason()`.
11. Bot replies with AI evaluation.

---

## 6. Containerization & Deployment Scripts Specification

### 6.1 `Dockerfile` Specification

```dockerfile
# Multi-stage or optimized single-stage Debian slim build
FROM python:3.11-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Ho_Chi_Minh

# Install tzdata for timezone accuracy and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    curl \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY . .

# Ensure data directory exists and set ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

VOLUME ["/app/data"]

CMD ["python", "-m", "src.main"]
```

### 6.2 `docker-compose.yml` Specification

```yaml
version: '3.8'

services:
  accountability-coach:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: telegram_accountability_coach
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
    environment:
      - TZ=Asia/Ho_Chi_Minh
      - PYTHONUNBUFFERED=1
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 6.3 `start.sh` (Linux / macOS)

```bash
#!/usr/bin/env bash
set -e

echo "=== Telegram Personal Accountability Coach ==="

# Check .env existence
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "👉 Please copy .env.example to .env and configure your tokens:"
    echo "   cp .env.example .env"
    exit 1
fi

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is not installed."
    exit 1
fi

# Set up virtual environment
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install / update dependencies
echo "📥 Checking and installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create data directory if not exists
mkdir -p data

echo "🚀 Starting Telegram Personal Accountability Coach..."
exec python -m src.main
```

### 6.4 `start.bat` (Windows)

```cmd
@echo off
setlocal enabledelayedexpansion

echo ==============================================
echo Telegram Personal Accountability Coach
echo ==============================================

if not exist .env (
    echo [ERROR] .env file not found!
    echo Please copy .env.example to .env and fill in your tokens:
    echo copy .env.example .env
    pause
    exit /b 1
)

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    pause
    exit /b 1
)

if not exist .venv (
    echo [INFO] Creating virtual environment (.venv)...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [INFO] Installing / updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

if not exist data (
    mkdir data
)

echo [INFO] Starting bot application...
python -m src.main
pause
```

---

## 7. Test Strategy & Mocking Contracts

To guarantee **100% test pass rate without external internet access or real tokens**:

1. **Telegram API Mocking**:
   - Mock `telegram.Bot.send_message`, `edit_message_text`, `answer_callback_query`.
   - Use `pytest-mock` or `unittest.mock.AsyncMock`.
2. **Gemini API Mocking**:
   - Mock `google.genai.Client.aio.models.generate_content`.
   - Test both success responses (containing `[EXCUSE]`, `[LEGITIMATE]`, praise) and failure paths (network error, timeout) to verify that fallback responses trigger accurately.
3. **APScheduler Mocking / Virtual Clock**:
   - Verify triggers using `pytest-asyncio` by inspecting scheduled job triggers (`CronTrigger`, `DateTrigger`).
   - Assert correct hour, minute, and timezone registration without waiting real clock time.
4. **Storage & Persistence Testing**:
   - Use `tmp_path` fixture for `records.json`.
   - Verify atomic replacement, missing directory creation, corrupt file handling, and streak boundary arithmetic across days and years.
5. **Security Authorization Testing**:
   - Pass updates with unauthorized `chat_id != ALLOWED_CHAT_ID`.
   - Assert that handlers reject/ignore and never call Gemini API or Storage write methods.

---

## 8. Summary Table of Deliverable Schemas & Files

| Component | Target Location | Key Responsibilities |
|---|---|---|
| **Environment Template** | `.env.example` | Template for `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID` |
| **Operational Config** | `config.yaml` | Schedule parameters, 7-day TOEIC syllabus, Gemini persona prompts, limits |
| **Persistence Store** | `data/records.json` | Streaks, active sessions, history logs, atomic writes |
| **Config Loader** | `src/config.py` | Typed dataclasses, schema validation, secret masking |
| **Storage Manager** | `src/storage.py` | Atomic persistence, session state machine, streak calculations |
| **AI Coach** | `src/coach.py` | Gemini 2.5 Flash, persona prompt generation, sliding window, fallbacks |
| **Scheduler** | `src/scheduler.py` | APScheduler in `Asia/Ho_Chi_Minh`, Gym, TOEIC, Major & 15m snoozes |
| **Bot UI & Handlers** | `src/bot.py` | PTB v20+, authorization filter, inline buttons, state handling |
| **Application Main** | `src/main.py` | Async runtime initialization, lifecycle orchestration, graceful shutdown |
| **Containerization** | `Dockerfile`, `docker-compose.yml` | Container runtime, volume mounting, non-root user |
| **Run Scripts** | `start.sh`, `start.bat` | One-click bootstrap scripts for Unix and Windows |
| **Test Suite** | `tests/` | 100% mocked offline automated test suite |
