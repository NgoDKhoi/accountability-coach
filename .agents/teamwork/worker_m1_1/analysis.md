# Milestone 1: Config, Data Models & Atomic Persistence - Implementation Analysis

**Author:** teamwork_preview_worker (worker_m1_1)  
**Date:** 2026-10-03  
**Working Directory:** `.agents/teamwork/worker_m1_1/`  
**Milestone:** Milestone 1 (Config, Data Models & Atomic Persistence)  
**Status:** IMPLEMENTED & 100% VERIFIED  

---

## 1. Executive Summary

Milestone 1 implements the foundational configuration, data modeling, and crash-safe persistence layer for the Autonomous Telegram Personal Accountability Coach (`serene-bohr`).

The subsystem guarantees:
1. **Decoupled Configuration Engine (`src/config.py`, `config.yaml`, `.env.example`)**:
   - Isolates sensitive secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`) in environment variables / `.env`.
   - Structures operational parameters (schedules, TOEIC 7-day rotation, Major subject study, system prompts, offline fallbacks) in human-editable YAML (`config.yaml`).
   - Validates environment variables with fail-fast type checking, whitespace stripping, and zero-check for `ALLOWED_CHAT_ID`.
   - Validates time formats (`HH:MM` in 24-hour range `00:00 - 23:59`), IANA timezones via Python standard `zoneinfo.ZoneInfo`, and enforces an exact 7-part rotation for TOEIC.
2. **Crash-Safe Atomic Persistence Layer (`src/storage.py`)**:
   - Implements `AtomicJsonStore` targeting `data/records.json`.
   - Uses temporary file staging (`NamedTemporaryFile` in `data/` directory), file flush, OS fsync, and **explicit file handle closure before `os.replace`** to guarantee 100% compatibility with Windows NTFS file locking without `PermissionError [WinError 32]`.
   - Coordinates concurrent asynchronous access using `asyncio.Lock` and delegates blocking filesystem I/O to worker threads via `asyncio.to_thread`.
   - Merges concurrent session updates to guarantee zero lost updates under parallel operations.
   - Computes daily check-in streaks against the `Asia/Ho_Chi_Minh` (UTC+7) calendar day boundary, supporting initial completion, consecutive progression (+1), broken streak gap resets to 1 (while preserving `best_streak`), same-day multi-session idempotency, and duplicate session completion deduplication.
   - Provides session state tracking (`pending`, `completed`, `snoozed`, `skipped`, `awaiting_reason`), snooze counting, and skip rationale tracking with AI classification (`EXCUSE` vs `LEGITIMATE`).
3. **Comprehensive Zero-Network Test Suite (`tests/`)**:
   - 77 unit tests covering positive execution, boundary values, error conditions, and concurrency scenarios with 100% pass rate.

---

## 2. File Ownership & Deliverables

| File | Purpose | Key Attributes / APIs |
|---|---|---|
| `requirements.txt` | Complete dependency manifest | PTB v20+, APScheduler v3.10+, google-genai, PyYAML, python-dotenv, tzdata, pytest, pytest-asyncio |
| `.env.example` | Operator template for secrets | Comments & placeholders for `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID` |
| `config.yaml` | Operational parameters & prompts | Gym splits (17:15 & 16:15), TOEIC (19:25 with 7-part rotation), Major (20:40), prompts & offline fallbacks |
| `src/__init__.py` | Package marker | Initializes `src` package |
| `src/config.py` | Configuration engine & dataclasses | `load_config()`, `AppConfig`, `GymScheduleConfig`, `ToeicScheduleConfig`, `MajorScheduleConfig`, `mask_secret()` |
| `src/storage.py` | Atomic persistence & streak engine | `AtomicJsonStore`, `StreakData`, `SessionRecord`, `SessionStatus` |
| `tests/__init__.py` | Test package marker | Initializes `tests` package |
| `tests/conftest.py` | Shared pytest fixtures | `clean_env`, `valid_env_dict`, `valid_yaml_dict`, `temp_env_file`, `temp_config_yaml_file`, `atomic_store` |
| `tests/test_config.py` | Configuration test suite | 44 tests covering valid loading, immutability, env validation, YAML syntax, time validation, timezone, limits |
| `tests/test_storage.py` | Storage test suite | 33 tests covering directory auto-creation, atomic writes, crash safety, concurrency, streaks, sessions, recovery |

---

## 3. Technical Implementation Details

### 3.1 Strict Configuration Decoupling (`src/config.py`)
- **Immutable Typed Dataclasses**:
  `AppConfig`, `GymScheduleConfig`, `ToeicScheduleConfig`, and `MajorScheduleConfig` are marked `frozen=True`. Any attempt to mutate configuration attributes at runtime raises `FrozenInstanceError`.
- **Secrets Parsing & Validation**:
  - `TELEGRAM_BOT_TOKEN`: Must be non-empty string.
  - `GEMINI_API_KEY`: Must be non-empty string.
  - `ALLOWED_CHAT_ID`: Strips leading/trailing whitespace (`.strip()`), parses as signed integer (`int(...)`). Rejects strings with non-digits or zero (`0`). Supports negative group/supergroup IDs.
- **Time Format & Timezone Checking**:
  - `validate_time_format`: Regex `^(\d{2}):(\d{2})$` enforces two-digit 24-hour notation. Rejects invalid hours (>23), minutes (>59), single-digit hours (`9:00`), and formats with seconds (`17:15:00`).
  - `ZoneInfo`: Validates timezone string against IANA database, raising `ValueError` on unknown timezones.
- **TOEIC Syllabus Rotation**:
  - Supports rotations passed as a 7-element `list` or a `dict` keyed by weekday names (`mon`..`sun`).
  - Validates that the syllabus contains exactly 7 items.
- **Graceful Prompt & Fallback Resolution**:
  - Supports prompts defined either at the YAML top level or nested under `ai_coach`.
  - Automatically merges user definitions with embedded default templates (`DEFAULT_PROMPTS`, `DEFAULT_FALLBACKS`), preventing `KeyError` exceptions if optional prompt entries are omitted.

### 3.2 Crash-Safe Atomic Persistence (`src/storage.py`)
- **Windows NTFS Atomic Write Protocol**:
  On Windows NTFS, open file handles block atomic file replacement (`WinError 32`). The atomic write protocol strictly executes:
  1. `NamedTemporaryFile(..., dir=self.dir_name, delete=False)` inside `data/` to avoid cross-volume links (`EXDEV`).
  2. Write JSON via `json.dump(data, temp_file, indent=2, ensure_ascii=False)`.
  3. `temp_file.flush()`.
  4. `os.fsync(temp_file.fileno())` to ensure physical disk write.
  5. `temp_file.close()` to release the OS handle lock.
  6. `os.replace(temp_path, self.file_path)` to perform an atomic swap.
  7. On any exception, unlinks `temp_path` via `os.remove` to ensure zero stray files.
- **Concurrency & Event Loop Protection**:
  - Internal `asyncio.Lock()` serializes all write operations.
  - Blocking filesystem operations run in worker threads via `asyncio.to_thread(self._sync_read)` and `asyncio.to_thread(self._sync_write, data)`.
  - `save_data(data)` automatically merges concurrent session records into the persisted state under the lock, eliminating race conditions during parallel updates.
- **Calendar Day Streak Accounting (`Asia/Ho_Chi_Minh`)**:
  - Calendar dates are evaluated as `date.fromisoformat(today_str)`.
  - $\Delta = D_{today} - D_{last}$:
    - First check-in: `current_streak = 1`, `best_streak = 1`, `total_completions = 1`.
    - Same-day completion ($\Delta = 0$): `current_streak` remains unchanged; `total_completions` increments (or stays same if duplicate `session_id`).
    - Consecutive day ($\Delta = 1$): `current_streak += 1`, `best_streak = max(best_streak, current_streak)`, `total_completions += 1`.
    - Gap day ($\Delta > 1$): `current_streak = 1`, `best_streak` preserved, `total_completions += 1`.
    - Out-of-order past completion ($\Delta < 0$): `current_streak` unchanged, `total_completions += 1`.
  - Duplicate completion for identical `session_id`: Idempotent no-op.
  - `get_effective_streak(today_str)`: Dynamically checks elapsed days without mutating records, returning `0` if more than 1 calendar day has lapsed.

---

## 4. Test Verification Summary

The test suite was executed via `pytest`:

```powershell
python -m pytest tests/test_config.py tests/test_storage.py -v
```

**Results:**
- Total Collected Tests: 77
- Passed: 77 (100%)
- Failed: 0
- Skipped: 0
- Execution Time: 1.80s

**Categories Verified:**
- Configuration loading, secret isolation, frozen immutability: 4 tests
- Environment variable validation (whitespace, negative IDs, invalid types, empty/missing variables): 15 tests
- YAML schema parsing (missing files, syntax errors, empty files, missing sections, 7-part rotation, time formats, timezone, numeric limits): 23 tests
- Helper functions and properties: 2 tests
- Directory auto-creation and empty database initialization: 3 tests
- Atomic file writing, cleanup of temporary files, crash safety on serialization error, crash safety on OS replace failure, concurrent async writes: 5 tests
- Calendar streak arithmetic (first completion, consecutive progression, same-day multi-session idempotency, duplicate completion deduplication, broken streak gap resets, large gap resets, new best records, month boundaries, year boundaries, leap year boundaries, effective streak expiry): 12 tests
- Session lifecycle tracking (unknown status, completion persistence, snooze counting, snooze-then-complete, skip excuse, skip legitimate, skip streak non-increment, multiple independent sessions, awaiting reason state machine, recent history retrieval): 10 tests
- Storage corruption recovery (empty file auto-recovery, malformed JSON recovery with backup creation, database reset, out-of-order date handling): 4 tests

---

## 5. Architectural Alignment with Downstream Milestones

- **Milestone 2 (AI Accountability Coach - `src/coach.py`)**: Can directly consume `config.gemini_api_key`, `config.gemini_model`, `config.system_prompt`, `config.prompts`, `config.fallbacks`, and `config.context_window_size`.
- **Milestone 3 (Proactive Scheduler - `src/scheduler.py`)**: Can directly consume `config.timezone`, `config.gym`, `config.toeic`, `config.major`, and schedule 15-minute DateTrigger snooze jobs using `config.snooze_minutes`.
- **Milestone 4 (Telegram Bot Core - `src/bot.py`, `src/main.py`)**: Can directly enforce whitelist filtering using `config.allowed_chat_id`, initialize PTB with `config.bot_token`, and persist user actions using `AtomicJsonStore`.
