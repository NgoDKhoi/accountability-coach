# Milestone 1: Configuration & Environment Technical Analysis Report

**Agent:** `teamwork_preview_explorer` (Milestone 1 - Explorer 1)  
**Target:** Autonomous Telegram Personal Accountability Coach (`serene-bohr`)  
**Scope:** `src/config.py`, `config.yaml`, `.env.example`, `requirements.txt`, Schema Dataclasses, Validation Rules & Fallbacks  
**Date:** 2026-10-03  
**Status:** Complete Architectural Specification  

---

## 1. Executive Summary & Role in System Architecture

Milestone 1 lays the foundational layer for the Autonomous Telegram Personal Accountability Coach. Before any scheduler jobs can be registered (`APScheduler`), before any AI prompts can be evaluated (`google-genai`), and before any Telegram bot events can be guarded (`python-telegram-bot`), the application requires an infallible, strictly decoupled configuration engine.

The configuration subsystem satisfies two primary design tenets:
1. **Strict Decoupling of Secrets vs. Operational Parameters:**
   - **Secrets (`.env`)**: Sensitive authentication credentials (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`) and security whitelist identifiers (`ALLOWED_CHAT_ID`) are sourced strictly from environment variables.
   - **Operational Parameters (`config.yaml`)**: Routine schedules (Gym, TOEIC, Major Study), syllabus rotation tables, system prompts, limits, and fallback messages reside in human-editable YAML.
2. **Fail-Fast Type & Integrity Validation:**
   - Application boot halts immediately with clear, descriptive exceptions if mandatory credentials are missing or malformed (e.g., non-numeric `ALLOWED_CHAT_ID`, non-existent timezones, invalid 24-hour time formats).
   - If optional operational parameters or prompt templates are omitted, sensible default fallbacks are automatically populated to prevent downstream `KeyError` or `AttributeError` exceptions.

```
                    +-----------------------------+
                    |  Environment (.env file)    |
                    |  - TELEGRAM_BOT_TOKEN       |
                    |  - GEMINI_API_KEY           |
                    |  - ALLOWED_CHAT_ID (int)    |
                    +-----------------------------+
                                   |
                                   v
+------------------------+   +-------------------+   +----------------------------+
| config.yaml            |-->|   src/config.py   |<--| Default Templates / Tables |
| - Timezone             |   |   `load_config()` |   | - Default Prompts          |
| - Gym / TOEIC / Major  |   +-------------------+   | - Default Fallbacks        |
| - Prompts & Fallbacks  |             |             | - Default TOEIC Rotation   |
+------------------------+             |             +----------------------------+
                                       v
                             +-------------------+
                             |  AppConfig (Obj)  |
                             +-------------------+
                               /       |       \
                              /        |        \
                             v         v         v
                      Scheduler    AI Coach    Bot Security & Handlers
                      (M3)         (M2)        (M4)
```

---

## 2. Requirements & Dependencies Analysis (`requirements.txt`)

The project environment is standardized on Python 3.12+ (compatible with host Python 3.14.4 on Windows). The dependency graph is intentionally lean to ensure fast container builds and minimal supply chain risk:

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

### Dependency Justifications:
- **`python-telegram-bot>=20.8,<22.0`**: Modern, fully asynchronous Telegram Bot framework. Supports `ApplicationBuilder`, custom filters for whitelist chat verification, inline keyboard markup, and callback query handlers.
- **`APScheduler>=3.10.4,<4.0.0`**: Async scheduler (`AsyncIOScheduler`) capable of running both recurrent cron jobs (`CronTrigger`) and dynamic one-shot snooze notifications (`DateTrigger`) on the main `asyncio` event loop.
- **`google-genai>=1.0.0`**: The official, authoritative Google GenAI SDK specifically mandated by Requirement R4 for interacting with `gemini-2.5-flash`.
- **`PyYAML>=6.0.1`**: Industry-standard YAML parser for parsing `config.yaml` using safe loader primitives (`yaml.safe_load`).
- **`python-dotenv>=1.0.1`**: Enables local development by parsing `.env` files into environment variables without overwriting already established system/container environment variables.
- **`tzdata>=2024.1`**: Windows NT lacks a native POSIX timezone database. `tzdata` ensures that Python's standard `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` resolves reliably across both Windows development machines and Linux container runtimes.
- **`pytest>=8.0.0` & `pytest-asyncio>=0.23.5`**: Standard asynchronous testing harness required for 100% offline unit, integration, and E2E verification.

---

## 3. Secrets & Environment Specification (`.env.example`)

A checked-in template `.env.example` provides explicit instructions for the operator. The live `.env` is ignored by `.gitignore`.

### 3.1 Content of `.env.example`
```env
# =================================================================
# Autonomous Telegram Personal Accountability Coach
# Environment Variables & Secrets Template (.env.example)
# =================================================================
# INSTRUCTIONS:
# Copy this file to '.env' and populate with your credentials:
#   cp .env.example .env (Linux/macOS) or copy .env.example .env (Windows)
# DO NOT commit the resulting '.env' file containing real tokens.
# =================================================================

# 1. Telegram Bot API Token obtained from @BotFather
# Example: 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# 2. Google Gemini API Key from Google AI Studio (https://aistudio.google.com/)
# Used for gemini-2.5-flash AI Coach persona and evaluation
GEMINI_API_KEY=your_gemini_api_key_here

# 3. Authorized Telegram Chat ID (Strict authorization: integer only)
# Only this chat ID can execute commands or receive schedules.
# Find your Chat ID by messaging @userinfobot on Telegram.
ALLOWED_CHAT_ID=123456789

# Optional Application Overrides (uncomment to override defaults):
# CONFIG_PATH=config.yaml
# LOG_LEVEL=INFO
# DATA_DIR=data
# RECORDS_FILE=data/records.json
```

### 3.2 Secrets Validation Rules
| Variable | Expected Type | Requirement | Validation Rules | Action on Failure |
|---|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `str` | Mandatory | Non-empty string after stripping whitespace. Must not be placeholder text. | Raise `ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")` |
| `GEMINI_API_KEY` | `str` | Mandatory | Non-empty string after stripping whitespace. Must not be placeholder text. | Raise `ValueError("Missing required environment variable: GEMINI_API_KEY")` |
| `ALLOWED_CHAT_ID` | `int` | Mandatory | Must parse cleanly as an integer via `int(raw.strip())`. Must not equal `0`. Can be positive (user) or negative (group/supergroup). | Raise `ValueError("ALLOWED_CHAT_ID must be a valid integer, got '...'")` or `ValueError("ALLOWED_CHAT_ID cannot be zero")` |
| `CONFIG_PATH` | `str` | Optional | If set, points to the YAML config file; defaults to `config.yaml`. | If target does not exist, raise `FileNotFoundError` |
| `LOG_LEVEL` | `str` | Optional | `DEBUG`, `INFO`, `WARNING`, `ERROR`. Defaults to `INFO`. | Fallback to `INFO` |

---

## 4. Operational Configuration Specification (`config.yaml`)

`config.yaml` contains all parameters that govern business logic without containing any secrets:

### 4.1 Complete `config.yaml` Blueprint
```yaml
# =================================================================
# Autonomous Telegram Personal Accountability Coach
# Operational Configuration (config.yaml)
# =================================================================

app:
  timezone: "Asia/Ho_Chi_Minh"
  history_limit: 10
  data_dir: "data"
  records_file: "data/records.json"

limits:
  max_snoozes: 2
  snooze_duration_minutes: 15
  micro_habit_duration_minutes: 2

schedules:
  gym:
    name: "Gym Session"
    cron_days_split1: "mon,tue,thu"
    time_split1: "17:15"
    window_split1: "17:30 – 18:30"
    cron_days_split2: "wed,sat"
    time_split2: "16:15"
    window_split2: "16:30 – 17:30"
    duration_minutes: 60
    message_template: "🏋️‍♂️ *GIỜ TẬP GYM ĐÃ ĐẾN!*\nKhung giờ tập: `{window}`\nChuẩn bị đồ tập, nạp năng lượng và rời bàn làm việc ngay nào!"

  toeic:
    name: "TOEIC Study Session"
    time: "19:25"
    window: "19:30 – 20:30"
    duration_minutes: 60
    message_template: "📚 *GIỜ HỌC TOEIC!*\nChủ đề hôm nay: *{topic}*\nKhung giờ học: `{window}`\nBật Pomodoro 25/5 và tập trung cao độ, không lướt mạng xã hội!"
    syllabus_rotation:
      - "Part 1 - Photographs (Mô tả hình ảnh)"
      - "Part 2 - Question-Response (Hỏi & Đáp)"
      - "Part 3 - Short Conversations (Đối thoại ngắn)"
      - "Part 4 - Short Talks (Bài nói ngắn)"
      - "Part 5 - Incomplete Sentences (Ngữ pháp & Từ vựng)"
      - "Part 6 - Text Completion (Điền đoạn văn)"
      - "Part 7 - Reading Comprehension & Full Mock Review"

  major:
    name: "Major Subject Study & Game Dev"
    time: "20:40"
    window: "20:45 – 21:45"
    duration_minutes: 60
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

## 5. Implementation Architecture (`src/config.py`)

### 5.1 Strict Adherence to Interface Contract
In accordance with `orchestrator/PROJECT.md` (lines 70–110), the interface contract requires:
- `GymScheduleConfig`
- `ToeicScheduleConfig`
- `MajorScheduleConfig`
- `AppConfig`
- `load_config(config_path: str = "config.yaml", env_path: str = ".env") -> AppConfig`

All 12 primary attributes on `AppConfig` match positional and keyword contracts exactly:
1. `bot_token: str`
2. `gemini_api_key: str`
3. `allowed_chat_id: int`
4. `timezone: str`
5. `max_snoozes: int`
6. `snooze_minutes: int`
7. `context_window_size: int`
8. `gym: GymScheduleConfig`
9. `toeic: ToeicScheduleConfig`
10. `major: MajorScheduleConfig`
11. `prompts: Dict[str, str]`
12. `fallbacks: Dict[str, str]`

Furthermore, additional attributes with defaults (`gemini_model`, `data_dir`, `records_file`, `micro_habit_duration_minutes`, `system_prompt`) and helper properties (`hour_split1`, `get_part_for_weekday`, `mask_secret`) are added, ensuring zero friction across downstream callers.

### 5.2 Complete Source Code Implementation
The complete recommended implementation has been authored at:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_1/proposed_config.py`

Key technical mechanisms in `load_config`:
1. **Idempotent Env Loading (`override=False`)**:
   `load_dotenv(dotenv_path=env_path, override=False)` respects environment variables already provided by the runtime (such as pytest `monkeypatch.setenv` or Docker container environments). If `env_path` file is missing, execution smoothly proceeds checking `os.environ` without crashing.
2. **Strict Integer Chat ID Parsing**:
   Strips whitespace from `ALLOWED_CHAT_ID`, parses with `int()`, checks for non-zero condition, and guarantees a pure typed `int` output.
3. **Timezone Validation with ZoneInfo**:
   Validates `ZoneInfo(timezone_str)` directly against IANA database, catching `ZoneInfoNotFoundError` immediately.
4. **Time String Validation**:
   Validates all cron split times (`HH:MM`) against regex `^(\d{1,2}):(\d{2})$` and verifies `0 <= hour <= 23` and `0 <= minute <= 59`.
5. **Flexible TOEIC Syllabus Parser**:
   Accepts syllabus rotations formatted as either a standard list of 7 items or a weekday dictionary (`mon`, `tue`, ..., `sun` or `0`..`6`). Guarantees an exact 7-item `List[str]`.
6. **Graceful Prompt/Fallback Merging**:
   Deep merges user YAML definitions with embedded `DEFAULT_PROMPTS` and `DEFAULT_FALLBACKS`. Even if a user deletes half of `config.yaml`, the bot continues functioning without unhandled `KeyError` crashes.

---

## 6. Integration Boundaries with Other Modules

| Downstream Module | Integration Point in `AppConfig` | Usage Rationale |
|---|---|---|
| **`src/storage.py` (M1)** | `config.allowed_chat_id`, `config.data_dir`, `config.records_file`, `config.timezone` | Initializes `AtomicJsonStore` targeting `data/records.json`, sets schema `user_id`, and calculates day streaks using `Asia/Ho_Chi_Minh`. |
| **`src/coach.py` (M2)** | `config.gemini_api_key`, `config.gemini_model`, `config.system_prompt`, `config.context_window_size`, `config.prompts`, `config.fallbacks` | Instantiates `google-genai` client, configures system persona, deque sliding window capacity (10), prompt formatting, and offline fallbacks. |
| **`src/scheduler.py` (M3)** | `config.timezone`, `config.gym`, `config.toeic`, `config.major`, `config.max_snoozes`, `config.snooze_minutes` | Configures `AsyncIOScheduler(timezone=ZoneInfo(cfg.timezone))`, registers CronTriggers for splits, resolves TOEIC day topic, and sets dynamic 15-minute DateTrigger jobs. |
| **`src/bot.py` / `main.py` (M4)** | `config.bot_token`, `config.allowed_chat_id` | Initializes `ApplicationBuilder().token(cfg.bot_token)` and decorates handlers with strict `@authorized_only(cfg.allowed_chat_id)` filter. |

---

## 7. Edge Cases & Verification Coverage

The following edge case matrix has been designed and implemented in `proposed_test_config.py` for testing verification:

| # | Edge Case / Scenario | Input Condition | Expected Behavior |
|---|---|---|---|
| 1 | Normal Boot | Valid `.env` and `config.yaml` | `load_config()` returns typed `AppConfig` with all attributes populated. |
| 2 | Missing `TELEGRAM_BOT_TOKEN` | Token omitted in env | Raises `ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")`. |
| 3 | Whitespace `TELEGRAM_BOT_TOKEN` | Token is `"   "` | Raises `ValueError`. |
| 4 | Missing `GEMINI_API_KEY` | Key omitted in env | Raises `ValueError("Missing required environment variable: GEMINI_API_KEY")`. |
| 5 | Missing `ALLOWED_CHAT_ID` | Variable omitted in env | Raises `ValueError("Missing required environment variable: ALLOWED_CHAT_ID")`. |
| 6 | Non-numeric `ALLOWED_CHAT_ID` | `ALLOWED_CHAT_ID="not_a_number"` | Raises `ValueError("ALLOWED_CHAT_ID must be a valid integer...")`. |
| 7 | Zero `ALLOWED_CHAT_ID` | `ALLOWED_CHAT_ID="0"` | Raises `ValueError("ALLOWED_CHAT_ID cannot be zero")`. |
| 8 | Padded `ALLOWED_CHAT_ID` | `ALLOWED_CHAT_ID="  123456789  "` | Successfully strips and parses to `123456789` (int). |
| 9 | Negative `ALLOWED_CHAT_ID` | `ALLOWED_CHAT_ID="-100123456789"` | Successfully parses to `-100123456789` (int). |
| 10 | Missing `config.yaml` | File does not exist | Raises `FileNotFoundError`. |
| 11 | Malformed YAML Syntax | Syntax error in YAML | Raises `ValueError("Failed to parse YAML configuration...")`. |
| 12 | Invalid Timezone String | `app.timezone: "Fake/City"` | Raises `ValueError("Invalid timezone...")`. |
| 13 | Invalid Time Format | `time_split1: "25:61"` | Raises `ValueError("Invalid time value...")`. |
| 14 | TOEIC Rotation as Dict | `{mon: "P1", tue: "P2", ...}` | Converts smoothly to 7-element `List[str]`. |
| 15 | TOEIC Rotation Invalid Size | Less than or greater than 7 items | Raises `ValueError("TOEIC syllabus rotation must contain exactly 7 items...")`. |
| 16 | Missing Prompts in YAML | Omitted `prompts` section | Defaults from `DEFAULT_PROMPTS` seamlessly populated. |
| 17 | Missing Fallbacks in YAML | Omitted `fallbacks` section | Defaults from `DEFAULT_FALLBACKS` seamlessly populated. |
| 18 | Mask Secret Utility | `mask_secret("1234567890abcdef")` | Returns `"1234...cdef"` without exposing complete token. |

---

## 8. Artifact Index in Explorer Directory

All artifacts required for Milestone 1 builder execution are available in `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_1/`:
- `proposed_config.py` — Complete drop-in code for `src/config.py`.
- `proposed_config.yaml` — Complete drop-in configuration for project root `config.yaml`.
- `proposed_env.example` — Complete template for project root `.env.example`.
- `proposed_requirements.txt` — Complete dependency manifest for project root `requirements.txt`.
- `proposed_test_config.py` — Complete unit test suite ready for `tests/test_config.py`.
- `handoff.md` — 5-component handoff report.
- `progress.md` — Liveness heartbeat and milestone record.
