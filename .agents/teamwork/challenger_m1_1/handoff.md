# Milestone 1 Challenger Handoff Report: Empirical Stress Test & Review

**Author:** teamwork_preview_challenger (`challenger_m1_1`)  
**Recipient:** Orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`)  
**Working Directory:** `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/challenger_m1_1/`  
**Milestone:** Milestone 1 (Config, Data Models & Atomic Persistence)  
**Date:** 2026-10-03  
**Verdict:** `REQUEST_CHANGES`

---

## 1. Observation

1. **Baseline Verification**:
   - Command: `python -m pytest tests/test_config.py tests/test_storage.py -v`
   - Result: 77 passed in 2.17s.

2. **Adversarial & Stress Harness Creation**:
   - File created: `tests/test_m1_adversarial.py` (22 tests covering concurrency bursts, Windows failure injection, binary garbage, non-dict JSON roots, leap years, year rollovers, timezone midnight crossings, and config boundaries).

3. **Empirical Failure Observations in `src/storage.py`**:
   - **Failure 1 & 2 (`_sync_write`, lines 136–158)**:
     - Verbatim test output:
       ```text
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_json_dump_preserves_target_file
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_fsync_preserves_target_file
       AssertionError: assert 1 == 0
        +  where 1 = len(['records_jss7hz0h.tmp'])
       ```
     - Code observation: In `_sync_write`, `temp_file.close()` is placed after `os.fsync(temp_file.fileno())` inside the try-block. When an exception occurs during `json.dump`, `flush`, or `fsync`, `temp_file.close()` is skipped. On Windows NTFS, calling `os.remove(temp_path)` on an open handle raises `PermissionError: [WinError 32]`, which is swallowed by `except OSError: pass`, leaving orphaned `.tmp` files.
   - **Failure 3 (`_sync_read`, line 110)**:
     - Verbatim test output:
       ```text
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_binary_garbage
       UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 1: invalid start byte
       ```
     - Code observation: `_sync_read` catches `(json.JSONDecodeError, OSError)`. Binary garbage or invalid UTF-8 bytes trigger `UnicodeDecodeError`, which subclasses `ValueError` and bypasses the `try-except` block, crashing `load_data()`.
   - **Failure 4, 5, 6 (`_sync_read`, lines 121–125)**:
     - Verbatim test output:
       ```text
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_array_root
       TypeError: list indices must be integers or slices, not str
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_null_root
       TypeError: argument of type 'NoneType' is not a container or iterable
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_number_root
       TypeError: argument of type 'int' is not a container or iterable
       ```
     - Code observation: `_sync_read` iterates `for key, val in DEFAULT_DATA.items(): if key not in data:` assuming `data` is a `dict`. If `data` is `[]`, `null`, or `12345`, it throws `TypeError`.

4. **Empirical Success Observations**:
   - Concurrency: 100 concurrent completions on same day passed with zero lost updates. 120 mixed concurrent operations passed.
   - Streak calculation: 365-day continuous progression passed. Leap year (2024-02-28 -> 2024-02-29 -> 2024-03-01) passed. Non-leap year (2025-02-28 -> 2025-03-01) passed. Year boundary (2025-12-31 -> 2026-01-01) passed. Streak break gap reset passed while preserving best streak. Out-of-order date submissions passed. Timezone midnight boundary across 23:59:59 and 00:00:01 in `Asia/Ho_Chi_Minh` passed.

---

## 2. Logic Chain

1. **NTFS File Locking Mechanics (Observation 3)**:
   - On Windows, a file cannot be deleted while an open file handle exists.
   - In `src/storage.py:136-159`, `temp_file.close()` is omitted in the exception handler.
   - Therefore, any transient serialization or I/O failure leaks temporary files indefinitely.
   - Fix: Close `temp_file` in `except Exception:` prior to `os.remove(temp_path)`.

2. **Exception Hierarchy in Python (Observation 3)**:
   - `UnicodeDecodeError` inherits from `ValueError`, NOT `OSError` or `json.JSONDecodeError`.
   - When a corrupted file has invalid byte sequences, `_sync_read` fails to catch `UnicodeDecodeError`.
   - Fix: Add `UnicodeDecodeError` to the caught exception tuple in `_sync_read`.

3. **Data Type Assumptions in JSON Deserialization (Observation 3)**:
   - `json.load()` produces valid Python primitives (`list`, `NoneType`, `int`, `str`) if the JSON file contains those root values.
   - `_sync_read` directly subscripts `data[key]` without checking `isinstance(data, dict)`.
   - Fix: Validate `isinstance(data, dict)` immediately after `json.load`, backing up corrupt non-dict data and resetting to `DEFAULT_DATA`.

---

## 3. Caveats

- **Scope Delimitation**: This evaluation exclusively stress-tested Milestone 1 deliverables (`src/config.py`, `src/storage.py`, data models, and persistence). Live Telegram bot networking and Gemini API interactions are deferred to Milestones 2 and 4.
- **Implementation Immunity**: In strict compliance with the Teamwork review protocol, no production code in `src/` was modified by this challenger. Fixes must be applied by `worker_m1_1`.
- **Adversarial Test Suite Retained**: The test file `tests/test_m1_adversarial.py` is saved in `tests/` so `worker_m1_1` can directly run and verify the fixes.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

Milestone 1 is well-architected and demonstrates exceptional rigor in streak calculation and async concurrency. However, 3 crash safety and cleanup bugs in `src/storage.py` must be resolved by `worker_m1_1`:
1. Ensure `temp_file.close()` is called before `os.remove(temp_path)` in `_sync_write` exception handling.
2. Catch `UnicodeDecodeError` in `_sync_read` to handle binary / encoding corruption.
3. Check `if not isinstance(data, dict):` in `_sync_read` to recover from non-dictionary JSON roots.

---

## 5. Verification Method

To independently verify the failure and fixes:

1. **Reproduce Failures**:
   ```powershell
   python -m pytest tests/test_m1_adversarial.py -v
   ```
   **Expected**: 5 failures corresponding to Challenges 1, 2, and 3.

2. **Verification after Worker Applies Fixes**:
   ```powershell
   python -m pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py -v
   ```
   **Pass Condition**: All 99 tests pass with 0 failures and 0 errors.
