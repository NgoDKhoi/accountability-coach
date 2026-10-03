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
