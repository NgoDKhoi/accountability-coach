# Technical Analysis: Windows NTFS Temp File Leak Fix in `src/storage.py` (`_sync_write`)

**Author:** teamwork_preview_explorer (`explorer_m1_r2_1`)  
**Target:** Milestone 1 Iteration 2 (Storage Atomic Persistence Defect Fix)  
**Date:** 2026-10-03  
**Status:** COMPLETE  

---

## 1. Executive Summary

During Milestone 1 challenger evaluation, empirical stress testing on Windows NTFS revealed that `AtomicJsonStore._sync_write` in `src/storage.py` leaks orphaned temporary files (`data/records_*.tmp`) whenever a write failure occurs during JSON serialization (`json.dump`), buffer flushing (`flush`), or disk synchronization (`os.fsync`).

The defect is caused by ordering and error handling in `_sync_write`: `temp_file.close()` was located inside the linear try-block after `os.fsync()`. When any error interrupts the write sequence before line 150, `temp_file.close()` is never reached. In the subsequent `except Exception:` block, `os.remove(temp_path)` is executed against an open file handle, triggering Windows NTFS `PermissionError: [WinError 32]`. Because `except OSError: pass` silently swallows this error, the open temporary file remains on disk indefinitely.

This analysis provides the exact root cause, Windows OS semantics, evaluation of design options, the recommended inner `try...finally` architecture, precise line-by-line patch specification, and cross-test implications.

---

## 2. Root Cause Analysis & Windows NTFS Mechanics

### 2.1 Code Observation in `src/storage.py` (lines 136–159)

```python
136: os.makedirs(self.dir_name, exist_ok=True)
137: temp_file = tempfile.NamedTemporaryFile(
138:     mode="w",
139:     dir=self.dir_name,
140:     prefix="records_",
141:     suffix=".tmp",
142:     delete=False,
143:     encoding="utf-8",
144: )
145: temp_path = temp_file.name
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

### 2.2 NTFS File Locking Mechanics

1. **Windows File Sharing Semantics**:
   - On Windows (NTFS/ReFS/FAT), an open file handle created via standard `open()` or `tempfile.NamedTemporaryFile(delete=False)` holds exclusive delete access unless opened with low-level Windows API flag `FILE_SHARE_DELETE`.
   - Attempting to delete (`os.remove` or `DeleteFileW`) a file with an active unshared handle raises:
     ```text
     PermissionError: [WinError 32] The process cannot access the file because it is being used by another process: '<temp_path>'
     ```
2. **Failure Sequence**:
   - If `json.dump` encounters non-serializable data (raising `TypeError`), or `temp_file.flush()` / `os.fsync()` encounters I/O failure (raising `OSError`), execution immediately jumps to line 152 (`except Exception:`).
   - Line 150 (`temp_file.close()`) is bypassed.
   - Line 155 calls `os.remove(temp_path)`.
   - Windows raises `PermissionError: [WinError 32]`.
   - Lines 156–157 (`except OSError: pass`) catch `PermissionError` (a subclass of `OSError`) and swallow it without logging or action.
   - Line 158 re-raises the original exception (`raise`).
   - The file handle remains open until Python Garbage Collection finalizes the file object. Even after GC closes the handle, the temporary file is already abandoned on disk.
3. **Cumulative Leakage Impact**:
   - In production or long-running daemon mode, recurrent serialization failures or transient write faults accumulate orphaned `records_*.tmp` files in `data/`, consuming disk storage and degrading directory listing performance.

---

## 3. Empirical Test Evidence

Running `python -m pytest tests/test_m1_adversarial.py -v` demonstrates this failure verbatim:

```text
FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_json_dump_preserves_target_file
FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_failure_during_fsync_preserves_target_file

================================== FAILURES ===================================
_ TestFailureInjectionAndCrashSafety.test_failure_during_json_dump_preserves_target_file _
    ...
    # Verify no orphaned temp files
    tmp_files = [f for f in os.listdir(stress_store.dir_name) if f.endswith(".tmp")]
>   assert len(tmp_files) == 0
E   AssertionError: assert 1 == 0
E    +  where 1 = len(['records_r9aszrpk.tmp'])

_ TestFailureInjectionAndCrashSafety.test_failure_during_fsync_preserves_target_file _
    ...
    tmp_files = [f for f in os.listdir(stress_store.dir_name) if f.endswith(".tmp")]
>   assert len(tmp_files) == 0
E   AssertionError: assert 1 == 0
E    +  where 1 = len(['records_8k_oyk1z.tmp'])
```

---

## 4. Design Alternatives Evaluation

Three potential architectures were analyzed:

| Criteria | Design 1: Nested `try...finally` (Recommended) | Design 2: Cleanup in `except Exception` | Design 3: Flag in Single `try...finally` |
|---|---|---|---|
| **Structure** | Inner `try...finally` for handle, outer `try...except` for cleanup | Outer `try...except`, with `temp_file.close()` called inside `except` | Single `try...finally` with boolean `committed` flag |
| **Separation of Concerns** | Clear separation: stream operations vs filesystem rename/cleanup | Mixed: duplicate `temp_file.close()` calls in normal path and except block | Requires auxiliary boolean state variable and conditional logic in finally |
| **Windows NTFS Safety** | 100% Guaranteed: `finally` executes before `os.replace` AND before outer `except` | 100% Guaranteed, but requires nested `try: temp_file.close() except Exception: pass` in except | 100% Guaranteed, but more convoluted flow |
| **Pythonic Elegance** | Standard idiom for resource lifetime management | More verbose and prone to missed branches | Moderate |
| **Alignment with Prompt** | Explicitly matches requirement: "close the temp file handle in finally before os.remove cleanup on failure" | Does not use `finally` for closure before cleanup | Uses `finally` for everything |

---

## 5. Recommended Architecture: Nested `try...finally`

### 5.1 Architecture Details

In this design:
1. `temp_file` is created and opened via `tempfile.NamedTemporaryFile(..., delete=False)`.
2. An outer `try` block wraps the entire write and replace operation, providing failure cleanup (`os.remove`) and re-raising.
3. An inner `try...finally` wraps all stream operations (`json.dump`, `flush`, `fsync`):
   - The inner `finally` block unconditionally calls `temp_file.close()`.
4. `os.replace(temp_path, self.file_path)` is executed only after the inner `try...finally` has completed successfully (at which point `temp_file` is already closed, satisfying Windows atomic rename constraints).
5. If any exception occurs during `json.dump`, `flush`, or `fsync`:
   - The inner `finally` executes and closes `temp_file`.
   - The exception propagates to the outer `except Exception:`.
   - At this moment, `temp_file` is guaranteed closed.
   - `os.remove(temp_path)` succeeds immediately on Windows NTFS without encountering `[WinError 32]`.
   - The exception is re-raised via `raise`.
6. If an exception occurs during `os.replace`:
   - The inner `finally` had already closed `temp_file`.
   - Outer `except Exception:` cleans up `temp_path` and re-raises.

### 5.2 Code Specification

```python
    def _sync_write(self, data: Dict[str, Any]) -> None:
        """Synchronous atomic write protocol:
        1. Ensure directory exists.
        2. Create NamedTemporaryFile in SAME directory (data/).
        3. Write JSON, flush buffer, and fsync to disk.
        4. Close file handle in finally block (guaranteed before os.replace or os.remove).
        5. Atomically replace target file using os.replace.
        6. Clean up temporary file on failure.
        """
        os.makedirs(self.dir_name, exist_ok=True)
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.dir_name,
            prefix="records_",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
        )
        temp_path = temp_file.name
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
```

---

## 6. Impact on Test Suite & Cross-Test Coordination

### 6.1 `tests/test_m1_adversarial.py`
The two failing crash-safety tests:
- `test_failure_during_json_dump_preserves_target_file` (line 162)
- `test_failure_during_fsync_preserves_target_file` (line 183)

Both assert:
```python
tmp_files = [f for f in os.listdir(stress_store.dir_name) if f.endswith(".tmp")]
assert len(tmp_files) == 0
```
With the proposed fix in `_sync_write`, both tests will pass immediately.

### 6.2 `tests/test_fuzz_storage_config.py` (Important Coordination Item!)
In `tests/test_fuzz_storage_config.py` line 438:
```python
    async def test_temp_file_leak_on_serialization_failure(
        self, atomic_store: AtomicJsonStore, temp_data_dir: Path
    ):
        """Stress: check if temp files are leaked on Windows NTFS when json.dump raises TypeError.
        Because temp_file.close() is not in a finally block, the open file handle prevents
        os.remove from deleting the temp file on Windows, leaking an orphaned .tmp file.
        """
        # Non-serializable payload
        with pytest.raises(TypeError):
            await atomic_store.save_data({"unsupported": {1, 2, 3}})

        # Check for lingering .tmp files in data/
        tmp_files = [f for f in os.listdir(temp_data_dir) if f.endswith(".tmp")]
        # On Windows NTFS, exactly 1 orphaned file remains because os.remove failed on open handle
        assert len(tmp_files) == 1
```

**Notice:** `challenger_m1_2` wrote `assert len(tmp_files) == 1` specifically to document the existing defect. Once `worker_m1_1` applies the fix in `_sync_write`:
- `test_temp_file_leak_on_serialization_failure` will produce 0 temporary files (`len(tmp_files) == 0`).
- Therefore, `assert len(tmp_files) == 1` will fail unless updated to `assert len(tmp_files) == 0`.
- The worker must update line 451 in `tests/test_fuzz_storage_config.py` from `assert len(tmp_files) == 1` to `assert len(tmp_files) == 0`.

---

## 7. Actionable Recommendation for `worker_m1_1`

1. **Target File**: `src/storage.py` (lines 146–158)
2. **Apply Patch**: Wrap lines 147–149 in `try...finally: temp_file.close()`, followed by `os.replace(temp_path, self.file_path)` outside the inner try-finally, keeping outer `except Exception:` for `os.remove` cleanup.
3. **Align Challenger Test**: Update `tests/test_fuzz_storage_config.py:451` from `assert len(tmp_files) == 1` to `assert len(tmp_files) == 0`.
4. **Run Verification Command**:
   ```powershell
   python -m pytest tests/test_storage.py tests/test_m1_adversarial.py tests/test_fuzz_storage_config.py -v
   ```
