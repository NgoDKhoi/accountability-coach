# Task Assignment: Milestone 1 Worker - Config & Storage Implementation

Read:
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_1/analysis.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_2/analysis.md`
- `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_3/analysis.md`

Your Working Directory:
`c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m1_1/`

Exclusive File Ownership:
- `.env.example`
- `config.yaml`
- `requirements.txt`
- `src/__init__.py`
- `src/config.py`
- `src/storage.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_config.py`
- `tests/test_storage.py`

Task Requirements:
1. Implement `requirements.txt` containing all runtime and test dependencies (`python-telegram-bot>=20.0`, `apscheduler>=3.10.4,<4.0.0`, `google-genai>=0.1.1`, `python-dotenv>=1.0.0`, `pyyaml>=6.0.0`, `tzdata>=2024.1`, `pytest>=7.0.0`, `pytest-asyncio>=0.21.0`).
2. Create `.env.example` with clear comments for `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`.
3. Create `config.yaml` with Gym schedules (Mon/Tue/Thu 17:15, Wed/Sat 16:15), 7-day TOEIC rotation (Part 1 to Full Mock), Major study (20:40), timezone `Asia/Ho_Chi_Minh`, prompts, and offline fallback responses.
4. Implement `src/config.py` with typed immutable dataclasses (`AppConfig`, `GymScheduleConfig`, `ToeicScheduleConfig`, `MajorScheduleConfig`) and robust `load_config()`. Enforce integer conversion for `ALLOWED_CHAT_ID` with whitespace stripping, validate required environment variables, validate timezone against `zoneinfo.ZoneInfo`, and validate 7-day rotation.
5. Implement `src/storage.py` (`AtomicJsonStore`, `StreakData`). Auto-create directories. Implement crash-safe atomic write using `tempfile.NamedTemporaryFile` in `data/` directory, flushing, closing file handle before calling `os.replace` (critical for Windows NTFS file locking), protected by `asyncio.Lock` and `asyncio.to_thread`. Implement calendar streak accounting in `Asia/Ho_Chi_Minh` timezone (handling first day, consecutive day, gap reset, and same-day multi-session idempotency). Implement session state tracking and skip recording.
6. Implement `tests/conftest.py`, `tests/test_config.py`, and `tests/test_storage.py` covering all positive, boundary, and negative test cases.
7. Install dependencies or run tests in virtual environment using Python and pytest. Ensure 100% of unit tests pass cleanly.
8. Deliver `analysis.md` and `handoff.md` in your directory.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.


## 2026-10-03T09:43:24Z
From: ac41226a-6cc6-45bc-9027-605104e502f4
Content: You are teamwork_preview_worker for Milestone 1 (Config, Data Models & Atomic Persistence).
Your assigned working directory: c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m1_1/
Please read the authoritative requirements at:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/ORIGINAL_REQUEST.md
Also read:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/orchestrator/PROJECT.md
and your dispatch instructions at:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/worker_m1_1/DISPATCH.md
and the 3 explorer reports at:
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_1/analysis.md
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_2/analysis.md
c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_3/analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your exclusive files to implement:
- requirements.txt
- .env.example
- config.yaml
- src/__init__.py
- src/config.py
- src/storage.py
- tests/__init__.py
- tests/conftest.py
- tests/test_config.py
- tests/test_storage.py

You must run the tests to verify that all config and storage tests pass 100%. Document test execution and outputs in your handoff report.
Deliver analysis.md and handoff.md in your working directory.
When done, message the orchestrator.
