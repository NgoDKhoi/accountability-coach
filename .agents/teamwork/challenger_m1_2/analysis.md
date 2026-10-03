# Adversarial Stress Test & Fuzzing Analysis: Milestone 1

**Author:** teamwork_preview_challenger (`challenger_m1_2`)  
**Target:** Milestone 1 Deliverables (`src/config.py`, `src/storage.py`)  
**Date:** 2026-10-03  
**Verdict:** `REQUEST_CHANGES`

---

## 1. Executive Summary

As the Empirical Challenger for Milestone 1, I constructed and executed an adversarial test harness (`tests/test_fuzz_storage_config.py`, 82 test cases) designed to find breaking points in configuration loading (`load_config`) and atomic storage recovery (`AtomicJsonStore`).

While `load_config` demonstrated exceptional defensive robustness across all boundary and malformed inputs, empirical fuzzing uncovered **3 reproducible bugs** in `AtomicJsonStore`'s corruption recovery and cleanup protocols on Windows NTFS:
1. **Unhandled `UnicodeDecodeError` on binary file corruption** (`_sync_read` misses `UnicodeDecodeError`).
2. **Unhandled `TypeError` crash on valid non-dict JSON roots** (`[]`, `123`, `null`).
3. **Leaked orphaned `.tmp` files on Windows NTFS** when serialization fails (file handle unclosed before `os.remove`).

---

## 2. Methodology & Test Harness

A dedicated empirical test module was created at `tests/test_fuzz_storage_config.py` covering:
- Malformed and extreme environment variables (`ALLOWED_CHAT_ID`, empty/whitespace secrets, embedded null characters).
- Corrupted and non-standard YAML configurations (unquoted sexagesimal times, non-dict roots, missing sections, broken syllabus lists, negative durations).
- Storage failure modes: zero-byte files, truncated syntax, binary garbage, non-dict JSON roots, schema key omission, high concurrency (60 tasks), and Windows NTFS handle lifecycle.

All tests were executed against Python 3.14.4 on Windows NT using `pytest`:
- Existing Worker Suite (`tests/test_config.py`, `tests/test_storage.py`): **77 passed**
- Challenger Adversarial Suite (`tests/test_fuzz_storage_config.py`): **82 passed** (validating boundary resistance and capturing defect behaviors)

---

## 3. Boundary Fuzzing Results: `load_config`

### 3.1 Environment Variable Fuzzing
| Test Scenario | Input | Expected | Actual | Status |
|---|---|---|---|---|
| Malformed chat ID strings | `"🤖_bot"`, `"12345abc"`, `"123-456"`, `"id:12345"` | `ValueError: ALLOWED_CHAT_ID` | Raised `ValueError` | **PASS** |
| Floats and scientific notation | `"123.456"`, `"1e5"`, `"NaN"`, `"Infinity"` | `ValueError: ALLOWED_CHAT_ID` | Raised `ValueError` | **PASS** |
| SQL/Shell injection attempts | `"' OR 1=1 --"`, `"12345;rm -rf /"` | `ValueError: ALLOWED_CHAT_ID` | Raised `ValueError` | **PASS** |
| Embedded null character in `.env` | `b"ALLOWED_CHAT_ID=12345\x00extra"` | `ValueError` | Raised `ValueError` | **PASS** |
| Negative Telegram Chat IDs | `"-1001234567890"`, `"-1"` | Parsed as negative `int` | Accepted `-1001234567890` | **PASS** |
| Extreme integer boundaries | `"10000000000000000000000000"` ($10^{25}$) | Parsed as `int` | Accepted without overflow | **PASS** |
| Missing or whitespace tokens | `"   "`, `"\t\t"`, `"\n\r"`, `""` | `ValueError` naming variable | Raised `ValueError` | **PASS** |

### 3.2 YAML Schema Fuzzing
| Test Scenario | Input | Expected | Actual | Status |
|---|---|---|---|---|
| Non-dict YAML root | Primitives: `42`, `"just a string"`, `true`, `null`, list `["a", "b"]` | `ValueError: empty or invalid` | Raised `ValueError` | **PASS** |
| Non-mapping subsections | `app: "not a dict"`, `limits: [1,2,3]`, `gym: "str"` | `ValueError` | Raised `ValueError` | **PASS** |
| Invalid Timezones | `"Mars/Phobos"`, `"Invalid/TZ"`, `"GMT+99"`, `""` | `ValueError: Invalid timezone` | Raised `ValueError` | **PASS** |
| Invalid Time Formats | `"24:00"`, `"00:60"`, `"-01:00"`, `"9:00"`, `"12:00:00"`, `"noon"` | `ValueError: HH:MM format` | Raised `ValueError` | **PASS** |
| Unquoted sexagesimal YAML time | `time_split1: 17:15` (parsed as `int` 1035 in YAML 1.1) | `ValueError: must be a string` | Raised `ValueError` | **PASS** |
| Broken TOEIC syllabus rotation | Lengths: `0`, `1`, `6`, `8` items | `ValueError: exactly 7 items` | Raised `ValueError` | **PASS** |
| Zero or negative durations | `duration_minutes: 0`, `-10`, `-60` | `ValueError: duration_minutes must be > 0` | Raised `ValueError` | **PASS** |

**Conclusion on `load_config`**: The config loader is rock-solid and gracefully rejects all boundary fuzz inputs.

---

## 4. Empirical Vulnerabilities Found: `AtomicJsonStore`

### ⚠️ Finding 1 (Severity: MEDIUM-HIGH): Unhandled `UnicodeDecodeError` on Binary Corruption
- **Location**: `src/storage.py`, lines 107–119:
  ```python
  try:
      with open(self.file_path, "r", encoding="utf-8") as f:
          data = json.load(f)
  except (json.JSONDecodeError, OSError) as exc:
      logger.error("Failed to parse %s (%s). Creating backup and re-initializing.", ...)
      ...
  ```
- **Attack Scenario**: If `data/records.json` undergoes bit-flips or contains non-UTF-8 bytes (e.g. `b"\x00\xff\xfe\x01\x02\x03"`), Python's stream decoder raises `UnicodeDecodeError`.
- **Root Cause**: `UnicodeDecodeError` inherits from `ValueError`, **not** from `OSError` and **not** from `json.JSONDecodeError`. The `except (json.JSONDecodeError, OSError)` clause does not catch it.
- **Empirical Proof**: In `tests/test_fuzz_storage_config.py::TestStorageStressAndRecovery::test_binary_garbage_handling`, `load_data()` crashed with unhandled `UnicodeDecodeError` instead of falling back to default data and creating a backup.
- **Blast Radius**: Store becomes completely inoperable upon binary corruption until a developer manually deletes the file.
- **Mitigation**: Update exception tuple to:
  ```python
  except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
  ```
  or simply `except (ValueError, OSError) as exc:` (since both `JSONDecodeError` and `UnicodeDecodeError` subclass `ValueError`).

---

### ⚠️ Finding 2 (Severity: MEDIUM): Unhandled `TypeError` Crash on Non-Dict JSON Roots
- **Location**: `src/storage.py`, lines 122–125:
  ```python
  # Enforce presence of all standard schema keys
  for key, val in DEFAULT_DATA.items():
      if key not in data:
          data[key] = copy.deepcopy(val)
  return data
  ```
- **Attack Scenario**: If `data/records.json` is modified or corrupted to contain valid JSON that is not an object (e.g. `[]`, `123`, `null`, `true`, `"string"`):
  - If `data` is `[]`: `key not in data` evaluates to `False`, then `data["version"] = 1` crashes with:
    `TypeError: list indices must be integers or slices, not str`.
  - If `data` is `123`, `null`, or `true`: `key not in data` crashes with:
    `TypeError: argument of type 'int' is not a container or iterable`.
- **Root Cause**: `_sync_read` assumes that if `json.load()` succeeds, `data` is a `dict`. It never validates `isinstance(data, dict)`.
- **Empirical Proof**: Verified in `test_json_array_root_behavior` and `test_json_scalar_root_behavior`.
- **Blast Radius**: The store crashes on boot and cannot self-heal from non-object JSON.
- **Mitigation**: Add a type check right after `json.load(f)`:
  ```python
  if not isinstance(data, dict):
      raise json.JSONDecodeError("Root JSON structure must be an object", "", 0)
  ```

---

### ⚠️ Finding 3 (Severity: LOW-MEDIUM): Leaked Orphaned `.tmp` Files on Windows NTFS
- **Location**: `src/storage.py`, lines 137–158:
  ```python
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
      json.dump(data, temp_file, indent=2, ensure_ascii=False)
      temp_file.flush()
      os.fsync(temp_file.fileno())
      temp_file.close()  # Line 150
      os.replace(temp_path, self.file_path)
  except Exception:
      if os.path.exists(temp_path):
          try:
              os.remove(temp_path)
          except OSError:
              pass
      raise
  ```
- **Attack Scenario**: If `data` contains an un-serializable object (e.g. a `set`, lambda, or circular reference), `json.dump` raises `TypeError`. Line 150 (`temp_file.close()`) is skipped.
- **Root Cause**: On Windows NTFS, an open file handle cannot be deleted with `os.remove`. Calling `os.remove(temp_path)` in `except Exception:` raises `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`. The inner `except OSError: pass` suppresses this error, leaving the `.tmp` file permanently on disk.
- **Empirical Proof**: Verified in `test_temp_file_leak_on_serialization_failure`: `len(tmp_files) == 1` confirms an orphaned `.tmp` file remains in `data/`.
- **Blast Radius**: Slow disk leak if malformed data is repeatedly passed to `save_data`.
- **Mitigation**: Explicitly close `temp_file` in a `finally` block or inside `except Exception:` before calling `os.remove`:
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

### ℹ️ Finding 4 (Severity: LOW): Malformed Internal Sub-structures (`streak: null`, `sessions: null`)
- **Location**: `src/storage.py`, lines 180, 208, 248.
- **Observation**: If `data["streak"] = None` or `data["sessions"] = None` exists in disk JSON, `_sync_read`'s `for key, val in DEFAULT_DATA.items(): if key not in data:` check passes because the key exists, but subsequent calls to `.get()` or `.setdefault()` raise `AttributeError: 'NoneType' object has no attribute 'get'`.
- **Mitigation**: Ensure `if not isinstance(data.get("streak"), dict): data["streak"] = copy.deepcopy(DEFAULT_DATA["streak"])` and similarly for `sessions` and `history`.

---

## 5. Summary Table & Final Verdict

| Component | Test Area | Assessment | Required Action |
|---|---|---|---|
| `src/config.py` | Boundary Fuzzing | **EXCELLENT** | None. Fully verified. |
| `src/storage.py` | Zero-byte File Recovery | **EXCELLENT** | None. Fully verified. |
| `src/storage.py` | Truncated Syntax Recovery | **EXCELLENT** | None. Fully verified. |
| `src/storage.py` | Concurrency & Streak Rules | **EXCELLENT** | None. Fully verified (60 concurrent ops). |
| `src/storage.py` | Binary Corruption Recovery | **FAILED** | Catch `UnicodeDecodeError` in `_sync_read`. |
| `src/storage.py` | Non-dict Root Recovery | **FAILED** | Validate `isinstance(data, dict)` in `_sync_read`. |
| `src/storage.py` | NTFS Temp File Cleanup | **FAILED** | Close `temp_file` before `os.remove` on write errors. |

**Final Verdict**: `REQUEST_CHANGES`  
Worker `worker_m1_1` must apply the 3 quick fixes to `src/storage.py` to ensure complete crash resilience.
