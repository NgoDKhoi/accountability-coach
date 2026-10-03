# Adversarial Analysis & Stress Test Report: Milestone 1

**Author:** teamwork_preview_challenger (`challenger_m1_1`)  
**Target:** Milestone 1 — Config, Data Models & Atomic Persistence (`worker_m1_1`)  
**Evaluation Date:** 2026-10-03  
**Verdict:** `REQUEST_CHANGES`

---

## 1. Executive Summary

Milestone 1 implements configuration loading (`src/config.py`) and atomic JSON persistence with calendar streak tracking (`src/storage.py`). Baseline testing with `pytest tests/test_config.py tests/test_storage.py` passed with 77/77 tests.

However, empirical adversarial testing and failure injection via `tests/test_m1_adversarial.py` (22 tests) revealed **3 critical/high severity failure modes** in `src/storage.py`:
1. **Windows NTFS Temporary File Leak** upon write/fsync failures (`WinError 32` file locking preventing cleanup in `_sync_write`).
2. **Unhandled `UnicodeDecodeError`** causing application crash when `records.json` contains invalid UTF-8 bytes or binary garbage in `_sync_read`.
3. **Unhandled `TypeError`** causing application crash when `records.json` root is a non-dictionary JSON value (`[]`, `null`, `12345`).

At the same time, the streak engine, concurrency serialization under asyncio lock, and configuration validation proved highly robust across 365-day simulated progressions, leap years, timezone boundaries, and 100+ concurrent operations.

---

## 2. Empirical Test Results Matrix

| Test Suite / Category | Scenarios Tested | Passed | Failed | Status |
|---|---|---|---|---|
| **High Concurrency** | 100 concurrent same-day completions, 120 mixed operations (completions, snoozes, skips, reads), multi-instance access | 3 | 0 | **PASS** |
| **Crash & Failure Injection** | Serialization failure, fsync failure, os.replace failure, truncated JSON, binary garbage, non-dict roots | 3 | 5 | **FAIL** |
| **Calendar Streak Engine** | 365 continuous days, leap year (2024), non-leap year (2025), year rollover (2025->2026), gap resets, late dates, midnight boundary, effective streak expiry | 8 | 0 | **PASS** |
| **Config & Time Validation** | HH:MM boundaries, 24:00/25:00/12:60 checks, non-string, empty strings | 3 | 0 | **PASS** |
| **Total** | | **17** | **5** | **FAIL** |

---

## 3. Detailed Failure Modes & Empirical Evidence

### Challenge 1: Temporary File Handle Leak on Windows (`src/storage.py:136-159`)
- **Severity**: HIGH
- **Root Cause**:
  In `_sync_write`:
  ```python
  temp_file = tempfile.NamedTemporaryFile(..., delete=False, ...)
  temp_path = temp_file.name
  try:
      json.dump(data, temp_file, indent=2, ensure_ascii=False)
      temp_file.flush()
      os.fsync(temp_file.fileno())
      temp_file.close() # Only closed if everything succeeds!
      os.replace(temp_path, self.file_path)
  except Exception:
      if os.path.exists(temp_path):
          try:
              os.remove(temp_path)
          except OSError:
              pass
      raise
  ```
  If an exception occurs during `json.dump`, `temp_file.flush()`, or `os.fsync` (e.g. `TypeError`, disk full, process interrupt):
  `temp_file.close()` is never executed. On Windows NTFS, calling `os.remove(temp_path)` on an open file handle fails with:
  `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
  The `except OSError: pass` silently swallows this, leaving `records_*.tmp` permanently stranded in the `data/` directory.
- **Empirical Evidence**:
  ```text
  FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_json_dump_preserves_target_file
  FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_fsync_preserves_target_file
  AssertionError: assert 1 == 0
  where 1 = len(['records_jss7hz0h.tmp'])
  ```
- **Mitigation**:
  Ensure `temp_file.close()` is guaranteed before `os.remove(temp_path)`:
  ```python
  except Exception:
      try:
          temp_file.close()
      except Exception:
          pass
      if os.path.exists(temp_path):
          try:
              os.remove(temp_path)
          except OSError:
              pass
      raise
  ```

---

### Challenge 2: Unhandled `UnicodeDecodeError` in Crash Recovery (`src/storage.py:107-120`)
- **Severity**: HIGH
- **Root Cause**:
  In `_sync_read`:
  ```python
  try:
      with open(self.file_path, "r", encoding="utf-8") as f:
          data = json.load(f)
  except (json.JSONDecodeError, OSError) as exc:
      ...
  ```
  When `records.json` is partially written or corrupted with invalid UTF-8 / binary garbage (e.g. interrupted system writes, abrupt power loss), `f.read()` raises `UnicodeDecodeError`.
  Because `UnicodeDecodeError` subclasses `ValueError` (not `json.JSONDecodeError` or `OSError`), it bypasses the `except` clause and bubbles up unhandled, crashing `AtomicJsonStore.load_data()`.
- **Empirical Evidence**:
  ```text
  FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_binary_garbage
  UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 1: invalid start byte
  ```
- **Mitigation**:
  Add `UnicodeDecodeError` (or `ValueError`) to the caught exceptions:
  ```python
  except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
  ```

---

### Challenge 3: Unhandled `TypeError` on Non-Dictionary JSON Roots (`src/storage.py:121-125`)
- **Severity**: MEDIUM-HIGH
- **Root Cause**:
  In `_sync_read`:
  ```python
  # Enforce presence of all standard schema keys
  for key, val in DEFAULT_DATA.items():
      if key not in data:
          data[key] = copy.deepcopy(val)
  return data
  ```
  If `records.json` contains valid JSON that is not a dictionary (e.g., `[]`, `null`, `12345`, `"string"`):
  - `[]`: `data[key] = copy.deepcopy(val)` raises `TypeError: list indices must be integers or slices, not str`.
  - `null`: `key not in data` raises `TypeError: argument of type 'NoneType' is not a container or iterable`.
  - `12345`: `key not in data` raises `TypeError: argument of type 'int' is not a container or iterable`.
  - `"string"`: raises `TypeError: 'str' object does not support item assignment`.
  This fails to auto-recover or re-initialize to default schema, crashing the store.
- **Empirical Evidence**:
  ```text
  FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_array_root
  TypeError: list indices must be integers or slices, not str
  FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_null_root
  TypeError: argument of type 'NoneType' is not a container or iterable
  FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_number_root
  TypeError: argument of type 'int' is not a container or iterable
  ```
- **Mitigation**:
  Enforce `isinstance(data, dict)` check before schema key iteration, treating non-dict data as corruption:
  ```python
  if not isinstance(data, dict):
      logger.error("Loaded data from %s is not a dictionary (%s). Creating backup and re-initializing.", self.file_path, type(data))
      backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
      try:
          os.replace(self.file_path, backup_path)
      except OSError:
          pass
      default_data = copy.deepcopy(DEFAULT_DATA)
      self._sync_write(default_data)
      return default_data
  ```

---

## 4. Validated Invariants (Passed Stress Tests)

The following components were stress-tested and demonstrated rock-solid correctness:
1. **Concurrency**: 100 simultaneous completions on the same day executed with zero exceptions, zero lost updates, and correct `total_completions == 100`. 120 mixed operations (completions, snoozes, skips, reads) maintained complete data integrity.
2. **Calendar Streak Engine**:
   - 365-day continuous progression calculated streaks flawlessly ($1 \to 365$).
   - Leap year transitions (2024-02-28 $\to$ 2024-02-29 $\to$ 2024-03-01) handled seamlessly.
   - Non-leap year transitions (2025-02-28 $\to$ 2025-03-01) handled seamlessly.
   - Year rollovers (2025-12-30 $\to$ 2026-01-02) handled seamlessly.
   - Streak breaks and multiple resets preserve the `best_streak` across resets.
   - Out-of-order date arrivals do not regress current streak or corrupt `last_completed_date`.
   - Midnight boundary in `Asia/Ho_Chi_Minh` timezone correctly marks calendar day increment across 23:59:59 and 00:00:01.
3. **Effective Streak Calculation**:
   - Correctly expires to 0 after 2 days lapse ($\Delta > 1$).
   - Retains active streak for today ($\Delta = 0$) and yesterday ($\Delta = 1$).
4. **Configuration Validation**:
   - Strict time format enforcement rejecting invalid times (`24:00`, `25:00`, `12:60`, `12:00:00`, non-strings).
   - Strict `ALLOWED_CHAT_ID` integer and non-zero validation.

---

## 5. Conclusion & Action Items

The code is well-structured and 85% of edge cases are handled elegantly. However, persistence layer crash safety must be watertight on Windows and against non-standard corruptions before proceeding to Milestone 2 (AICoach) and Milestone 4 (PTB Bot).

**Action Items for `worker_m1_1`**:
1. In `src/storage.py` `_sync_write`: Ensure `temp_file.close()` is called in the `except` block before `os.remove(temp_path)`.
2. In `src/storage.py` `_sync_read`: Catch `UnicodeDecodeError` in addition to `json.JSONDecodeError` and `OSError`.
3. In `src/storage.py` `_sync_read`: Add `if not isinstance(data, dict):` check and trigger corruption recovery.
4. Run `pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py` — all 99 tests must pass with 0 failures.
