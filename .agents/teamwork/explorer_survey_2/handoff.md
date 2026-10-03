# Handoff Report: Schemas, Interface Boundaries, Lifecycle & Deployment

**Agent:** `teamwork_preview_explorer` (explorer_survey_2)  
**Parent / Recipient:** `ac41226a-6cc6-45bc-9027-605104e502f4` (orchestrator)  
**Handoff Type:** Hard (Survey Task Complete)  
**Date:** 2026-10-03  

---

## 1. Observation

1. **Requirements in `ORIGINAL_REQUEST.md`**:
   - Lines 12–15: Async Telegram bot using `python-telegram-bot` (v20+); strict user authorization via `ALLOWED_CHAT_ID` loaded from `.env`; setup files (`.env.example`, `config.yaml`, `Dockerfile`, `docker-compose.yml`, `start.bat`, `start.sh`).
   - Lines 17–27: Async scheduler via `APScheduler` (`AsyncIOScheduler`) in `Asia/Ho_Chi_Minh` timezone; Gym sessions (Mon, Tue, Thu at 17:15; Wed, Sat at 16:15); TOEIC study session (daily at 19:25 with 7-day parts rotation); Major subject study (daily at 20:40).
   - Lines 29–46: Inline action buttons: `[✅ Đã hoàn thành]`, `[⏳ Xin lùi 15 phút]` (15m one-shot job, max 2 limit, escalating firmness), `[🛑 Hôm nay nghỉ (Có lý do)]` (text reason capture, Gemini reason evaluation: excuse vs legitimate obstacle, 2-minute micro-habit enforcement).
   - Lines 47–52: Google Gemini API via `google-genai` with model `gemini-2.5-flash`; concise technical persona (max 2-3 sentences), sliding context window (6-10 messages), graceful offline fallback.
   - Lines 53–57: Atomic persistence in `data/records.json` using temporary file + rename/replace.
   - Lines 58–66: 100% offline unit/integration test suite via `pytest` and `pytest-asyncio` mocking Telegram and Gemini.

2. **Workspace Environment**:
   - `python --version` returned `Python 3.14.4` in the host shell environment.
   - Workspace root `c:/Users/khoi1/Documents/antigravity/serene-bohr` is currently an uninitialized repo containing only `.agents` and `.git`.
   - Python packages `python-telegram-bot`, `apscheduler`, `google-genai` are not yet installed in host Python, requiring standard project virtual environment management via `requirements.txt`.

3. **Survey Phase Artifacts Delivered**:
   - `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/analysis.md` (detailed architectural specifications and schema definitions).

---

## 2. Logic Chain

1. **Separation of Configuration Concerns**:
   - *Based on Observation 1 (R1)*: Storing API keys or chat IDs in `config.yaml` risks committing secrets to git. Therefore, `.env` / `.env.example` strictly houses `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, and `ALLOWED_CHAT_ID`, while `config.yaml` houses operational schedules, TOEIC syllabus rotation, prompts, and limits.
2. **Persistence Schema & Concurrency Safety**:
   - *Based on Observation 1 (R3, R5)*: The user can interact asynchronously via Telegram callbacks while APScheduler fires background jobs. Without atomic persistence, sudden process termination during file writing corrupts JSON files. Specifying temporary file write + flush + fsync + `os.replace` guarantees file integrity across crashes and operating systems.
   - *Based on Observation 1 (R5)*: Tracking both `active_sessions` and calendar streak requires tracking `current_streak`, `longest_streak`, `last_completed_date`, and `total_completions`. Evaluating against `today` in `Asia/Ho_Chi_Minh` ensures timezone consistency regardless of host system time.
3. **Module Decoupling & Interface Boundaries**:
   - *Based on Observation 1 (R1 - R5)*:
     - `src/config.py` acts as a pure read-only configuration provider returning immutable dataclasses.
     - `src/storage.py` manages local file I/O and state mutations without importing Telegram or Gemini libraries.
     - `src/coach.py` encapsulates `google-genai` API communication, sliding context window, and fallback dictionary without knowing Telegram bot internals.
     - `src/scheduler.py` registers cron jobs and dynamic one-shot 15-minute date jobs via `AsyncIOScheduler`.
     - `src/bot.py` binds Telegram event loop, validates `ALLOWED_CHAT_ID`, builds inline keyboards, and routes user text to either skip-reason evaluation or AI coaching chat.
4. **Deployability & Cross-Platform Execution**:
   - *Based on Observation 1 & 2*: A containerized environment (`Dockerfile` with `python:3.11-slim`, `docker-compose.yml`) avoids host Python version discrepancies, sets `TZ=Asia/Ho_Chi_Minh`, and mounts `./data:/app/data`. Single-click shell scripts (`start.sh` for Linux/macOS and `start.bat` for Windows) create a local `.venv` and install `requirements.txt` automatically.

---

## 3. Caveats

1. **APScheduler Version Constraint**: `APScheduler` version 3.x (`apscheduler>=3.10.4,<4.0.0`) must be used. APScheduler 4.0 alpha/beta introduces major breaking API changes that are incompatible with standard `AsyncIOScheduler` syntax.
2. **`google-genai` Library**: The request explicitly requires `google-genai` with model `gemini-2.5-flash` (not legacy `google-generativeai`). The async client (`genai.Client().aio.models.generate_content`) should be utilized to prevent blocking the asyncio event loop.
3. **Telegram Callback Button Length**: Telegram `callback_data` has a strict 64-byte limit. All callback payloads (`done:<session_id>`, `snooze:<session_id>`, `skip:<session_id>`) use compact session identifiers (e.g. `gym_20261003_1715` = 17 bytes) well below the 64-byte limit.

---

## 4. Conclusion

The architectural boundaries, JSON persistence schemas, YAML configurations, environment templates, module interface contracts, and container deployment scripts are fully specified and documented in `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/analysis.md`. The design guarantees:
1. Complete coverage of requirements R1 through R6.
2. Zero ambiguity for implementer agents across all 5 core modules.
3. 100% testability using offline mocks without real tokens or external network access.

---

## 5. Verification Method

1. **Inspect Analysis Report**:
   - Review file content at: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_2/analysis.md`
   - Verify that all sections (Config, Storage, AI Coach, Scheduler, Bot, Containerization, Test Strategy) provide explicit signatures and schemas.
2. **Contract Schema Validation**:
   - Confirm `config.yaml` schema contains Gym (Mon/Tue/Thu 17:15, Wed/Sat 16:15), TOEIC 7-day rotation (Mon–Sun), Major subject (20:40), and fallback strings.
   - Confirm `data/records.json` schema contains `streak`, `active_sessions`, `awaiting_reason`, and `history`.
3. **Invalidation Condition**:
   - The contract design is invalidated if any module signature lacks type annotations, if secret tokens are exposed in `config.yaml`, or if APScheduler trigger times differ from `ORIGINAL_REQUEST.md`.
