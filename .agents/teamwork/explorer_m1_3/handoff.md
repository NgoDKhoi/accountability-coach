# Milestone 1: Handoff Report — Test Suite & Fixtures

**Agent**: `teamwork_preview_explorer` (`explorer_m1_3`)  
**Target Milestone**: Milestone 1 (Test Suite & Fixtures)  
**Recipient**: Orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`) / Milestone 1 Developer  
**Date**: 2026-10-03  
**Status**: COMPLETE (Hard Handoff)  

---

## 1. Observation

1. **Requirements & Scope**:
   - `ORIGINAL_REQUEST.md` (lines 53–66): Mandates atomic JSON persistence (`data/records.json`) ensuring data safety against crashes or concurrent writes, and an automated test suite using `pytest` and `pytest-asyncio` verifying atomic JSON persistence and streak calculation without external network access or real API tokens.
   - `orchestrator/PROJECT.md` (lines 70–133): Defines interface contracts for `src/config.py` (`AppConfig`, `GymScheduleConfig`, `ToeicScheduleConfig`, `MajorScheduleConfig`, `load_config()`) and `src/storage.py` (`StreakData`, `AtomicJsonStore` with methods `load_data()`, `save_data()`, `get_streak()`, `record_completion()`, `record_snooze()`, `record_skip()`, `get_session_status()`).
   - `explorer_m1_3/DISPATCH.md` (lines 11–15, 31–36): Explicitly tasks designing unit tests for `tests/test_config.py`, `tests/test_storage.py`, and `tests/conftest.py`, covering valid/invalid config loading, missing env vars, whitespace handling in `ALLOWED_CHAT_ID`, atomic write verification, directory creation, streak progression and resets, multi-session same-day idempotency, snooze increments, and skip reasons.

2. **Windows NTFS File Locking Constraints**:
   - `explorer_survey_1/analysis.md` (lines 405–412): Notes that on Windows NTFS, attempting `os.replace` on an open file handle causes `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process.` Therefore, `temp_file.close()` must be called prior to `os.replace()`, and temp files must reside in the same directory (`data/`) to prevent cross-volume link errors (`EXDEV`/WinError 17).

3. **Host Runtime Environment**:
   - Command `python --version` confirmed `Python 3.14.4` running on Windows.
   - Command `pytest --version` confirmed pytest is not installed globally; virtual environment installation of `pytest`, `pytest-asyncio`, and `pyyaml` will be required during implementation.

---

## 2. Logic Chain

1. **Config Validation Logic**:
   - `ALLOWED_CHAT_ID` comes in from `.env` or `os.environ` as a string. Telegram users often paste strings with spaces (e.g. `" 123456789 \n"`). `src/config.py` must `.strip()` and convert to `int`. If the string is non-numeric, empty, or zero, `load_config` must raise `ValueError`.
   - Missing required environment variables (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`) must abort startup with clear `ValueError` specifying the variable name.
   - `config.yaml` schema must enforce structural integrity: root sections (`app`, `schedules`, `prompts`, `fallbacks`), exact 7-part TOEIC rotation for Monday–Sunday, 24-hour `HH:MM` time format, and valid IANA timezones (`Asia/Ho_Chi_Minh`).

2. **Storage Integrity Logic**:
   - When `AtomicJsonStore` is instantiated with a path in non-existent directories, parent directories must be auto-created (`os.makedirs(exist_ok=True)`).
   - If `records.json` does not exist on disk, `load_data()` must return a canonical empty database structure without crashing.
   - Atomic replacement must write to a temporary file in `data/`, flush, fsync, close handle, and call `os.replace`. If an exception occurs during serialization or replace, the target file must remain intact and temporary files must be cleaned up.
   - Concurrency must be protected with `asyncio.Lock` to serialize simultaneous coroutine updates.

3. **Streak Calculation & Idempotency Logic**:
   - `today_str` is formatted as ISO `YYYY-MM-DD` in `Asia/Ho_Chi_Minh`.
   - On the first completion: `current_streak = 1`, `best_streak = 1`, `last_completed_date = today_str`, `total_completions = 1`.
   - On subsequent sessions on the **same calendar day** (e.g., Gym completed, then TOEIC completed): `last_completed_date == today_str`. Daily streak counter must **remain 1** (idempotent), but `total_completions` increments.
   - On consecutive calendar days (`(today - last_date).days == 1`): `current_streak += 1`, updating `best_streak` if exceeded.
   - Across month boundaries (`2026-10-31` to `2026-11-01`), year boundaries (`2026-12-31` to `2027-01-01`), and leap days (`2028-02-28` to `2028-02-29`), date arithmetic correctly identifies consecutive days.
   - On gaps (`(today - last_date).days > 1`): `current_streak` resets to `1`, but `best_streak` remains preserved.

4. **Session Status, Snooze, & Skip Logic**:
   - `record_snooze(session_id, count)` transitions status to `"snoozed"` and stores `snooze_count`. Subsequent completion retains `snooze_count` history.
   - `record_skip(session_id, reason, classification, ts)` transitions status to `"skipped"` and records reason and classification (`EXCUSE` vs `LEGITIMATE`). Crucially, a skip must **never increment `current_streak`** or update `last_completed_date`.

---

## 3. Caveats

1. **Milestone Boundary**: This test specification strictly covers Milestone 1 components (`src/config.py` and `src/storage.py`). Telegram Bot handlers (`src/bot.py`), APScheduler jobs (`src/scheduler.py`), and Gemini API calls (`src/coach.py`) are out of Milestone 1 unit test scope and will be tested in subsequent milestones (M2, M3, M4) and E2E suites.
2. **Pytest Dependency**: `pytest` and `pytest-asyncio` must be installed in the project virtual environment before executing the test command.
3. **No Database Migration Layer**: The schema operates on single-file local JSON. Schema migrations are handled by defensive dictionary `.get(key, default)` lookups in `load_data()`.

---

## 4. Conclusion

The complete test suite specification and implementations for Milestone 1 are ready in `analysis.md`:
- `tests/conftest.py`: 9 modular pytest fixtures providing zero-network isolation, `tmp_path` directories, mock environment variables, and pre-configured store/config objects.
- `tests/test_config.py`: 22 test scenarios across 3 test classes (`TestLoadConfigSuccess`, `TestEnvValidation`, `TestYamlValidation`).
- `tests/test_storage.py`: 23 test scenarios across 5 test classes (`TestStorageInitAndDirectory`, `TestAtomicWriteAndCrashSafety`, `TestStreakProgression`, `TestSessionTracking`, `TestDataCorruptionRecovery`).

The test suite thoroughly covers all requirements, failure modes, Windows NTFS safety rules, and streak edge cases.

---

## 5. Verification Method

### Independent Verification Commands
```bash
# 1. Install test dependencies
pip install pytest pytest-asyncio pyyaml

# 2. Run config unit tests
pytest tests/test_config.py -v

# 3. Run storage unit tests
pytest tests/test_storage.py -v

# 4. Run entire Milestone 1 unit test suite
pytest tests/test_config.py tests/test_storage.py -v --tb=short
```

### Files to Inspect
- Detailed test suite analysis & code: `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_3/analysis.md`
- Target implementation paths:
  - `tests/conftest.py`
  - `tests/test_config.py`
  - `tests/test_storage.py`

### Invalidation Conditions
The test suite or design is invalidated if:
1. `ALLOWED_CHAT_ID` with leading/trailing whitespace fails to parse into integer.
2. An unclosed file handle causes `PermissionError: [WinError 32]` on Windows during atomic file replace.
3. Multiple session completions on the same calendar day cause `current_streak` to increment more than once.
4. A session skip causes `current_streak` to advance.
5. Missing mandatory secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`) do not fail fast with `ValueError`.
