# Milestone 1 Iteration 2 Explorer Handoff: _sync_write Handle Closure Analysis

**Author:** teamwork_preview_explorer (`explorer_m1_r2_1`)  
**Recipient:** Orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`)  
**Working Directory:** `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_1/`  
**Milestone:** Milestone 1 Iteration 2  
**Date:** 2026-10-03  
**Status:** COMPLETE (Hard Handoff)  

---

## 1. Observation

1. **Test Failure Verbatim Observation (`tests/test_m1_adversarial.py`)**:
   - Command: `python -m pytest tests/test_m1_adversarial.py -v`
   - Results:
     ```text
     FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_json_dump_preserves_target_file
     FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_fsync_preserves_target_file

     AssertionError: assert 1 == 0
      +  where 1 = len(['records_r9aszrpk.tmp'])
     ```
2. **Current Implementation in `src/storage.py` (lines 146–158)**:
   ```python
   146: try:
   147:     json.dump(data, temp_file, indent=2, ensure_ascii=False)
   148:     temp_file.flush()
   149:     os.fsync(temp_file.fileno())
   150:     temp_file.close()  # CRITICAL: releases Windows handle lock
   151:     os.replace(temp_path, self.file_path)
   152: except Exception:
   153:     if os.path.exists(temp_path):
   154:         try:
   155:             os.remove(temp_path)
   156:         except OSError:
   157:             pass
   158:     raise
   ```
3. **OS Behavior on Windows NTFS**:
   - When an unhandled exception occurs in lines 147–149 (`json.dump`, `flush`, `fsync`), execution branches directly to line 152 (`except Exception:`).
   - Line 150 (`temp_file.close()`) is bypassed, leaving the file descriptor open in the Python process.
   - Line 155 (`os.remove(temp_path)`) attempts deletion on Windows NTFS. Because Windows prohibits deleting files with active unshared handles, this raises `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
   - Lines 156–157 (`except OSError: pass`) catch `PermissionError` and suppress it.
   - Line 158 re-raises the initial exception, leaving an orphaned `records_*.tmp` file in the directory.
4. **Fuzz Test Observation in `tests/test_fuzz_storage_config.py` (lines 448–451)**:
   - `challenger_m1_2` wrote `test_temp_file_leak_on_serialization_failure` asserting `assert len(tmp_files) == 1` to document this existing defect under unpatched code.

---

## 2. Logic Chain

1. **Resource Lifetime & Scoping (Observations 1 & 2)**:
   - On Windows, file deletion (`os.remove`) and atomic replacement (`os.replace`) require that the file handle is closed.
   - To guarantee that `temp_file.close()` runs before `os.remove(temp_path)` in the exception handler, the file handle must be closed in a `finally` block of an inner `try...finally` enclosing `json.dump`, `flush`, and `fsync`.
2. **Exception Propagation Guarantee (Observation 3)**:
   - By nesting `try...finally` inside the outer `try...except Exception:`, any exception raised during serialization or I/O executes `finally: temp_file.close()` before the exception bubbles to the outer `except Exception:`.
   - When the outer `except Exception:` block executes `os.remove(temp_path)`, the handle is already closed. Windows NTFS deletes the temporary file without `[WinError 32]`.
   - The original exception propagates cleanly via `raise`.
3. **Cross-Test Synchronization Requirement (Observation 4)**:
   - When the fix is implemented, `len(tmp_files)` on write failure becomes 0 instead of 1.
   - Consequently, `tests/test_m1_adversarial.py` will pass, but `tests/test_fuzz_storage_config.py:451` must be updated from `assert len(tmp_files) == 1` to `assert len(tmp_files) == 0`.

---

## 3. Caveats

- **Scope Delimitation**: This analysis is focused strictly on the `_sync_write` temporary file cleanup defect on Windows NTFS.
- **Other Iteration 2 Defects**: Recovery from binary corruption (`UnicodeDecodeError`) and non-dict JSON roots (`isinstance(data, dict)`) in `_sync_read` are documented in peer analysis / challenger reports and must be implemented concurrently by `worker_m1_1`.
- **Read-Only Explorer Constraint**: In accordance with the Explorer archetype rules, no changes have been committed directly to `src/storage.py` or `tests/`. Implementation is delegated to `worker_m1_1`.

---

## 4. Conclusion

The fix for `_sync_write` in `src/storage.py` must adopt a nested `try...finally` pattern that guarantees handle closure before `os.replace` on the success path and before `os.remove` on the failure path:

### Concrete Code Replacement for `src/storage.py` (lines 146–158):

```python
<<<<
        try:
            json.dump(data, temp_file, indent=2, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()  # CRITICAL: releases Windows handle lock
            os.replace(temp_path, self.file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
====
        try:
            try:
                json.dump(data, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            finally:
                temp_file.close()  # CRITICAL: releases Windows handle lock before replace or cleanup

            os.replace(temp_path, self.file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise
>>>>
```

---

## 5. Verification Method

1. **Code Inspection**:
   - Inspect `src/storage.py` to confirm `temp_file.close()` is inside `finally:` prior to `os.replace` and outer `except Exception:`.
2. **Run Adversarial Crash Safety Tests**:
   ```powershell
   python -m pytest tests/test_m1_adversarial.py -k "test_failure_during_json_dump or test_failure_during_fsync" -v
   ```
   **Pass Condition**: Both tests pass with 0 orphaned `.tmp` files.
3. **Run Fuzzing Suite after Assertion Alignment**:
   ```powershell
   python -m pytest tests/test_fuzz_storage_config.py -k "test_temp_file_leak_on_serialization_failure" -v
   ```
   **Pass Condition**: Passes with `assert len(tmp_files) == 0`.
4. **Invalidation Conditions**:
   - Any `.tmp` file remains in `data/` or `temp_dir` after a simulated write failure.
   - Any `PermissionError: [WinError 32]` encountered during temp file removal.
