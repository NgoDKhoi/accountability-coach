# Analysis Report: Microsecond Backup Timestamp in `src/storage.py`

**Author:** teamwork_preview_explorer (`explorer_m1_r3_2`)  
**Target:** Orchestrator & Worker (`worker_m1_r3`)  
**Date:** 2026-10-03  
**Milestone:** Milestone 1 Iteration 3  
**Scope:** Backup file timestamp resolution in `src/storage.py`

---

## 1. Executive Summary

In `src/storage.py`, when `AtomicJsonStore._sync_read` encounters corrupted, truncated, or unparseable JSON files, it generates a backup file with a timestamp before restoring defaults. Currently, line 114 formats this timestamp as `"%Y%m%d_%H%M%S"`, providing only 1-second resolution. If consecutive corruption events occur within the same second (e.g. during rapid burst writes, power glitch recovery, or tight loop test executions), `datetime.now().strftime("%Y%m%d_%H%M%S")` produces identical file paths. Line 116 executes `os.replace(self.file_path, backup_path)`, which unconditionally overwrites the previous backup file, causing silent loss of forensic and recovery data.

By upgrading the timestamp format to `"%Y%m%d_%H%M%S_%f"`, each backup filename incorporates 6 digits of microsecond resolution, guaranteeing unique backup filenames for consecutive corruptions occurring fractions of a second apart.

---

## 2. Problem Statement & Root Cause Analysis

### 2.1 Code Location
File: `src/storage.py`  
Method: `AtomicJsonStore._sync_read` (lines 107–122)

```python
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            logger.error("Failed to parse %s (%s). Creating backup and re-initializing.", self.file_path, exc)
            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                os.replace(self.file_path, backup_path)
            except OSError:
                pass
            default_data = copy.deepcopy(DEFAULT_DATA)
            self._sync_write(default_data)
            return default_data
```

### 2.2 Mechanism of Failure
1. **Timestamp Granularity Limitation**:
   `"%Y%m%d_%H%M%S"` truncates time to seconds (e.g. `20261003_113645`).
2. **Rapid Failure Scenario**:
   Suppose a corrupted file is detected at `11:36:45.100`. The file is backed up to:
   `records.json.corrupt.20261003_113645`
   Suppose a subsequent read or immediate re-corruption occurs at `11:36:45.300`. The backup path generated is identical:
   `records.json.corrupt.20261003_113645`
3. **Destructive Overwrite via `os.replace`**:
   `os.replace` atomically overwrites existing destination files on both Windows and POSIX. As a result:
   - The backup from the first corruption is permanently destroyed.
   - Only 1 backup file remains on disk instead of 2.
   - Challenger `challenger_m1_r2_2` correctly flagged this in Milestone 1 Iteration 2 (GATE_STATUS.md).

---

## 3. Proposed Fix

### 3.1 Primary Fix: Format Update
In `src/storage.py` line 114, update:

```python
<<<<
            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
====
            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
>>>>
```

### 3.2 Format Breakdown
- `%Y`: 4-digit year (e.g. `2026`)
- `%m`: 2-digit month (`10`)
- `%d`: 2-digit day (`03`)
- `_`: separator
- `%H`: 2-digit hour (`11`)
- `%M`: 2-digit minute (`36`)
- `%S`: 2-digit second (`45`)
- `_`: separator
- `%f`: 6-digit microsecond (`000000`–`999999`)

Example output filename:
`records.json.corrupt.20261003_113645_123456`

### 3.3 Defense-in-Depth Collision Guard (Optional Enhancement)
Under normal execution, `datetime.now()` advances by milliseconds/microseconds between operations. However, in synthetic environments with frozen clocks (`freezegun`), two calls could conceivably have identical microsecond timestamps. To provide 100% mathematical collision immunity:

```python
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = f"{self.file_path}.corrupt.{now_str}"
            if os.path.exists(backup_path):
                counter = 1
                while os.path.exists(f"{backup_path}_{counter}"):
                    counter += 1
                backup_path = f"{backup_path}_{counter}"
```

**Recommendation:** The standard format update `f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"` satisfies the exact gate requirement specified by the orchestrator and challenger. The while-loop counter can optionally be included as defense-in-depth.

---

## 4. Test Suite Impact Analysis

An exhaustive search across the test suite revealed four existing test assertions that inspect backup files:

1. `tests/test_fuzz_storage_config.py` line 378:
   `corrupt_backups = [f for f in files if ".corrupt." in f]`
2. `tests/test_fuzz_storage_config.py` line 402:
   `corrupt_backups = [f for f in os.listdir(temp_data_dir) if ".corrupt." in f]`
3. `tests/test_m1_adversarial.py` line 227:
   `corrupt_backups = [f for f in os.listdir(stress_store.dir_name) if ".corrupt." in f]`
4. `tests/test_m1_adversarial.py` line 239:
   `corrupt_backups = [f for f in os.listdir(stress_store.dir_name) if ".corrupt." in f]`

**Result**: All existing tests check for the substring `".corrupt." in f`. None of them enforce a fixed string length or strict regex matching the old 15-character timestamp. Therefore, upgrading to `%Y%m%d_%H%M%S_%f` will **not** cause any regression in any existing test.

---

## 5. Verification Test Specification

To rigorously verify that consecutive corruptions within the same second generate unique backup files without overwriting, the following test should be added to `tests/test_storage.py` (under `TestStorageCorruptionRecovery`):

```python
    async def test_consecutive_corruptions_within_same_second_create_unique_backups(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        """Verifies consecutive corruptions within the same second generate unique backup files with microseconds."""
        import re

        data_dir = os.path.dirname(str(temp_records_path))

        # First corruption
        temp_records_path.write_text("{corrupt_payload_alpha", encoding="utf-8")
        data1 = await atomic_store.load_data()
        assert data1["streak"]["current_streak"] == 0

        # Second corruption immediately after (within the same second)
        temp_records_path.write_text("{corrupt_payload_beta", encoding="utf-8")
        data2 = await atomic_store.load_data()
        assert data2["streak"]["current_streak"] == 0

        # Verify that TWO distinct .corrupt backup files exist (neither was overwritten)
        corrupt_backups = [f for f in os.listdir(data_dir) if ".corrupt." in f]
        assert len(corrupt_backups) == 2, f"Expected 2 unique backups, found {len(corrupt_backups)}: {corrupt_backups}"

        # Verify microsecond format pattern: .corrupt.YYYYMMDD_HHMMSS_ffffff
        pattern = re.compile(r"^.*\.corrupt\.\d{8}_\d{6}_\d{6}$")
        for backup_name in corrupt_backups:
            assert pattern.match(backup_name), f"Backup filename {backup_name} does not match microsecond format"
```

### Verification Mechanics:
- On the unpatched code (`%Y%m%d_%H%M%S`), the second `load_data()` generates the same filename as the first, calls `os.replace`, and leaves `len(corrupt_backups) == 1`, failing the assertion.
- On the patched code (`%Y%m%d_%H%M%S_%f`), the microsecond component differs, preserving both files and satisfying `len(corrupt_backups) == 2` and the regex check.

---

## 6. Implementation Patch

```diff
--- a/src/storage.py
+++ b/src/storage.py
@@ -111,7 +111,7 @@ class AtomicJsonStore:
                 raise json.JSONDecodeError("JSON root must be an object", "", 0)
         except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
             logger.error("Failed to parse %s (%s). Creating backup and re-initializing.", self.file_path, exc)
-            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
+            backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
             try:
                 os.replace(self.file_path, backup_path)
             except OSError:
```
