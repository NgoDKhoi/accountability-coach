# Comprehensive Specification Mining Analysis: Autonomous Telegram Personal Accountability Coach

**Author:** `teamwork_preview_spec_miner` (Survey Phase)  
**Date:** 2026-10-03  
**Target System:** Autonomous Telegram Personal Accountability Coach for IT Student & Game Developer  
**Authoritative Sources:**  
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`  
- `python-telegram-bot` (v20+ async architecture)  
- `APScheduler` (AsyncIOScheduler, CronTrigger, DateTrigger, ZoneInfo)  
- `google-genai` SDK (`gemini-2.5-flash` client, prompt schema, fallback handling)  
- Atomic File I/O standards (`os.replace`, POSIX/Windows filesystem atomic semantics)  

---

## 1. Executive Summary & System Overview

The system is an autonomous, asynchronous Telegram-based accountability coach tailored for an IT student and game developer. The coach operates proactively (via scheduled push notifications) and reactively (via two-way conversation and inline button actions), backed by Google Gemini (`gemini-2.5-flash`) for behavioral coaching and lightweight atomic JSON persistence (`data/records.json`).

The core architecture operates across six primary subsystems:
1. **Telegram Core & Security (R1):** Async PTB v20 application with strict whitelist authorization (`ALLOWED_CHAT_ID`) dropping or denying unauthorized interaction.
2. **Proactive APScheduler (R2):** `Asia/Ho_Chi_Minh` timezone-aware scheduler managing Gym, TOEIC 7-day part rotation, and Major Subject preparation sessions.
3. **Interactive Inline State Machine (R3):** Three-way action triggers (`Done`, `Snooze 15m`, `Skip with Reason`), supporting 15-minute one-shot rescheduling (capped at 2 snoozes) and AI justification evaluation (excuse vs legitimate obstacle with 2-minute micro-habit enforcement).
4. **Gemini AI Accountability Coach (R4):** `google-genai` integration with a cynical, direct tech-lead/game-dev persona, strict 2–3 sentence response length, sliding context window (6–10 messages), and offline fallback resilience.
5. **Atomic JSON Persistence (R5):** Crash-safe write operations to `data/records.json` using atomic temporary file renaming and calendar-day streak accounting.
6. **Zero-Network Automated Test Suite (R6):** Complete offline test coverage with `pytest` and `pytest-asyncio` mocking Telegram, Gemini, and system clocks.

---

## 2. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Security & Authorization | Whitelist Chat ID Filter | Validates that any incoming Telegram update originates from `ALLOWED_CHAT_ID`. | `Update.effective_chat.id`, `ALLOWED_CHAT_ID` from `.env` | Allows handler execution if matched. | If mismatched: rejects with access denied notice or silently ignores; Gemini is never invoked. | ORIGINAL_REQUEST.md R1 & AC |
| 2 | Security & Authorization | Secret / Config Decoupling | Separates sensitive tokens (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`) from operational settings (`config.yaml`). | `.env` variables, `config.yaml` | Loaded configuration dictionary / dataclass. | Raises `ValueError` or logs fatal error on missing required secret at boot. | ORIGINAL_REQUEST.md R1 & AC |
| 3 | Telegram Core | Bot Lifecycle & Async Boot | Initializes PTB `Application` with async event loop, attaches handlers, binds scheduler, starts polling. | Bot token, event loop, config | Active polling bot service with clean shutdown on SIGINT/SIGTERM. | Fails boot if token is invalid or network unreachable at startup. | ORIGINAL_REQUEST.md R1 |
| 4 | Telegram Core | `/start` Command Handler | Greets authorized user, displays bot mission, status, and command list. | Telegram `/start` command from authorized user | Welcome text message explaining schedules and coach capabilities. | Unauthorized user gets access denied / ignored. | ORIGINAL_REQUEST.md R1 |
| 5 | Telegram Core | `/help` Command Handler | Displays usage guidelines, session types, and snooze/skip mechanics. | Telegram `/help` command | Formatted markdown help text. | Unauthorized user gets access denied / ignored. | ORIGINAL_REQUEST.md R1 |
| 6 | Telegram Core | `/status` / Streak Command | Reports current streak, best streak, recent check-in log, and pending sessions. | Telegram `/status` command | Formatted streak summary and status report from `data/records.json`. | If records file missing, initializes empty state and returns streak 0. | ORIGINAL_REQUEST.md R1, R5 |
| 7 | Proactive Scheduler | Timezone-Aware Scheduler Setup | Configures APScheduler `AsyncIOScheduler` strictly with timezone `Asia/Ho_Chi_Minh` (UTC+7). | `config.yaml` timezone setting (`Asia/Ho_Chi_Minh`) | Running scheduler instance aligned with local Vietnam time. | Fallbacks or logs error if timezone string is invalid in `zoneinfo`. | ORIGINAL_REQUEST.md R2 |
| 8 | Proactive Scheduler | Gym Workout Reminder (Mon, Tue, Thu) | Triggers proactive notification at 17:15 for the 17:30–18:30 gym session on Mon, Tue, Thu. | Cron trigger: `day_of_week='mon,tue,thu'`, `hour=17`, `minute=15` | Telegram message with session details and 3 inline buttons sent to `ALLOWED_CHAT_ID`. | Logs exception and retries message push if Telegram API temporary error. | ORIGINAL_REQUEST.md R2 |
| 9 | Proactive Scheduler | Gym Workout Reminder (Wed, Sat) | Triggers proactive notification at 16:15 for the 16:30–17:30 gym session on Wed, Sat. | Cron trigger: `day_of_week='wed,sat'`, `hour=16`, `minute=15` | Telegram message with session details and 3 inline buttons sent to `ALLOWED_CHAT_ID`. | Logs exception if push fails. | ORIGINAL_REQUEST.md R2 |
| 10 | Proactive Scheduler | TOEIC Study Session Trigger | Triggers proactive reminder daily at 19:25 for the 19:30–20:30 study window. | Cron trigger: `hour=19`, `minute=25` | Telegram message with day's TOEIC topic and 3 inline buttons. | Logs exception if push fails. | ORIGINAL_REQUEST.md R2 |
| 11 | Proactive Scheduler | TOEIC 7-Day Syllabus Rotation | Dynamically resolves study topic based on current day of week (Monday=Part 1, ..., Sunday=Full Mock). | Current weekday index (0–6) in `Asia/Ho_Chi_Minh`, rotation list in `config.yaml` | Resolved TOEIC topic name & description injected into reminder text. | If config is missing key, defaults to generic TOEIC review. | ORIGINAL_REQUEST.md R2 |
| 12 | Proactive Scheduler | Major Subject Study Trigger | Triggers proactive notification daily at 20:40 for study window 20:45–21:45. | Cron trigger: `hour=20`, `minute=40` | Telegram message with IT/game dev study reminder and 3 inline buttons. | Logs exception if push fails. | ORIGINAL_REQUEST.md R2 |
| 13 | Interactive State Machine | Inline Keyboard Generator | Builds interactive markup with `[✅ Đã hoàn thành]`, `[⏳ Xin lùi 15 phút]`, and `[🛑 Hôm nay nghỉ (Có lý do)]`. | Session ID, session type, current snooze count | `InlineKeyboardMarkup` with callback data strings (e.g. `act:done:<id>`, `act:snooze:<id>:<cnt>`, `act:skip:<id>`). | Renders valid Telegram markup. | ORIGINAL_REQUEST.md R3 |
| 14 | Interactive State Machine | "Done" Completion Handler | Processes `[✅ Đã hoàn thành]` click: updates streak, writes record, requests Gemini congratulation. | Callback query with `act:done:<id>` | Edited message indicating completion; celebratory 2–3 sentence AI message sent. | If Gemini fails, sends deterministic fallback congratulation. | ORIGINAL_REQUEST.md R3 |
| 15 | Interactive State Machine | "Snooze 15m" Handler | Reschedules session for +15 minutes, updates message status, tracks consecutive snooze count. | Callback query with `act:snooze:<id>:<cnt>` | One-shot job added to APScheduler at `now + 15 min`; message edited to reflect snooze state. | Rejects with warning if snooze count >= 2. | ORIGINAL_REQUEST.md R3 |
| 16 | Interactive State Machine | Snooze Cap & Escalation | Enforces hard limit of 2 snoozes per session with escalating firmness on attempts. | Snooze attempt when snooze count is 1 vs 2 | Count 1: gentle reminder + 15m job. Count 2: firm warning + 15m job. Count >2: blocked with strict warning. | Button becomes disabled or replies with "Hết lượt hoãn!". | ORIGINAL_REQUEST.md R3 |
| 17 | Interactive State Machine | Snooze Job Execution | APScheduler one-shot job fires after 15 minutes to re-alert user. | Scheduled `DateTrigger` firing in event loop | Sends follow-up push alert with updated snooze count and inline buttons. | Logs failure if send fails. | ORIGINAL_REQUEST.md R3 |
| 18 | Interactive State Machine | "Skip with Reason" Trigger | Initiates skip justification flow; sets user state awaiting chat explanation. | Callback query with `act:skip:<id>` | Prompts user in chat: "Nhập lý do bạn muốn nghỉ hôm nay:" and sets pending state. | Handles timeout or state override if user takes another action. | ORIGINAL_REQUEST.md R3 |
| 19 | Interactive State Machine | Skip Reason Evaluation Flow | Intercepts next text message from user while in awaiting-reason state; passes reason to Gemini evaluator. | Text message content, session ID, pending state | Evaluates excuse vs legitimate obstacle; updates record; sends coach response. | Clears pending state; falls back to rule-based parser if AI fails. | ORIGINAL_REQUEST.md R3 |
| 20 | Interactive State Machine | 2-Minute Micro-Habit Enforcement | If Gemini classifies skip reason as an excuse/procrastination, dismantles excuse and enforces 2-minute micro-habit. | Gemini classification = EXCUSE | Sarcastic/firm AI message giving 2-minute actionable challenge (e.g. 1 question / 5 pushups). | User remains unexcused; session kept pending or marked with micro-habit badge. | ORIGINAL_REQUEST.md R3 |
| 21 | Interactive State Machine | Legitimate Skip Approval | If Gemini classifies reason as legitimate obstacle (sickness, emergency, hard deadline), records skip. | Gemini classification = LEGITIMATE | Empathetic AI message; session marked `status="skipped"` in `data/records.json`. | Preserves streak integrity according to skip policy. | ORIGINAL_REQUEST.md R3 |
| 22 | AI Accountability Coach | `google-genai` Client Integration | Connects to Google GenAI SDK using `gemini-2.5-flash` model. | `GEMINI_API_KEY`, prompt contents, system instruction | Generated text string from Gemini model. | Catches API errors, quota limits, connection timeouts. | ORIGINAL_REQUEST.md R4 |
| 23 | AI Accountability Coach | IT & Game Dev Coach Persona | System prompt shaping AI as direct, concise senior tech lead / game developer coach. | User inputs, context history, system prompt | Output strictly limited to 2–3 sentences, tech metaphors, sarcastic to slacking, proud of discipline. | Truncates or formats if model exceeds length. | ORIGINAL_REQUEST.md R4 |
| 24 | AI Accountability Coach | Sliding Dialogue Context Window | In-memory sliding buffer retaining the most recent 6–10 messages for ongoing dialogue context. | Inbound user messages, outbound AI replies | Context list passed into Gemini `contents` / chat session. | Drops oldest message pair when window size exceeds configured limit (e.g., 10). | ORIGINAL_REQUEST.md R4 |
| 25 | AI Accountability Coach | Graceful Offline Fallback | Fallback response generator activated when Gemini API fails, times out, or quota is exhausted. | Exception raised by `google-genai` client | High-quality pre-baked coach responses matching persona; bot flow never crashes. | Error logged with level WARNING/ERROR. | ORIGINAL_REQUEST.md R4 |
| 26 | AI Accountability Coach | Reactive Free-Form Chat | Allows authorized user to chat freely with the accountability coach outside scheduled reminders. | Inbound text message when not in pending skip state | Gemini coach response maintaining persona and context window. | Unauthorized users rejected; API errors fall back gracefully. | ORIGINAL_REQUEST.md R4 |
| 27 | Atomic Persistence | Data Directory Auto-Creation | Ensures `data/` directory and `data/records.json` exist prior to read/write operations. | Filepath `data/records.json` | Creates parent directory and initializes empty valid JSON structure if absent. | Catches `OSError` / filesystem permission issues. | ORIGINAL_REQUEST.md R5 |
| 28 | Atomic Persistence | Atomic JSON File Write | Writes updated state to a temporary file in `data/` and uses `os.replace` to atomically overwrite `data/records.json`. | Serialized JSON data dict | Uncorrupted `data/records.json` guaranteed even upon sudden kill or crash. | Removes temp file if serialization or write fails before rename. | ORIGINAL_REQUEST.md R5 |
| 29 | Atomic Persistence | JSON Schema Validation | Enforces standard JSON data structure containing `streak` and `sessions` / `history`. | In-memory dict | Valid JSON schema written to disk. | Recovers or initializes defaults if corrupted. | ORIGINAL_REQUEST.md R5 |
| 30 | Atomic Persistence | Calendar Day Streak Tracking | Tracks daily streak relative to local calendar day (`Asia/Ho_Chi_Minh`), handling consecutive days vs gaps. | Session completion timestamp, current record `streak` | Updated `current_streak`, `best_streak`, `last_completed_date`. | Idempotent for multiple completions on same calendar day (does not double-count streak). | ORIGINAL_REQUEST.md R5 |
| 31 | Test Suite | Offline Telegram API Mocking | Mock fixtures for Telegram `Bot`, `Update`, `User`, `Chat`, `CallbackQuery`, and `Application`. | Simulated test events | Executed handler calls without outbound HTTP network traffic. | Asserts handler logic and state changes under zero network. | ORIGINAL_REQUEST.md R6 |
| 32 | Test Suite | Offline Gemini API Mocking | Mock fixtures simulating `google-genai` responses for done, excuse, legitimate, and chat prompts. | Simulated prompt inputs | Returns mocked model outputs (`text="Mocked congrats"`) or simulated API exceptions. | Verifies both success paths and graceful fallback logic. | ORIGINAL_REQUEST.md R6 |
| 33 | Test Suite | APScheduler Trigger Verification | Automated tests validating cron triggers, day-of-week bindings, and timezone correctness. | Scheduler instance, job configurations | Asserts next fire times and cron specifications match R2 exact schedules. | Fails if trigger minutes, hours, or weekdays mismatch. | ORIGINAL_REQUEST.md R6 |
| 34 | Test Suite | State Machine & Snooze Limit Tests | Tests asserting Done, Snooze (1, 2, and 3 attempts), and Skip reason workflows. | Synthetic callback queries and text messages | Asserts one-shot jobs scheduled, snooze counts capped, micro-habit triggered. | Fails if snooze allowed > 2 times. | ORIGINAL_REQUEST.md R6 |
| 35 | Test Suite | Atomic Persistence Integrity Tests | Tests verifying atomic file writes, crash safety, and streak calculation edge cases. | Simulated consecutive and broken day check-ins, simulated write aborts | Validates file contents, `tmp_path` integrity, streak numbers. | Asserts streak reset on gap > 1 day. | ORIGINAL_REQUEST.md R6 |
| 36 | Test Suite | Security Whitelist Tests | Tests verifying that updates from unauthorized `chat_id != ALLOWED_CHAT_ID` are dropped/denied. | Unauthorized `Update` objects | Verifies access denied response or silent drop; verifies Gemini is 0 times called. | Fails if unauthorized user receives bot service. | ORIGINAL_REQUEST.md R6 |
| 37 | Packaging & Deployment | `.env.example` Template | Sample environment file detailing required variables and placeholder values. | File template | Clear guidance for user secrets setup. | System validates presence of variables on startup. | ORIGINAL_REQUEST.md R1 & AC |
| 38 | Packaging & Deployment | `config.yaml` Configuration | Human-readable configuration for schedules, TOEIC rotation, prompts, and limits. | YAML file | Parsed configuration objects. | Schema validation catches invalid YAML or missing keys. | ORIGINAL_REQUEST.md R1 & AC |
| 39 | Packaging & Deployment | `Dockerfile` & `docker-compose.yml` | Container specification for isolated deployment with volume persistence for `data/`. | Docker build instructions | Reproducible Linux container image running python app. | Builds cleanly without external proprietary deps. | ORIGINAL_REQUEST.md R1 & AC |
| 40 | Packaging & Deployment | Single-Click Startup Scripts | `start.bat` (Windows) and `start.sh` (Linux/macOS) managing venv, requirements, and execution. | User launch | Autonomous bootstrap and execution. | Exits with error code and instructions if python is missing. | ORIGINAL_REQUEST.md R1 & AC |

---

## 3. Edge Cases & Boundary Conditions

| # | Feature | Input | Observed / Specified Behavior |
|---|---------|-------|-------------------------------|
| 1 | Whitelist Authorization | Message from unauthorized `chat_id` (e.g. 999999999 when allowed is 123456789) | Bot sends access denied message (e.g. "⛔ Quyền truy cập bị từ chối") or silently drops the update; NO Gemini call is made, NO state is changed. |
| 2 | Whitelist Authorization | CallbackQuery from unauthorized user clicking an inline button forwarded to another chat | Callback is intercepted by authorization check; alert/answer callback query sent with "Access denied" or ignored; NO action executed. |
| 3 | Whitelist Authorization | `ALLOWED_CHAT_ID` in `.env` contains whitespace, quotes, or string format | Configuration parser must strip whitespace and parse as integer (`int(os.getenv("ALLOWED_CHAT_ID").strip())`) to prevent type mismatch during `update.effective_chat.id == ALLOWED_CHAT_ID`. |
| 4 | Scheduler Timezone | Daylight Saving Time or system clock differences | Timezone is explicitly anchored to `Asia/Ho_Chi_Minh` (fixed UTC+7, no DST). Scheduler calculates job triggers based on `ZoneInfo("Asia/Ho_Chi_Minh")` regardless of host OS timezone. |
| 5 | Scheduler Triggers | Wednesday vs Monday Gym schedule triggers | On Wednesday at 16:15, only the 16:30–17:30 session triggers. On Monday at 17:15, only the 17:30–18:30 session triggers. System must not confuse the two cron specs. |
| 6 | TOEIC Syllabus Rotation | Weekday index transition across midnight (Sunday 23:59 to Monday 00:00) | Calculation uses `datetime.now(tz).weekday()` at trigger time (19:25 Vietnam time). Sunday triggers index 6 (Full Mock/Review), Monday triggers index 0 (Part 1). |
| 7 | Inline Action Double-Click | User rapidly clicks `[✅ Đã hoàn thành]` twice | Handler edits the message immediately upon first click (removing or replacing inline buttons with "✅ Đã xong lúc HH:MM"), and verifies session state in memory/database. Subsequent clicks acknowledge callback with "Đã ghi nhận rồi bro!" without double-incrementing streak. |
| 8 | Snooze Max Limit | User clicks `[⏳ Xin lùi 15 phút]` when `snooze_count` is already 2 | Bot rejects snooze, does NOT create a 3rd job, and replies firmly: "⚠️ Đã hết lượt hoãn (2/2)! Hãy bắt tay vào làm ngay bây giờ!" Inline button for snooze is disabled or removed. |
| 9 | Snooze Across Session Overlap | User snoozes Major Subject at 20:40 twice (20:55, 21:10) | Each snooze schedules a one-shot job with a unique job ID (`snooze_major_<timestamp>`). Old snooze job is cleared/replaced. |
| 10 | Skip Flow State Interruption | User clicks `[🛑 Hôm nay nghỉ]` then clicks `[✅ Đã hoàn thành]` before typing reason | Clicking `[✅ Đã hoàn thành]` clears the pending skip state for that session, marks session complete, and proceeds with Done flow. |
| 11 | Skip Flow Non-Text Input | User sends a sticker, photo, or audio voice note while bot awaits skip reason | Bot detects non-text message and responds: "Vui lòng nhập lý do bằng văn bản (text) để AI Coach thẩm định." State remains awaiting reason. |
| 12 | Skip Flow Timeout / Abandonment | User clicks `[🛑 Hôm nay nghỉ]` but never types a reason | Session remains marked as `pending` or `in_progress`. Pending state does not block future scheduled reminders or status commands. (Can expire after session window). |
| 13 | Skip Reason Evaluation | Ambiguous user reason (e.g. "Hơi mệt nhưng vẫn ráng được không?") | Prompt instructs Gemini to classify borderline lazy thoughts as EXCUSE, encouraging the 2-minute micro-habit. |
| 14 | Skip Reason Evaluation | Real emergency reason (e.g. "Bị ngộ độc thực phẩm đang ở bệnh viện") | Prompt instructs Gemini to classify as LEGITIMATE, express brief empathy, and record skip without forcing micro-habit. |
| 15 | Gemini API Outage / Quota Exceeded | `google-genai` raises `APIError`, `ResourceExhausted`, or `Timeout` | Catch block intercepts error, logs it, and returns an appropriate pre-configured fallback message from `config.yaml` matching coach persona. Bot does not crash. |
| 16 | Gemini Empty API Key | `GEMINI_API_KEY` is empty or unset in development | Bot starts in offline/mock coach mode; all AI calls gracefully return persona-compliant fallback strings without raising unhandled exceptions. |
| 17 | Sliding Context Window | User chats 20 messages in a row | Context deque retains only the latest 6–10 messages (e.g. 5 user messages + 5 AI replies). Older messages are safely evicted to prevent token bloat. |
| 18 | Atomic Persistence File Missing | `data/records.json` does not exist on initial startup | Persistence layer automatically creates `data/` directory and initializes `records.json` with `{"streak": {"current_streak": 0, "best_streak": 0, "last_completed_date": null}, "sessions": []}`. |
| 19 | Atomic Persistence Crash During Write | Process is killed (SIGKILL) while writing data | Data is written to `data/records.json.tmp` first. Original `data/records.json` remains completely untouched and valid until `os.replace` atomically commits the file. |
| 20 | Streak Accounting Multiple Sessions | User completes Gym at 18:00, then completes TOEIC at 20:00 on same day | When completing TOEIC, streak logic sees `last_completed_date == today`. Session is recorded as completed, but daily streak counter does NOT increment twice on the same day. |
| 21 | Streak Accounting Consecutive Days | User completed yesterday (`today - 1 day`), and completes today | `current_streak` increments by 1. If `current_streak > best_streak`, `best_streak` is updated. `last_completed_date = today`. |
| 22 | Streak Accounting Gap Day | User completed 2 days ago (`today - 2 days`), missed yesterday, completes today | `current_streak` resets to 1 (new streak started). `best_streak` remains unchanged. `last_completed_date = today`. |
| 23 | Streak Accounting Month/Year Boundary | Check-in on 2026-10-31 followed by 2026-11-01, or 2026-12-31 to 2027-01-01 | Streak calculation parses ISO date strings into Python `datetime.date` objects; `(date_today - last_date).days == 1` correctly evaluates consecutive days across month/year boundaries. |
| 24 | Bot Restart Persistence | Bot crashes or is restarted after user snoozed | Session status and snooze counts are persisted in `records.json`. On startup, active snooze jobs within future time can be restored or gracefully handled. |
| 25 | Message Editing Permission Error | Telegram message to edit is too old (>48 hours) or already deleted | Handlers catch `telegram.error.BadRequest` ("Message to edit not found") and fall back to sending a new reply message. |

---

## 4. Deep-Dive Specification Breakdown Across R1 – R7

### R1. Telegram Bot Core & Security Specification

#### 1.1 Architecture & Libraries
- **Framework:** `python-telegram-bot` version `>=20.0` (async/await native architecture).
- **Application Structure:**
  - `ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()`
  - Handlers registered via `application.add_handler(...)`.
  - Integration with `APScheduler` running on the same asyncio event loop.

#### 1.2 Security & Authorization Guard
- **Environment Variable:** `ALLOWED_CHAT_ID` (integer).
- **Mechanism:** Custom Handler Filter or Authorization Middleware / Decorator.
- **Contract:**
  ```python
  def authorized_only(func):
      @functools.wraps(func)
      async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
          chat_id = update.effective_chat.id if update.effective_chat else None
          if chat_id != settings.ALLOWED_CHAT_ID:
              if update.callback_query:
                  await update.callback_query.answer("⛔ Access Denied.", show_alert=True)
              elif update.effective_message:
                  await update.effective_message.reply_text("⛔ Quyền truy cập bị từ chối.")
              return
          return await func(update, context, *args, **kwargs)
      return wrapper
  ```
- **Zero Quota Leakage:** Unauthorized updates are halted immediately before invoking any Gemini API or reading private session history.

#### 1.3 Command Specifications
1. `/start`:
   - **Input:** Telegram command message `/start`.
   - **Behavior:** Verifies authorization. Sends greeting message introducing the accountability coach, stating current streak and listing commands (`/status`, `/help`).
2. `/help`:
   - **Input:** Telegram command message `/help`.
   - **Behavior:** Explains the 3 scheduled routines (Gym, TOEIC, Major Subject), the 3 inline action buttons, and how snooze/skip works.
3. `/status`:
   - **Input:** Telegram command message `/status`.
   - **Behavior:** Loads persistence data; outputs current streak, best streak, last completed date, and today's session completion summary.

---

### R2. Proactive Scheduler Specification

#### 2.1 Scheduler Engine
- **Engine:** `apscheduler.schedulers.asyncio.AsyncIOScheduler`.
- **Timezone:** `ZoneInfo("Asia/Ho_Chi_Minh")`. All cron triggers, date triggers, and time calculations must explicitly use this timezone.

#### 2.2 Routine Trigger Schedule Matrix

| Routine Name | Days of Week | Trigger Time (VN Time) | Window Range | Window Duration | Description / Content |
|--------------|--------------|------------------------|--------------|-----------------|-----------------------|
| **Gym Session** | Mon, Tue, Thu | 17:15:00 | 17:30 – 18:30 | 60 mins | Workout reminder. Focus: Physical stamina, game dev endurance. |
| **Gym Session** | Wed, Sat | 16:15:00 | 16:30 – 17:30 | 60 mins | Early workout window for midweek/weekend. |
| **TOEIC Study** | Daily (Mon–Sun)| 19:25:00 | 19:30 – 20:30 | 60 mins | Dynamic topic pulled from 7-Day rotation syllabus. |
| **Major Subject**| Daily (Mon–Sun)| 20:40:00 | 20:45 – 21:45 | 60 mins | Computer Science & Game Development preparation. |

*(Note: Friday and Sunday have no gym routine, giving scheduled physical rest).*

#### 2.3 7-Day TOEIC Rotation Syllabus
Configured in `config.yaml`:
- **Monday (Day 0):** `Part 1: Photographs` (Mô tả tranh - Luyện nghe và phản xạ từ vựng hình ảnh).
- **Tuesday (Day 1):** `Part 2: Question-Response` (Hỏi - Đáp - Phản xạ bẫy phát âm & từ để hỏi).
- **Wednesday (Day 2):** `Part 3: Short Conversations` (Hội thoại ngắn - Nắm bắt ngữ cảnh & skimming câu hỏi).
- **Thursday (Day 3):** `Part 4: Short Talks` (Bài nói ngắn - Nghe ý chính & suy luận thông tin).
- **Friday (Day 4):** `Part 5: Incomplete Sentences` (Ngữ pháp & Từ vựng - Tốc độ giải đề ngữ pháp trong 10-15s).
- **Saturday (Day 5):** `Part 6: Text Completion` (Điền đoạn văn - Liên kết câu & từ vựng theo chủ đề).
- **Sunday (Day 6):** `Part 7 & Full Mock / Review` (Đọc hiểu đoạn đơn/đoạn kép & Tổng ôn test tuần).

#### 2.4 Dynamic Reminder Message Construction
The push reminder message sent to `ALLOWED_CHAT_ID` must contain:
1. **Header:** Distinct emoji + routine tag (e.g. `🏋️‍♂️ [LỊCH TẬP GYM]`, `🎧 [LỊCH HỌC TOEIC]`, `💻 [LỊCH HỌC CHUYÊN NGÀNH]`).
2. **Time Window:** Explicit window (e.g. `17:30 – 18:30`).
3. **Focus Topic:** Dynamically inserted (e.g. `Chủ đề hôm nay: Part 2: Question-Response`).
4. **Motivational Call-To-Action:** Tailored to IT / Game Developer mindset (e.g. "Đừng để não bị throttle. Bật compiler lên và cày cuốc!").
5. **Inline Action Keyboard:** 3 buttons as specified in R3.

---

### R3. Inline Actions, Snooze, & Skip State Machine Specification

#### 3.1 Inline Action Keyboard Schema
```
Row 1: [ ✅ Đã hoàn thành ]         -> callback_data: "done:<session_id>"
Row 2: [ ⏳ Xin lùi 15 phút (0/2) ] -> callback_data: "snooze:<session_id>:0"
Row 3: [ 🛑 Hôm nay nghỉ (Có lý do) ] -> callback_data: "skip:<session_id>"
```

#### 3.2 Action Flow 1: "Done" (`[✅ Đã hoàn thành]`)
```
[User clicks "Done"]
         │
         ▼
[Check session status in persistence]
         │
         ├── Already done? ──> Answer callback "Đã ghi nhận rồi bro!" (no-op)
         │
         ▼
[Edit Message: "✅ ĐÃ HOÀN THÀNH lúc HH:MM"]
[Remove or disable inline buttons]
         │
         ▼
[Update data/records.json]
├── Status: "completed"
├── Completed_at: ISO timestamp
└── Increment Daily Streak (if first completion today)
         │
         ▼
[Invoke Gemini Coach for Congratulatory Message]
├── Prompt: "User completed <session_title>. Streak: <streak>. Praise discipline, IT/game dev theme, 2-3 sentences."
└── Send reply to user (or fallback string if AI fails)
```

#### 3.3 Action Flow 2: "Snooze 15m" (`[⏳ Xin lùi 15 phút]`)
```
[User clicks "Snooze"]
         │
         ▼
[Read current snooze_count for session]
         │
         ├── snooze_count == 0:
         │     ├── Increment count to 1
         │     ├── Update message: "⏳ Đã lùi 15 phút (Lần 1/2). Tập trung chuẩn bị đi bro!"
         │     └── Schedule APScheduler DateTrigger at now + 15 mins
         │
         ├── snooze_count == 1:
         │     ├── Increment count to 2
         │     ├── Update message: "⚠️ Đã lùi 15 phút (Lần 2/2). Đây là LẦN CUỐI CÙNG!"
         │     └── Schedule APScheduler DateTrigger at now + 15 mins
         │
         └── snooze_count >= 2:
               ├── Reject snooze request
               ├── Answer callback alert: "⛔ Đã hết 2 lượt hoãn! Không lùi nữa, bắt tay làm ngay!"
               └── Update buttons to remove snooze option
```

#### 3.4 Action Flow 3: "Skip with Reason" (`[🛑 Hôm nay nghỉ (Có lý do)]`)
```
[User clicks "Skip"]
         │
         ▼
[Set User State: AWAITING_SKIP_REASON for session_id]
[Prompt in chat: "🛑 Nhập lý do bạn muốn nghỉ hôm nay để AI Coach thẩm định:"]
         │
         ▼
[User sends Text Message]
         │
         ▼
[Clear AWAITING_SKIP_REASON state]
[Send prompt to Gemini 2.5 Flash]
├── System instruction: Evaluate if user justification is an EXCUSE or LEGITIMATE OBSTACLE.
├── Rules:
│     - EXCUSE (lười, mệt nhẹ, buồn ngủ, muốn chơi game):
│       Be sarcastic, dismantle excuse, enforce 2-minute micro-habit rule.
│       Max 2-3 sentences.
│     - LEGITIMATE (sốt, tai nạn, cấp cứu, deadline công ty đột xuất):
│       Brief empathy, approve skip, advise recovery.
│       Max 2 sentences.
         │
         ▼
[Parse Gemini Response Verdict]
         │
         ├── Verdict: EXCUSE:
         │     ├── Send AI response with micro-habit challenge
         │     └── Session remains unapproved (status: "micro_habit_pending" or "pending")
         │
         └── Verdict: LEGITIMATE:
               ├── Send AI response approving rest
               ├── Update data/records.json: status: "skipped", reason: text, verdict: "legitimate"
               └── Message updated: "🛑 ĐÃ NGHỈ (Có lý do chính đáng)"
```

---

### R4. Two-Way AI Accountability Coach (Gemini API) Specification

#### 4.1 SDK & Model Configuration
- **Library:** `google-genai` (official Google GenAI SDK).
- **Client Instantiation:**
  ```python
  from google import genai
  client = genai.Client(api_key=settings.GEMINI_API_KEY)
  ```
- **Target Model:** `gemini-2.5-flash`.

#### 4.2 System Prompt & Coach Persona Specification
- **Persona:** Senior Tech Lead & Hardcore Game Developer Accountability Coach.
- **Tone Attributes:**
  1. **Direct & Uncompromising:** Speaks plainly, no corporate fluff, treats procrastination like high-severity production bugs.
  2. **Technical & Game-Dev Mindset:** Uses analogies like memory leaks, frame drops, compiling, XP grinding, latency, state machines.
  3. **Cynical / Sarcastic to Excuses:** Pierces rationalizations quickly; calls out laziness with witty gamer/programmer banter.
  4. **Genuinely Respects Execution:** When user shows discipline, praises like a senior engineer seeing zero compiler warnings.
  5. **Length Constraint:** Strictly 2 to 3 sentences maximum per reply.

#### 4.3 Sliding Context Window Engine
- **Data Structure:** In-memory `collections.deque(maxlen=10)` or list.
- **Storage Item:** Turn tuple/dict: `{"role": "user" | "model", "parts": [content]}`.
- **Sliding Policy:**
  - Maintains up to 10 latest dialogue turns (5 user queries + 5 coach responses).
  - Automatically evicts the oldest items when capacity is reached.
  - Context is preserved across continuous conversation turns.

#### 4.4 Graceful Fallback Engine
When `google-genai` fails (network error, timeout, HTTP 429 quota exhausted, invalid key):
- **Catch Exception:** `Exception` / `genai.errors.APIError`.
- **Behavior:** Never raise unhandled exception to Telegram framework.
- **Fallback Repository (in `config.yaml`):**
  - `congrats`: "Code clean, build thành công! Giữ vững streak hôm nay bro, tuyệt đối không để technical debt tích tụ!"
  - `excuse`: "Nghe mùi ngụy biện rồi đấy. Dẹp game sang một bên, làm đúng 2 phút rồi muốn nghỉ thì nghỉ!"
  - `legitimate`: "Lý do hợp lệ. Hệ thống chấp thuận nghỉ để bảo trì phần cứng. Mau hồi phục rồi quay lại cày!"
  - `chat_default`: "Server AI đang bảo trì một chút, nhưng nguyên tắc không đổi: bớt lướt mạng, tập trung vào mục tiêu đi!"

---

### R5. Lightweight Atomic JSON Persistence Specification

#### 5.1 Storage File & Directory
- **Path:** `data/records.json` relative to project root.
- **Directory Initialization:**
  ```python
  os.makedirs("data", exist_ok=True)
  ```

#### 5.2 Atomic Write Protocol
To prevent data corruption during process interruption or concurrent operations:
1. Serialize data dict to JSON string.
2. Write string to temporary file in the same directory: `data/records.json.tmp`.
3. Flush and sync file descriptors to disk (`file.flush()`, `os.fsync(file.fileno())`).
4. Atomically rename/replace temporary file to target path using `os.replace("data/records.json.tmp", "data/records.json")`.
5. Under both POSIX and modern Windows NTFS, `os.replace` provides atomic replacement semantics if files reside on the same filesystem.

#### 5.3 Data Schema (`data/records.json`)
```json
{
  "version": 1,
  "streak": {
    "current_streak": 5,
    "best_streak": 14,
    "last_completed_date": "2026-10-03"
  },
  "sessions": [
    {
      "id": "20261003_gym_1715",
      "date": "2026-10-03",
      "session_type": "gym",
      "title": "Gym Session (17:30 - 18:30)",
      "scheduled_time": "17:15",
      "status": "completed",
      "snooze_count": 1,
      "completed_at": "2026-10-03T17:45:12+07:00",
      "skip_reason": null,
      "skip_verdict": null
    }
  ]
}
```

#### 5.4 Streak Calculation Rules
All calculations rely on calendar dates in `Asia/Ho_Chi_Minh` (`date_today = datetime.now(tz).date()`):
1. **Case 1: First Completion Ever** (`last_completed_date is None`):
   - `current_streak = 1`
   - `best_streak = 1`
   - `last_completed_date = date_today.isoformat()`
2. **Case 2: Already Completed a Session Today** (`last_completed_date == date_today.isoformat()`):
   - `current_streak` remains unchanged.
   - `best_streak` remains unchanged.
   - Session status is saved as `completed`.
3. **Case 3: Consecutive Day Completion** (`date_today - last_date == 1 day`):
   - `current_streak += 1`
   - If `current_streak > best_streak`: `best_streak = current_streak`
   - `last_completed_date = date_today.isoformat()`
4. **Case 4: Streak Broken** (`date_today - last_date > 1 day`):
   - `current_streak = 1`
   - `best_streak` remains unchanged.
   - `last_completed_date = date_today.isoformat()`

---

### R6. Automated Test Suite Specification

#### 6.1 Testing Framework
- **Tools:** `pytest`, `pytest-asyncio`.
- **Constraint:** 100% offline pass without external network calls, real Telegram bots, or real Gemini API tokens.

#### 6.2 Test Architecture & Mocking Matrix

| Test Module | Target Functionality | Mocking Strategy | Assertions |
|-------------|----------------------|------------------|------------|
| `test_security.py` | User Whitelist (`ALLOWED_CHAT_ID`) | Mock `Update` with authorized and unauthorized `effective_chat.id`. | Authorized updates invoke handlers; unauthorized updates receive access denied notice; Gemini is NEVER invoked. |
| `test_scheduler.py` | APScheduler Triggers & Timezone | Inspect registered jobs in `AsyncIOScheduler`. | Validate `Asia/Ho_Chi_Minh` timezone, job count (4 baseline jobs), cron days and hours. |
| `test_toeic.py` | 7-Day TOEIC Syllabus Rotation | Freeze or parameterize weekday 0 through 6. | Assert Monday -> Part 1, Tuesday -> Part 2, ..., Sunday -> Full Mock. |
| `test_actions.py` | Inline Buttons (Done, Snooze, Skip) | Mock `CallbackQuery` updates and state store. | Done increments streak; Snooze schedules 15m DateTrigger; Snooze caps at 2; Skip transitions to reason prompt. |
| `test_gemini.py` | AI Coach & Fallback Engine | Mock `google.genai.Client` and `models.generate_content`. | Generates 2-3 sentence replies; catches API exceptions and emits fallback text. |
| `test_persistence.py` | Atomic JSON Storage & Streaks | Use `pytest` `tmp_path` fixture for records file. | Atomicity of write via temp file; directory creation; streak calculation for consecutive, same-day, and gap days. |

---

### R7. Packaging & Deployment Files Specification

#### 7.1 Deliverable Files Inventory
1. `.env.example`:
   ```bash
   TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
   GEMINI_API_KEY="your_gemini_api_key_here"
   ALLOWED_CHAT_ID=123456789
   ```
2. `config.yaml`:
   Contains operational parameters:
   - `timezone: "Asia/Ho_Chi_Minh"`
   - `schedules`: Gym (Mon,Tue,Thu 17:15; Wed,Sat 16:15), TOEIC (Daily 19:25), Major (Daily 20:40).
   - `toeic_rotation`: 7 items (Monday through Sunday).
   - `prompts`: System persona instructions, excuse evaluation prompt, congratulation prompt.
   - `fallbacks`: Pre-configured persona messages for network/API failures.
   - `limits`: `max_snooze: 2`, `snooze_minutes: 15`, `context_window_size: 10`.
3. `requirements.txt`:
   ```text
   python-telegram-bot>=20.0
   APScheduler>=3.10.0,<4.0
   google-genai>=0.1.0
   PyYAML>=6.0
   python-dotenv>=1.0.0
   pytest>=8.0.0
   pytest-asyncio>=0.23.0
   ```
4. `Dockerfile`:
   - Base image: `python:3.11-slim` or `python:3.12-slim`.
   - Workdir: `/app`.
   - Installs requirements, copies `src/` and `config.yaml`.
   - Volumes: `/app/data` for persistent storage.
   - Non-root user for security.
5. `docker-compose.yml`:
   - Service definition mounting `.env`, `config.yaml`, and `./data:/app/data`.
   - `restart: unless-stopped`.
6. `start.bat`:
   - Windows cmd/powershell script: checks Python, creates `.venv`, installs `requirements.txt`, launches `python -m src.main`.
7. `start.sh`:
   - POSIX executable script (`chmod +x`): creates virtualenv, installs deps, executes bot with clean trap handlers.
8. `src/` modular layout:
   - `src/__init__.py`
   - `src/config.py`: Loads `.env` and `config.yaml`.
   - `src/storage.py`: Atomic JSON persistence and streak logic.
   - `src/ai_coach.py`: Gemini client, sliding context, fallback logic.
   - `src/scheduler.py`: APScheduler setup, TOEIC rotation, trigger jobs.
   - `src/bot.py`: Telegram handlers, auth guard, inline state machine.
   - `src/main.py`: Entrypoint tying together bot, scheduler, and persistence.
9. `tests/` modular layout:
   - `tests/conftest.py`: Fixtures for mock bot, mock Gemini, temp records.
   - `tests/test_security.py`
   - `tests/test_scheduler.py`
   - `tests/test_actions.py`
   - `tests/test_persistence.py`
   - `tests/test_ai_coach.py`

---

## 5. Verification & Test Strategy

To independently verify the complete specification:
1. **Verification Command:**
   ```bash
   pytest -v tests/
   ```
   All tests must execute without network calls and achieve 100% pass rate.
2. **Schema & Config Check:**
   Validate `config.yaml` against schema definition; check `.env.example` completeness.
3. **Behavioral Integrity:**
   Ensure unauthorized user receives zero unauthorized AI cycles; persistence cannot corrupt `records.json`; max snooze never exceeds 2.
