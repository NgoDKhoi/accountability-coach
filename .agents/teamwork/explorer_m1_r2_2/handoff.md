# Milestone 1 Iteration 2 Explorer 2 Handoff Report: Storage Read Corruption Recovery Fix

**Author:** teamwork_preview_explorer (`explorer_m1_r2_2`)  
**Recipient:** Orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`)  
**Working Directory:** `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r2_2/`  
**Milestone:** Milestone 1 Iteration 2  
**Date:** 2026-10-03  
**Status:** COMPLETE (Hard Handoff)  

---

## 1. Observation

1. **Assigned Scope (`DISPATCH.md`)**:
   - Formulate the fix for `_sync_read` in `src/storage.py`:
     1. Catch `UnicodeDecodeError` in addition to `json.JSONDecodeError` and `OSError` to handle binary garbage and non-UTF-8 corruption gracefully.
     2. Verify that parsed JSON is a `dict` (`isinstance(raw, dict)`), falling back to default schema if root is non-dict (`list`, `int`, `str`, `None`).

2. **Empirical Defect 1: Unhandled `UnicodeDecodeError` on Binary Garbage**:
   - **File & Line Numbers**: `src/storage.py`, lines 107–110:
     ```python
     107:         try:
     108:             with open(self.file_path, "r", encoding="utf-8") as f:
     109:                 data = json.load(f)
     110:         except (json.JSONDecodeError, OSError) as exc:
     ```
   - **Verbatim Error Output** (`python -m pytest tests/test_m1_adversarial.py`):
     ```text
     FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_binary_garbage
     UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 1: invalid start byte
     ```
   - **Exception Hierarchy**: `UnicodeDecodeError` subclasses `UnicodeError` -> `ValueError` -> `Exception`. It does not inherit from `OSError` or `json.JSONDecodeError`.

3. **Empirical Defect 2: Unhandled `TypeError` on Valid Non-Dict JSON Roots**:
   - **File & Line Numbers**: `src/storage.py`, lines 121–125:
     ```python
     121:         # Enforce presence of all standard schema keys
     122:         for key, val in DEFAULT_DATA.items():
     123:             if key not in data:
     124:                 data[key] = copy.deepcopy(val)
     125:         return data
     ```
   - **Verbatim Error Outputs** (`python -m pytest tests/test_m1_adversarial.py`):
     - For JSON Array `[]`:
       ```text
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_array_root
       TypeError: list indices must be integers or slices, not str
       ```
     - For JSON Null `null`:
       ```text
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_null_root
       TypeError: argument of type 'NoneType' is not a container or iterable
       ```
     - For JSON Number `12345`:
       ```text
       FAILED tests/test_m1_adversarial.py::TestFailureInjectionAndCrashSafety::test_corruption_recovery_on_json_number_root
       TypeError: argument of type 'int' is not a container or iterable
       ```

4. **Challenger Cross-Suite Observations**:
   - In `tests/test_m1_adversarial.py`, Challenger 1 asserted that `load_data()` recovers and returns a valid `dict` with default keys and creates a `.corrupt.` backup file.
   - In `tests/test_fuzz_storage_config.py` (lines 394–436), Challenger 2 wrote proof-of-defect assertions in Iteration 1 expecting `pytest.raises(UnicodeDecodeError)` and `pytest.raises(TypeError)`.

---

## 2. Logic Chain

1. **Exception Handling Gap in UTF-8 Stream Decoding (Observation 2)**:
   - Python's `open(..., encoding="utf-8")` / `json.load()` encounters non-UTF-8 bytes and raises `UnicodeDecodeError`.
   - Because `_sync_read` only intercepts `(json.JSONDecodeError, OSError)`, `UnicodeDecodeError` escapes unhandled.
   - This bypasses the corruption backup and re-initialization block (lines 111–119), causing application crashes on boot or state read.
   - Therefore, adding `UnicodeDecodeError` to the caught exception tuple ensures binary corruptions trigger the self-healing routine.

2. **Semantic Schema Invalidation of Non-Dict Roots (Observation 3)**:
   - Valid JSON syntax permits primitives (`[]`, `null`, `12345`, `"string"`, `true`) at root level per RFC 8259.
   - When parsed, `data` is a `list`, `NoneType`, `int`, etc.
   - Iterating `DEFAULT_DATA` keys against non-dictionary types triggers `TypeError` during membership testing or item assignment.
   - Validating `if not isinstance(data, dict): raise json.JSONDecodeError("JSON root must be an object", "", 0)` inside the `try` block immediately funnels non-dict roots into the existing corruption recovery path without code duplication.

3. **Defense-in-Depth for Sub-Schema Integrity**:
   - In lines 121–125, if `records.json` has a dict root but individual subfields are scalar corruptions (e.g. `{"streak": 123}`), checking type consistency against `DEFAULT_DATA` (`isinstance(val, dict) and not isinstance(data[key], dict)`) prevents subsequent `AttributeError` in caller methods (`get_streak`, `save_data`).

4. **Test Suite Alignment (Observation 4)**:
   - Fixing `_sync_read` causes `test_m1_adversarial.py`'s 4 failing tests to pass.
   - In `test_fuzz_storage_config.py`, the 3 proof-of-defect tests that asserted unpatched exceptions will now succeed rather than raise; their assertions must be updated to expect the healed state.

---

## 3. Caveats

1. **Read-Only Investigation Constraint**: In accordance with the Teamwork explorer persona, no edits have been made to `src/storage.py`. The patch is fully specified below for `worker_m1_1` to apply.
2. **Scope Boundaries**: This report focuses on `_sync_read` in `src/storage.py`. Peer explorer `explorer_m1_r2_1` covers `_sync_write` (Windows file lock on error cleanup), and peer explorer `explorer_m1_r2_3` covers the overall 4-suite regression matrix.
3. **Fuzz Test Suite Updates**: `worker_m1_1` must coordinate with `explorer_m1_r2_3`'s verification plan to update the 3 proof-of-defect tests in `tests/test_fuzz_storage_config.py` from `pytest.raises` to assertions on `load_data()` success.

---

## 4. Conclusion

The fix for `_sync_read` in `src/storage.py` is concise, robust, and completely eliminates the 4 empirical read corruption crashes.

### Actionable Patch Specification for `worker_m1_1`:

Target file: `src/storage.py` (lines 107–125)

```python
<<<<
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to parse %s (%s). Creating backup and re-initializing.", self.file_path, exc)
            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.replace(self.file_path, backup_path)
            except OSError:
                pass
            default_data = copy.deepcopy(DEFAULT_DATA)
            self._sync_write(default_data)
            return default_data

        # Enforce presence of all standard schema keys
        for key, val in DEFAULT_DATA.items():
            if key not in data:
                data[key] = copy.deepcopy(val)
        return data
====
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise json.JSONDecodeError("JSON root must be an object", "", 0)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            logger.error("Failed to parse %s (%s). Creating backup and re-initializing.", self.file_path, exc)
            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.replace(self.file_path, backup_path)
            except OSError:
                pass
            default_data = copy.deepcopy(DEFAULT_DATA)
            self._sync_write(default_data)
            return default_data

        # Enforce presence of all standard schema keys
        for key, val in DEFAULT_DATA.items():
            if key not in data:
                data[key] = copy.deepcopy(val)
            elif isinstance(val, dict) and not isinstance(data[key], dict):
                data[key] = copy.deepcopy(val)
            elif isinstance(val, list) and not isinstance(data[key], list):
                data[key] = copy.deepcopy(val)
        return data
>>>>
```

---

## 5. Verification Method

### 1. Independent Verification Commands
```powershell
# Verify corruption recovery specifically
python -m pytest tests/test_m1_adversarial.py -k "test_corruption_recovery" -v

# Verify entire adversarial suite
python -m pytest tests/test_m1_adversarial.py -v

# Verify unit tests for storage
python -m pytest tests/test_storage.py -v
```

### 2. Files to Inspect
- `src/storage.py`: Lines 107–128
- `tests/test_m1_adversarial.py`: Lines 213–270 (`test_corruption_recovery_*`)
- `tests/test_fuzz_storage_config.py`: Lines 394–436

### 3. Invalidation Conditions
- Any occurrence of unhandled `UnicodeDecodeError` when `records.json` contains raw binary data.
- Any occurrence of `TypeError` when `records.json` contains `[]`, `null`, `12345`, or string scalars.
- Failure to create a `.corrupt.<timestamp>` backup file upon corruption recovery.
