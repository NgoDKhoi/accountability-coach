# Handoff Report — Technical Architecture Survey

**From**: teamwork_preview_explorer (Survey Phase)  
**To**: Orchestrator & Downstream Architect / Implementer Agents  
**Date**: 2026-10-03  
**Working Directory**: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/`  
**Detailed Report**: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/analysis.md`  

---

## 1. Observation

1. **System & Working Environment**:
   - Host OS: Windows.
   - Python Version: `3.14.4` (verified via `python --version`, exit code 0).
   - Package status: `tzdata 2026.3`, `python-dotenv 1.0.1`, and `PyYAML 6.0.3` are present in host pip. `python-telegram-bot`, `APScheduler`, `google-genai`, and `pytest` are required dependencies to be specified in `requirements.txt`.
2. **Authoritative Requirements (`ORIGINAL_REQUEST.md`)**:
   - `ORIGINAL_REQUEST.md:13`: Mandates asynchronous bot using `python-telegram-bot` (v20+).
   - `ORIGINAL_REQUEST.md:14`: Strict user authorization (`ALLOWED_CHAT_ID` via `.env`).
   - `ORIGINAL_REQUEST.md:18`: `APScheduler` (`AsyncIOScheduler`) configured for `Asia/Ho_Chi_Minh` timezone.
   - `ORIGINAL_REQUEST.md:19-27`: Baseline schedules: Gym (Mon, Tue, Thu 17:15; Wed, Sat 16:15), TOEIC Daily at 19:25 with 7-day syllabus rotation, Major Study Daily at 20:40.
   - `ORIGINAL_REQUEST.md:29-46`: Inline action buttons (`[✅ Đã hoàn thành]`, `[⏳ Xin lùi 15 phút]`, `[🛑 Hôm nay nghỉ (Có lý do)]`), max 2 consecutive snoozes, skip reason evaluation via AI Coach.
   - `ORIGINAL_REQUEST.md:48-52`: `google-genai` SDK with `gemini-2.5-flash`, concise 2-3 sentence persona, sliding context window (6-10 messages), resilient fallback error handling.
   - `ORIGINAL_REQUEST.md:54-57`: Atomic JSON persistence in `data/records.json`.
   - `ORIGINAL_REQUEST.md:59-66`: Automated test suite via `pytest` and `pytest-asyncio` with mocked Telegram & Gemini APIs.
3. **Cross-Platform Atomic Write Verification**:
   - Directly verified on host Windows system via `python -c "..."` (exit code 0):
     Creating a temporary file with `NamedTemporaryFile(delete=False)` in the target directory, closing the file handle, and performing `os.replace(tmp, target)` succeeded atomically and written content `{"status": "ok"}` was verified.
4. **Google GenAI SDK Verification**:
   - The modern SDK is `google-genai` (`from google import genai`, `from google.genai import types`).
   - Asynchronous generation is accessed via `client.aio.models.generate_content(...)`.
   - Persona instructions are passed via `types.GenerateContentConfig(system_instruction=...)`.
   - Multi-turn sliding conversation is passed as a list of `types.Content(role="user"|"model", parts=[types.Part.from_text(...)])`.
5. **PTB v20 & APScheduler Integration**:
   - PTB `ApplicationBuilder` provides `post_init` and `post_shutdown` coroutine hooks that execute within the bot's `asyncio` event loop.

---

## 2. Logic Chain

1. **Telegram & Scheduler Co-existence**:
   - *Observation*: PTB v20 runs entirely on `asyncio`. `APScheduler` offers `AsyncIOScheduler`.
   - *Step 1*: Rather than relying on PTB's internal `JobQueue` wrappers (which constrain trigger types and complicate standalone testing), a dedicated `SchedulerService` wrapping `AsyncIOScheduler(timezone=ZoneInfo("Asia/Ho_Chi_Minh"))` directly provides full control over `CronTrigger` and dynamic `DateTrigger` snooze jobs.
   - *Step 2*: Registering `scheduler_service.start()` in `post_init(application)` and `scheduler_service.shutdown()` in `post_shutdown(application)` ensures both share the exact same event loop lifecycle with zero concurrency conflicts.
2. **Dynamic Snooze & Cap Enforcement**:
   - *Observation*: User clicks `snooze` button; max 2 snoozes per session allowed.
   - *Step 1*: In the callback handler for `snooze:<session_id>`, query `records.json` for `snooze_count`.
   - *Step 2*: If `snooze_count >= 2`, disallow scheduling, edit message with escalated firmness.
   - *Step 3*: If `snooze_count < 2`, increment count, calculate `run_date = now + timedelta(minutes=15)`, register job with ID `f"snooze_{session_id}_{date}_{count}"` using `DateTrigger`, and edit message with confirmation.
3. **Cross-Platform Atomic Storage**:
   - *Observation*: Windows raises `WinError 32` if replacing an open file. Linux raises `EXDEV` if moving across different mount points.
   - *Step 1*: Target directory must be guaranteed (`os.makedirs(dir_name, exist_ok=True)`).
   - *Step 2*: Temporary file must be created inside `dir_name` (`tempfile.NamedTemporaryFile(dir=dir_name, delete=False)`).
   - *Step 3*: Data must be flushed and synced (`os.fsync`), and the temporary file handle **closed** before `os.replace`.
   - *Step 4*: Wrap the whole read-modify-write operation with an in-memory `asyncio.Lock()` to prevent coroutine race conditions.
4. **Offline Testability**:
   - *Observation*: Acceptance criteria require 100% test pass offline without real tokens or external network.
   - *Step 1*: `pytest.ini` with `asyncio_mode = auto` standardizes async test execution.
   - *Step 2*: Telegram handlers accept `(update, context)`. Passing mock `Update` (with mock `message` or `callback_query`) and mock `Context` allows direct invocation and verification of bot replies and callback answers.
   - *Step 3*: Injecting a mock `gemini_client` into the AI coach service decouples tests from the Google API and verifies exact fallback and persona handling.

---

## 3. Caveats

1. **APScheduler 3.x vs 4.x**: APScheduler 4.0 is a major rewrite currently in alpha/pre-release with incompatible APIs. The project must pin `APScheduler>=3.10.4,<4.0.0` to maintain stability with `AsyncIOScheduler`.
2. **Windows IANA Timezones**: Python standard `zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")` on Windows systems without system-level tzdata requires the `tzdata` package. `tzdata` is confirmed present on the host and must be included in `requirements.txt`.
3. **Multi-process concurrency**: The atomic storage implementation uses `os.replace` and an in-process `asyncio.Lock()`. If multiple OS processes write to `records.json` simultaneously, OS-level file locking (`msvcrt`/`fcntl` or `portalocker`) would be required. Since the bot is architected as a single daemon process, `asyncio.Lock()` + atomic replace is completely sufficient.

---

## 4. Conclusion

The technical architecture is thoroughly validated, concrete, and ready for immediate architectural blueprinting and implementation:
- **Bot Layer**: `python-telegram-bot` v20+ with `@authorized_only` guard, `post_init` / `post_shutdown` hooks.
- **Scheduler**: Dedicated `AsyncIOScheduler` configured for `Asia/Ho_Chi_Minh` managing the 3 baseline schedules (Gym, TOEIC 7-day rotation, Major) and dynamic 15-minute DateTrigger snooze jobs capped at 2.
- **AI Coach**: `google-genai` with `gemini-2.5-flash`, `GenerateContentConfig(system_instruction=...)`, sliding deque(10) context, 2-3 sentence persona, and circuit-breaking fallbacks.
- **Persistence**: `AtomicJsonStore` with closed temporary file + `os.replace` + `asyncio.Lock()`.
- **Testing**: Pytest with `pytest-asyncio` auto mode and comprehensive Telegram & GenAI mocks.

---

## 5. Verification Method

1. **Inspect Analysis Report**:
   - Review `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_survey_1/analysis.md` for complete code structures, schemas, and configurations.
2. **Test Atomic Write Pattern**:
   - Command:
     ```powershell
     python -c "import os, tempfile, json; os.makedirs('data', exist_ok=True); f = tempfile.NamedTemporaryFile('w', dir='data', delete=False); json.dump({'test': True}, f); f.close(); os.replace(f.name, 'data/test.json'); print(open('data/test.json').read()); os.remove('data/test.json')"
     ```
   - Expect: prints `{"test": true}` without `PermissionError`.
3. **Invalidation Conditions**:
   - If APScheduler 4.0 is installed, triggers and scheduler APIs will fail.
   - If temporary files are not closed before `os.replace` on Windows, tests will crash with `WinError 32`.
   - If unauthorized users can trigger Gemini calls or mutate store records, the security filter is invalid.
