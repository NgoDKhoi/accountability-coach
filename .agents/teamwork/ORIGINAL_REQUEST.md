# Original User Request

## 2026-10-03T09:22:18Z

An autonomous Telegram personal accountability coach for an IT student and game developer, featuring proactive scheduled reminders, two-way interactive AI coaching via Gemini, Telegram inline action buttons, and lightweight local persistence.

Working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr
Integrity mode: development

## Requirements

### R1. Telegram Bot Core & Security
- Implement an asynchronous Telegram bot using `python-telegram-bot` (v20+).
- Enforce strict user authorization: only respond to and accept commands from the user matching `ALLOWED_CHAT_ID` configured via `.env`. Any messages or callbacks from unknown chat IDs must be ignored or rejected to protect Gemini API quotas and private schedules.
- Provide clear setup instructions, environment template (`.env.example`), configuration file (`config.yaml`), containerization (`Dockerfile`, `docker-compose.yml`), and single-click startup scripts (`start.bat` for Windows and `start.sh` for Linux/macOS).

### R2. Proactive Scheduler (Push Notifications)
- Integrate an async scheduler using `APScheduler` (`AsyncIOScheduler`) configured for the `Asia/Ho_Chi_Minh` timezone.
- Schedules must be driven by `config.yaml` with the following baseline jobs:
  1. **Gym Session (1 hour):**
     - Monday, Tuesday, Thursday at 17:15 (for workout window 17:30 – 18:30).
     - Wednesday, Saturday at 16:15 (for workout window 16:30 – 17:30).
  2. **TOEIC Study Session (1 hour):**
     - Daily at 19:25 (for study window 19:30 – 20:30), dynamically pulling the day's focus topic based on a 7-day TOEIC parts rotation defined in `config.yaml` (e.g. Mon: Part 1, Tue: Part 2, ..., Sun: Full Mock/Review).
  3. **Major Subject Study & Preparation (1 hour):**
     - Daily at 20:40 (for study window 20:45 – 21:45).
- Each proactive reminder must be pushed directly to `ALLOWED_CHAT_ID` with inline keyboard buttons.

### R3. Inline Actions, Snooze, & Skip Flow
- Each proactive reminder message must include interactive inline keyboard buttons:
  - `[✅ Đã hoàn thành]` (Mark Done)
  - `[⏳ Xin lùi 15 phút]` (Snooze 15 minutes)
  - `[🛑 Hôm nay nghỉ (Có lý do)]` (Skip with Reason)
- When `[✅ Đã hoàn thành]` is clicked:
  - Edit message or reply to confirm completion.
  - Increment the user's daily streak and log the record.
  - AI sends a brief congratulatory message acknowledging discipline.
- When `[⏳ Xin lùi 15 phút]` is clicked:
  - Update message to reflect snoozed status.
  - Schedule an automated one-shot reminder job in APScheduler to trigger after 15 minutes.
  - Enforce a maximum limit of 2 consecutive snoozes for that session, escalating firmness if reached.
- When `[🛑 Hôm nay nghỉ (Có lý do)]` is clicked:
  - Transition state to await the user's justification text via chat.
  - Pass the reason to the AI Coach to evaluate whether it is a legitimate obstacle or an excuse.
  - If it is an excuse/procrastination, AI breaks down the excuse and enforces a 2-minute micro-habit. If legitimate, record as skipped.

### R4. Two-Way AI Accountability Coach (Gemini API)
- Connect to Google Gemini API using `google-genai` with model `gemini-2.5-flash`.
- Coach Persona: Direct, concise, technical/practical mindset, slightly sarcastic toward procrastination/excuses, praises genuine execution. Responses must be concise (max 2–3 sentences).
- Maintain a short-term sliding context window (recent 6–10 messages) in memory so the AI understands ongoing dialogue context.
- Robust error handling: If the Gemini API or network fails, provide graceful fallback messages so bot operation is never interrupted.

### R5. Lightweight Atomic JSON Persistence
- Store check-in history, session statuses, snooze counts, and daily streaks in `data/records.json`.
- Automatically create `data/records.json` and directory if missing.
- Use atomic write techniques (writing to a temporary file and atomically renaming/replacing) to ensure data safety against crashes or concurrent writes.

### R6. Automated Test Suite (Verification)
- Include a test suite using `pytest` and `pytest-asyncio` with mocked Telegram Bot API and Gemini API responses.
- Tests must verify:
  - Schedule registration and correct timezone/cron triggers.
  - Inline button callback handling (Done, Snooze, Skip reason flow).
  - Snooze job creation and snooze limit enforcement.
  - Atomic JSON persistence and streak calculation.
  - Unauthorized user rejection.

## Acceptance Criteria

### Execution & Architecture
- [ ] Project root contains `.env.example`, `config.yaml`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `start.sh`, `start.bat`, `src/`, and `tests/`.
- [ ] Configuration separates secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID` in `.env`) from operational parameters (schedules, TOEIC syllabus, prompts in `config.yaml`).
- [ ] Bot boots cleanly, initializes APScheduler in `Asia/Ho_Chi_Minh` timezone, and connects handlers.

### Functionality & Persistence
- [ ] Unauthorized Telegram users attempting `/start` or sending messages receive an access denied notice or are ignored, without invoking Gemini.
- [ ] Proactive jobs fire with the 3 inline action buttons.
- [ ] Clicking `[✅ Đã hoàn thành]` records completion in `data/records.json` and updates streak.
- [ ] Clicking `[⏳ Xin lùi 15 phút]` schedules a 15-minute one-shot reminder and caps at 2 snoozes.
- [ ] Clicking `[🛑 Hôm nay nghỉ (Có lý do)]` prompts for reason, routes to Gemini evaluator, and updates record.
- [ ] `data/records.json` is written atomically without corruption.

### Verification
- [ ] Automated tests run via `pytest` and pass 100% without requiring external network access or real API tokens.


## 2026-10-04T03:32:03Z

Resume implementation of the Telegram Personal Accountability Coach at Milestone 3, building upon fully completed and tested Milestone 1 (Config, Storage, Atomic JSON) and Milestone 2 (Gemini AI Coach). Strictly do NOT re-run or modify completed M1 and M2 components.

Working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr
Integrity mode: development

## Current Baseline Status
- **Milestone 1 (DONE)**: `src/config.py`, `src/storage.py`, `config.yaml`, `.env.example`, 181 unit & adversarial tests passing.
- **Milestone 2 (DONE)**: `src/coach.py` (Gemini 2.5 Flash, sliding context, excuse evaluator, offline fallbacks), 153 tests passing.
- **E2E Test Suites (READY)**: `tests/test_e2e_tier1_features.py` through `tier4_scenarios.py` ready for validation.

## Remaining Requirements to Implement

### R1. Milestone 3: Proactive Scheduler Service (`src/scheduler.py`)
- Implement `SchedulerService` using APScheduler `AsyncIOScheduler` strictly configured for `Asia/Ho_Chi_Minh` timezone.
- Attach recurring cron triggers driven by `config.yaml`:
  1. **Gym Split 1**: Mon, Tue, Thu at 17:15.
  2. **Gym Split 2**: Wed, Sat at 16:15.
  3. **TOEIC Study**: Daily at 19:25 (with dynamic 7-day part rotation via `config.toeic.get_part_for_weekday()`).
  4. **Major Subject Study**: Daily at 20:40.
- Implement dynamic 15-minute DateTrigger snooze jobs with ID format `snooze_{session_id}_{snooze_count}` and callback invocation.
- Implement `cancel_job()`, `trigger_job()` (for test harness), `start()`, and `shutdown()`.
- Add unit tests in `tests/test_scheduler.py` and pass Group 2 scheduler tests in `tests/test_e2e_tier1_features.py`.
- Refer to detailed specification and blueprint in `.agents/teamwork/explorer_m3_1/analysis.md`.

### R2. Milestone 4: Telegram Bot Core & Interactive Inline Actions (`src/bot.py`, `src/main.py`)
- Implement `build_application(config, storage, coach, scheduler)` using `python-telegram-bot` (v20+ async).
- Enforce strict security whitelist: incoming messages or callback queries with `chat_id != ALLOWED_CHAT_ID` are immediately rejected without calling Gemini.
- Command handlers: `/start`, `/help`, `/status` (reporting streak, best streak, and total completions).
- Inline keyboards with buttons:
  - `[✅ Đã hoàn thành]`: Increments streak, updates `data/records.json`, queries coach for congratulation, edits message text.
  - `[⏳ Xin lùi 15 phút]`: Increments snooze count, schedules 15-minute one-shot reminder job in scheduler, enforces max 2 snoozes with escalating warnings.
  - `[🛑 Hôm nay nghỉ (Có lý do)]`: Sets user state to await justification text. Upon receipt, routes reason to `coach.evaluate_skip_reason()`. If excuse, enforces 2-minute micro-habit; if legitimate, marks session skipped.
- Free-form coaching chat: Authorized user messages outside skip flow receive responses from `coach.chat()`.
- Entrypoint `src/main.py`: Loads config, initializes storage, coach, scheduler, registers proactive triggers, builds application, and runs bot.

### R3. Milestone 5: Containerization, Setup Scripts & Documentation
- `Dockerfile` using `python:3.12-slim` or `python:3.11-slim`.
- `docker-compose.yml` with persistent volume mount for `data/` and environment variables from `.env`.
- Single-click startup scripts:
  - `start.bat` for Windows (creates venv if needed, installs requirements, launches bot).
  - `start.sh` for Linux/macOS (chmod +x, creates venv, installs requirements, launches bot).
- `README.md` with low-code friendly instructions for non-dev users.

### R4. Milestone 6: Final Integration & E2E Test Suite Validation
- Execute all tests across unit, integration, and E2E tiers (`tests/test_config.py`, `tests/test_storage.py`, `tests/test_coach.py`, `tests/test_scheduler.py`, `tests/test_bot.py`, `tests/test_e2e_tier*.py`).
- Ensure 100% pass rate with zero network access required.

## Acceptance Criteria

### Execution & Architecture
- [ ] `src/scheduler.py`, `src/bot.py`, and `src/main.py` created and adhere to interface contracts in `PROJECT.md`.
- [ ] `Dockerfile`, `docker-compose.yml`, `start.sh`, `start.bat`, and `README.md` created in root directory.
- [ ] M1 and M2 code remain intact without regression.

### Functionality & Persistence
- [ ] Unauthorized Telegram updates rejected at security gate without calling Gemini.
- [ ] Proactive scheduler registers all 4 scheduled jobs and dynamic snooze DateTrigger jobs.
- [ ] Done, Snooze (up to 2 times), and Skip reason workflows execute correctly and update `data/records.json`.
- [ ] `src/main.py` starts without import errors and boots bot lifecycle.

### Verification
- [ ] All unit, integration, and E2E tests pass 100% via `pytest`.
