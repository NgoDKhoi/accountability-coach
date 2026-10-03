# Project: Autonomous Telegram Personal Accountability Coach

## Architecture
An asynchronous Telegram bot application for an IT student and game developer, integrating:
1. **Telegram Core (`src/bot.py`, `src/main.py`)**: Asynchronous `python-telegram-bot` (v20+) application with strict whitelist authorization filter (`ALLOWED_CHAT_ID`), interactive inline keyboards, `/start`, `/help`, `/status` commands, and chat state machine.
2. **Proactive Scheduler (`src/scheduler.py`)**: `APScheduler` (`AsyncIOScheduler`) in `Asia/Ho_Chi_Minh` (UTC+7) timezone, managing Gym workouts, 7-day TOEIC parts rotation, Major subject study, and dynamic 15-minute DateTrigger snooze jobs.
3. **AI Accountability Coach (`src/coach.py`)**: Google GenAI SDK (`gemini-2.5-flash`), IT & Game Dev Coach persona (max 2-3 sentences), sliding conversation history deque (6-10 messages), excuse vs legitimate obstacle evaluator with 2-minute micro-habit challenge, and resilient offline fallbacks.
4. **Atomic JSON Persistence (`src/storage.py`)**: Crash-safe atomic disk writes (`tempfile.NamedTemporaryFile` + `os.replace` guarded by `asyncio.Lock`), managing calendar day streaks, session statuses, snooze counts, and check-in history in `data/records.json`.
5. **Configuration & Environment (`src/config.py`)**: Strictly decoupled settings loading `.env` secrets and `config.yaml` operational parameters.
6. **Deployment & Execution**: `Dockerfile`, `docker-compose.yml`, `start.sh`, `start.bat`, `requirements.txt`.
7. **Automated Test Infrastructure (`tests/`)**: Zero-network mocked test suite via `pytest` and `pytest-asyncio` covering all unit, integration, and end-to-end tiers.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Whitelist Chat ID Filter | Validates incoming updates originate from `ALLOWED_CHAT_ID`. Rejects/ignores unauthorized users without calling Gemini. | M4 | Survey F1 |
| 2 | Secret / Config Decoupling | Separates sensitive tokens (`.env`) from operational parameters (`config.yaml`). | M1 | Survey F2 |
| 3 | Bot Lifecycle & Async Boot | Initializes PTB `Application` with async lifecycle (`post_init`, `post_shutdown`), attaching handlers and scheduler. | M4 | Survey F3 |
| 4 | `/start` Command Handler | Greets authorized user with coach mission, schedules overview, and command list. | M4 | Survey F4 |
| 5 | `/help` Command Handler | Displays usage guidelines, session types, snooze/skip mechanics. | M4 | Survey F5 |
| 6 | `/status` / Streak Command | Reports current streak, best streak, recent check-in log, and pending sessions. | M4 | Survey F6 |
| 7 | Timezone-Aware Scheduler Setup | Configures APScheduler `AsyncIOScheduler` strictly with timezone `Asia/Ho_Chi_Minh`. | M3 | Survey F7 |
| 8 | Gym Workout Reminder (Mon, Tue, Thu) | Cron trigger at 17:15 for 17:30–18:30 workout window on Mon, Tue, Thu with 3 inline buttons. | M3 | Survey F8 |
| 9 | Gym Workout Reminder (Wed, Sat) | Cron trigger at 16:15 for 16:30–17:30 workout window on Wed, Sat with 3 inline buttons. | M3 | Survey F9 |
| 10 | TOEIC Study Session Trigger | Cron trigger daily at 19:25 for 19:30–20:30 study window with 3 inline buttons. | M3 | Survey F10 |
| 11 | TOEIC 7-Day Syllabus Rotation | Dynamically resolves day's focus topic based on 7-day TOEIC parts rotation in `config.yaml`. | M3 | Survey F11 |
| 12 | Major Subject Study Trigger | Cron trigger daily at 20:40 for 20:45–21:45 study window with 3 inline buttons. | M3 | Survey F12 |
| 13 | Inline Keyboard Generator | Builds interactive markup with `[✅ Đã hoàn thành]`, `[⏳ Xin lùi 15 phút]`, and `[🛑 Hôm nay nghỉ (Có lý do)]`. | M4 | Survey F13 |
| 14 | "Done" Completion Handler | Increments daily streak, updates `data/records.json`, requests Gemini congratulation, edits message. | M4 | Survey F14 |
| 15 | "Snooze 15m" Handler | Reschedules session +15 minutes via APScheduler one-shot job, increments snooze count. | M4 | Survey F15 |
| 16 | Snooze Cap & Escalation | Enforces hard limit of 2 snoozes per session with escalating firmness warnings. | M4 | Survey F16 |
| 17 | Snooze Job Execution | APScheduler one-shot `DateTrigger` fires alert after 15 minutes with updated snooze count. | M3 | Survey F17 |
| 18 | "Skip with Reason" Trigger | Puts user in `awaiting_reason` state, prompts for justification text. | M4 | Survey F18 |
| 19 | Skip Reason Evaluation Flow | Intercepts user text, routes reason to AI coach evaluator, updates record. | M4 | Survey F19 |
| 20 | 2-Minute Micro-Habit Enforcement | If AI classifies reason as excuse/procrastination, breaks down excuse and enforces 2-minute micro-habit. | M4 | Survey F20 |
| 21 | Legitimate Skip Approval | If AI classifies reason as legitimate obstacle (sickness, emergency), approves skip and records status. | M4 | Survey F21 |
| 22 | `google-genai` Client Integration | Connects to Google GenAI SDK with model `gemini-2.5-flash`. | M2 | Survey F22 |
| 23 | IT & Game Dev Coach Persona | Direct, concise (max 2-3 sentences), slightly sarcastic toward excuses, praises genuine execution. | M2 | Survey F23 |
| 24 | Sliding Context Window | In-memory sliding buffer retaining recent 6–10 messages for ongoing context. | M2 | Survey F24 |
| 25 | Graceful Offline Fallback | Fallback responses matching persona when Gemini API fails, times out, or is offline. | M2 | Survey F25 |
| 26 | Reactive Free-Form Chat | Authorized user can chat freely with AI coach outside scheduled reminders. | M2 | Survey F26 |
| 27 | Data Directory Auto-Creation | Automatically ensures `data/` and `data/records.json` exist prior to read/write. | M1 | Survey F27 |
| 28 | Atomic JSON File Write | Uses temporary file in `data/` + flush + `os.replace` for crash-safe writes. | M1 | Survey F28 |
| 29 | JSON Schema Validation | Enforces valid structure for `streak`, `sessions`, `active_sessions`, `history`. | M1 | Survey F29 |
| 30 | Calendar Day Streak Tracking | Tracks daily streaks in `Asia/Ho_Chi_Minh` timezone, handling consecutive days vs gaps idempotently. | M1 | Survey F30 |
| 31 | Offline Telegram API Mocking | Test fixtures mocking Telegram Bot, Update, Chat, CallbackQuery, and Application. | E2E / M4 | Survey F31 |
| 32 | Offline Gemini API Mocking | Test fixtures simulating `google-genai` client for done, excuse, legitimate, and chat prompts. | E2E / M2 | Survey F32 |
| 33 | APScheduler Trigger Verification | Automated tests validating cron triggers, weekdays, and timezone correctness. | E2E / M3 | Survey F33 |
| 34 | State Machine & Snooze Limit Tests | Tests asserting Done, Snooze (1, 2, and 3 attempts), and Skip reason workflows. | E2E / M4 | Survey F34 |
| 35 | Atomic Persistence Integrity Tests | Tests verifying crash safety, temp file replace, and streak calculation edge cases. | E2E / M1 | Survey F35 |
| 36 | Security Whitelist Tests | Tests verifying that updates from unauthorized `chat_id != ALLOWED_CHAT_ID` are dropped/denied. | E2E / M4 | Survey F36 |
| 37 | `.env.example` Template | Sample environment file detailing required variables and placeholder values. | M1 | Survey F37 |
| 38 | `config.yaml` Configuration | Configuration for schedules, TOEIC 7-day syllabus rotation, prompts, and limits. | M1 | Survey F38 |
| 39 | `Dockerfile` & `docker-compose.yml` | Container specification for isolated deployment with volume mount for `data/`. | M5 | Survey F39 |
| 40 | Single-Click Startup Scripts | `start.bat` (Windows) and `start.sh` (Linux/macOS) managing venv, requirements, and execution. | M5 | Survey F40 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Design 4-tier opaque-box test suite (`TEST_INFRA.md`, Tiers 1-4, test runner) -> `TEST_READY.md` | none | DONE |
| M1 | Config, Data Models & Atomic Persistence | `.env.example`, `config.yaml`, `src/config.py`, `src/storage.py`, data models, atomic writes, streak calculation, unit tests | none | DONE |
| M2 | Gemini AI Accountability Coach | `src/coach.py`, `google-genai` client (`gemini-2.5-flash`), coach persona, sliding window, excuse evaluator, fallbacks, unit tests | M1 | DONE |
| M3 | Proactive Scheduler | `src/scheduler.py`, `APScheduler` in `Asia/Ho_Chi_Minh`, Gym triggers, TOEIC 7-day rotation, Major subject trigger, 15m snooze jobs, unit tests | M1 | IN_PROGRESS |
| M4 | Telegram Bot Core & Interactive Inline Flow | `src/bot.py`, `src/main.py`, whitelist security guard, command handlers, inline action state machine, micro-habit challenge routing, unit tests | M1, M2, M3 | PLANNED |
| M5 | Deployment Packaging & Scripts | `Dockerfile`, `docker-compose.yml`, `start.sh`, `start.bat`, `requirements.txt`, `README.md` | M1, M2, M3, M4 | PLANNED |
| M6 | Final Integration & E2E Verification | Phase 1: Pass 100% E2E test suite (Tiers 1-4). Phase 2: Tier 5 Adversarial Coverage Hardening | E2E, M1-M5 | PLANNED |

## Interface Contracts

### `src/config.py`
```python
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass(frozen=True)
class GymScheduleConfig:
    cron_days_split1: str # 'mon,tue,thu'
    time_split1: str      # '17:15'
    cron_days_split2: str # 'wed,sat'
    time_split2: str      # '16:15'
    duration_minutes: int # 60

@dataclass(frozen=True)
class ToeicScheduleConfig:
    time: str             # '19:25'
    duration_minutes: int # 60
    syllabus_rotation: List[str] # 7 parts (Mon-Sun)

@dataclass(frozen=True)
class MajorScheduleConfig:
    time: str             # '20:40'
    duration_minutes: int # 60

@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    gemini_api_key: str
    allowed_chat_id: int
    timezone: str         # 'Asia/Ho_Chi_Minh'
    max_snoozes: int      # 2
    snooze_minutes: int   # 15
    context_window_size: int # 10
    gym: GymScheduleConfig
    toeic: ToeicScheduleConfig
    major: MajorScheduleConfig
    prompts: Dict[str, str]
    fallbacks: Dict[str, str]

def load_config(config_path: str = "config.yaml", env_path: str = ".env") -> AppConfig: ...
```

### `src/storage.py`
```python
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

@dataclass
class StreakData:
    current_streak: int
    best_streak: int
    last_completed_date: Optional[str] # YYYY-MM-DD
    total_completions: int

class AtomicJsonStore:
    def __init__(self, file_path: str = "data/records.json"): ...
    async def load_data(self) -> Dict[str, Any]: ...
    async def save_data(self, data: Dict[str, Any]) -> None: ...
    async def get_streak(self) -> StreakData: ...
    async def record_completion(self, session_id: str, session_type: str, today_str: str) -> StreakData: ...
    async def record_snooze(self, session_id: str, new_count: int) -> int: ...
    async def record_skip(self, session_id: str, reason: str, classification: str, timestamp_str: str) -> None: ...
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]: ...
```

### `src/coach.py`
```python
from typing import Optional, Tuple

class AICoachService:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash", config: Optional[dict] = None, client: Optional[Any] = None): ...
    async def get_congratulation(self, session_type: str, streak: int) -> str: ...
    async def evaluate_skip_reason(self, session_type: str, reason: str) -> Tuple[str, str]: ...
    # returns: (classification: 'EXCUSE' | 'LEGITIMATE', response_text: str)
    async def chat(self, user_message: str) -> str: ...
    def clear_context(self) -> None: ...
```

### `src/scheduler.py`
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Callable, Coroutine, Any

class SchedulerService:
    def __init__(self, timezone_str: str = "Asia/Ho_Chi_Minh"): ...
    def register_scheduled_jobs(self, config: Any, trigger_callback: Callable[[str, str], Coroutine[Any, Any, None]]) -> None: ...
    def schedule_snooze_job(self, session_id: str, session_type: str, snooze_count: int, delay_minutes: int, callback: Callable[[str, str, int], Coroutine[Any, Any, None]]) -> str: ...
    def cancel_job(self, job_id: str) -> bool: ...
    def start(self) -> None: ...
    def shutdown(self) -> None: ...
```

### `src/bot.py`
```python
from telegram.ext import Application
from typing import Any

def build_application(config: Any, storage: Any, coach: Any, scheduler: Any) -> Application: ...
```

## Code Layout
```
serene-bohr/
├── .env.example
├── config.yaml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── start.sh
├── start.bat
├── README.md
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── storage.py
│   ├── coach.py
│   ├── scheduler.py
│   └── bot.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_storage.py
│   ├── test_coach.py
│   ├── test_scheduler.py
│   ├── test_bot.py
│   ├── test_e2e_tier1_features.py
│   ├── test_e2e_tier2_boundaries.py
│   ├── test_e2e_tier3_pairwise.py
│   └── test_e2e_tier4_scenarios.py
└── data/
    └── records.json
```
