# Unified Test Verification Execution Plan & Analysis (181 Tests)

**Author:** teamwork_preview_explorer (`explorer_m1_r3_3`)  
**Target:** Orchestrator (`ac41226a-6cc6-45bc-9027-605104e502f4`)  
**Scope:** Milestone 1 Iteration 3 — Complete Unified Test Verification Execution Plan  
**Working Directory:** `c:/Users/khoi1/Documents/antigravity/serene-bohr/.agents/teamwork/explorer_m1_r3_3/`  
**Date:** 2026-10-03  

---

## 1. Executive Summary

Milestone 1 encompasses a total of **181 automated tests** across four test modules:
1. `tests/test_config.py` (44 tests)
2. `tests/test_storage.py` (33 tests)
3. `tests/test_m1_adversarial.py` (22 tests)
4. `tests/test_fuzz_storage_config.py` (82 tests)

In Iteration 2, executing these test suites in isolation passed 100%, but executing the unified test verification command:
```powershell
python -m pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py tests/test_fuzz_storage_config.py -v
```
resulted in `1 failed, 180 passed in 46.89s`.

This analysis provides a comprehensive, rigorous execution plan ensuring that all 181 tests execute sequentially and in isolation, completely eliminating cross-test environmental pollution, race conditions, file descriptor leaks, and timing anomalies, thereby guaranteeing a 100% pass rate.

---

## 2. Test Suite Inventory & Exact Test Count Breakdown

A granular inspection of the test codebase confirms the exact distribution of the 181 tests:

### 2.1. `tests/test_config.py` (44 Tests)
Validates configuration loading, YAML parsing, schema enforcement, secret masking, and environment variable fallbacks.

| Class | Method | Parameters / Cases | Test Count |
|---|---|---|---|
| `TestLoadConfigSuccess` | `test_load_config_valid_files` | Single run with valid YAML + `.env` | 1 |
| `TestLoadConfigSuccess` | `test_app_config_immutability` | FrozenInstanceError assertion | 1 |
| `TestLoadConfigSuccess` | `test_default_values_when_yaml_app_omitted` | Default values verification | 1 |
| `TestLoadConfigSuccess` | `test_load_config_from_os_environ_directly` | Direct `os.environ` reading | 1 |
| `TestEnvValidation` | `test_allowed_chat_id_whitespace_handling` | 4 whitespace variations | 1 |
| `TestEnvValidation` | `test_allowed_chat_id_invalid_values` | 8 invalid IDs (`""`, `"abc"`, `"123.456"`, `"0"`, `"None"`, `"undefined"`, `"true"`, `"0x1A"`) | 8 |
| `TestEnvValidation` | `test_missing_required_env_vars` | 3 variables (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`) | 3 |
| `TestEnvValidation` | `test_empty_env_vars` | 3 variables (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`) | 3 |
| `TestYamlValidation` | `test_missing_yaml_file` | Missing file raises `FileNotFoundError` | 1 |
| `TestYamlValidation` | `test_invalid_yaml_syntax` | Bad tab indentation raises `ValueError` | 1 |
| `TestYamlValidation` | `test_empty_yaml_file` | Empty file raises `ValueError` | 1 |
| `TestYamlValidation` | `test_missing_schedules_section` | Missing `schedules` section | 1 |
| `TestYamlValidation` | `test_missing_schedule_subsections` | 3 subsections (`gym`, `toeic`, `major`) | 3 |
| `TestYamlValidation` | `test_toeic_syllabus_rotation_length` | 5 invalid lengths (`0`, `5`, `6`, `8`, `14`) | 5 |
| `TestYamlValidation` | `test_toeic_rotation_from_dict` | Rotation passed as dict | 1 |
| `TestYamlValidation` | `test_invalid_time_formats` | 6 malformed times (`24:00`, `25:30`, `12:60`, `9:00`, `invalid`, `17:15:00`) | 6 |
| `TestYamlValidation` | `test_invalid_timezone` | Nonexistent timezone string | 1 |
| `TestYamlValidation` | `test_invalid_numeric_limits` | 3 invalid numeric limits | 3 |
| `TestHelpers` | `test_mask_secret` | Secret string truncation and masking | 1 |
| `TestHelpers` | `test_schedule_properties_and_helpers` | Cron and property helper validation | 1 |
| **Total `test_config.py`** | | | **44** |

### 2.2. `tests/test_storage.py` (33 Tests)
Validates core atomic persistence, file creation, lock contention, streak calculation, streak expiry, and session status transitions.

| Class | Method | Focus | Test Count |
|---|---|---|---|
| `TestAtomicWriteBasics` | `test_auto_create_parent_directory` | Directory creation on init | 1 |
| `TestAtomicWriteBasics` | `test_load_data_when_file_does_not_exist` | Empty store auto-population | 1 |
| `TestAtomicWriteBasics` | `test_get_streak_when_file_does_not_exist` | Initial streak defaults | 1 |
| `TestAtomicWriteBasics` | `test_atomic_write_creates_valid_file` | Atomic save operation | 1 |
| `TestAtomicWriteBasics` | `test_atomic_write_cleans_up_temporary_files` | Zero temp file residue | 1 |
| `TestAtomicWriteBasics` | `test_crash_safety_on_serialization_error` | Non-serializable payload safety | 1 |
| `TestAtomicWriteBasics` | `test_crash_safety_on_os_replace_failure` | Target replacement failure safety | 1 |
| `TestAtomicWriteBasics` | `test_concurrent_writes_thread_safe` | Basic lock concurrency safety | 1 |
| `TestStreakProgression` | `test_first_ever_session_completion` | Day 1 completion streak = 1 | 1 |
| `TestStreakProgression` | `test_consecutive_days_progression` | Day 1 -> Day 2 -> Day 3 streak increment | 1 |
| `TestStreakProgression` | `test_multi_session_same_day_idempotency` | Multiple sessions in 1 calendar day | 1 |
| `TestStreakProgression` | `test_duplicate_session_completion_idempotency` | Re-completing identical session ID | 1 |
| `TestStreakProgression` | `test_broken_streak_reset_to_one_after_gap` | 1-day missed reset to 1 | 1 |
| `TestStreakProgression` | `test_large_gap_streak_reset` | Multi-month gap streak reset | 1 |
| `TestStreakProgression` | `test_new_best_streak_record` | `best_streak` update logic | 1 |
| `TestStreakProgression` | `test_month_boundary_progression` | Jan 31 -> Feb 01 streak continuity | 1 |
| `TestStreakProgression` | `test_year_boundary_progression` | Dec 31 -> Jan 01 streak continuity | 1 |
| `TestStreakProgression` | `test_leap_year_boundary_progression` | Feb 28 -> Feb 29 -> Mar 01 continuity | 1 |
| `TestStreakProgression` | `test_effective_streak_expiry` | Expired streak after 48 hours | 1 |
| `TestSessionManagement` | `test_get_session_status_unknown` | Unknown session query returns None | 1 |
| `TestSessionManagement` | `test_record_completion_persists_session` | Session status and history entry | 1 |
| `TestSessionManagement` | `test_record_snooze_increments` | Snooze count increment | 1 |
| `TestSessionManagement` | `test_snooze_then_completed` | Snooze -> Completed transition | 1 |
| `TestSessionManagement` | `test_record_skip_excuse` | Skip with excuse status | 1 |
| `TestSessionManagement` | `test_record_skip_legitimate` | Skip with legitimate obstacle | 1 |
| `TestSessionManagement` | `test_skip_does_not_increment_streak` | Streak preservation on skip | 1 |
| `TestSessionManagement` | `test_multiple_independent_sessions_same_day` | Gym, TOEIC, Major on same day | 1 |
| `TestSessionManagement` | `test_awaiting_reason_lifecycle` | Setting and clearing reason state | 1 |
| `TestSessionManagement` | `test_get_recent_history` | History ordering and limit | 1 |
| `TestCorruptionAndRecovery` | `test_empty_file_recovery` | 0-byte file recovery | 1 |
| `TestCorruptionAndRecovery` | `test_corrupted_json_syntax_recovery` | Syntax-corrupted file recovery | 1 |
| `TestCorruptionAndRecovery` | `test_store_reset` | Store reset to blank defaults | 1 |
| `TestCorruptionAndRecovery` | `test_out_of_order_date_streak_handling` | Retroactive completion handling | 1 |
| **Total `test_storage.py`** | | | **33** |

### 2.3. `tests/test_m1_adversarial.py` (22 Tests)
Validates high concurrency (100 concurrent writes), fault injection during dump/fsync/replace, leap year/year-boundary streaks, and adversarial time strings.

| Class | Method | Stress Target | Test Count |
|---|---|---|---|
| `TestHighConcurrencyStress` | `test_100_concurrent_completions_same_day` | 100 concurrent async completions | 1 |
| `TestHighConcurrencyStress` | `test_100_concurrent_mixed_operations` | 100 concurrent mixed ops (complete/snooze/skip) | 1 |
| `TestHighConcurrencyStress` | `test_multi_instance_file_safety` | 5 separate store instances on 1 file | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_failure_during_json_dump_preserves_target_file` | Mock json.dump failure | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_failure_during_fsync_preserves_target_file` | Mock os.fsync failure | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_failure_during_os_replace_preserves_target_file` | Mock os.replace failure | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_corruption_recovery_on_truncated_json` | Incomplete JSON recovery | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_corruption_recovery_on_binary_garbage` | Binary non-UTF8 recovery | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_corruption_recovery_on_json_array_root` | `[]` root recovery | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_corruption_recovery_on_json_null_root` | `null` root recovery | 1 |
| `TestCrashAndCorruptionFaultInjection` | `test_corruption_recovery_on_json_number_root` | `12345` root recovery | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_365_days_continuous_progression` | 365 daily completions loop | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_leap_year_transition_progression` | 2024 leap year sequence | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_non_leap_year_transition_progression` | 2023 non-leap year sequence | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_year_boundary_transition_progression` | Dec 31 to Jan 01 boundary | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_multiple_gap_streak_resets_preserve_all_time_best` | Repeated resets and best streak | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_out_of_order_past_date_completion_does_not_corrupt_streak` | Historical date completion | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_timezone_midnight_boundary_behavior` | Asia/Ho_Chi_Minh midnight edge | 1 |
| `TestCalendarEdgeCasesAndStreaks` | `test_streak_data_effective_streak_comprehensive` | Datetime boundary expiry matrix | 1 |
| `TestConfigAdversarialInputs` | `test_extreme_time_values` | 6 extreme time formats | 1 |
| `TestConfigAdversarialInputs` | `test_non_string_time` | Integer passed as time | 1 |
| `TestConfigAdversarialInputs` | `test_empty_string_time` | Empty string passed as time | 1 |
| **Total `test_m1_adversarial.py`** | | | **22** |

### 2.4. `tests/test_fuzz_storage_config.py` (82 Tests)
Validates adversarial boundary fuzzing and storage stress recovery.

| Class | Method | Parameters / Fuzz Cases | Test Count |
|---|---|---|---|
| `TestConfigBoundaryFuzzing` | `test_malformed_allowed_chat_id_rejected` | 19 malformed strings (`🤖_bot`, `NaN`, SQLi, etc.) | 19 |
| `TestConfigBoundaryFuzzing` | `test_null_char_in_dotenv_file` | Embedded null character byte in `.env` | 1 |
| `TestConfigBoundaryFuzzing` | `test_extreme_and_negative_chat_ids` | 4 extreme integers (`-1001234567890`, `10**25`, etc.) | 4 |
| `TestConfigBoundaryFuzzing` | `test_empty_or_whitespace_tokens` | 4 whitespace token strings | 4 |
| `TestConfigBoundaryFuzzing` | `test_yaml_non_dict_root_rejected` | 5 non-dict YAML roots (`42`, `true`, `null`, lists) | 5 |
| `TestConfigBoundaryFuzzing` | `test_yaml_malformed_section_types` | 6 malformed YAML sections | 6 |
| `TestConfigBoundaryFuzzing` | `test_invalid_timezones_rejected` | 6 invalid timezones (`Mars/Phobos`, `UTC+07:00`, etc.) | 6 |
| `TestConfigBoundaryFuzzing` | `test_validate_time_format_boundaries` | 12 boundary time formats (`24:00`, `noon`, etc.) | 12 |
| `TestConfigBoundaryFuzzing` | `test_unquoted_yaml_sexagesimal_time` | Unquoted sexagesimal integer in YAML 1.1 | 1 |
| `TestConfigBoundaryFuzzing` | `test_broken_toeic_syllabus_rotations` | 6 invalid TOEIC rotations | 6 |
| `TestConfigBoundaryFuzzing` | `test_negative_or_zero_durations` | 6 negative / zero durations | 6 |
| `TestStorageStressAndRecovery` | `test_zero_byte_file_recovery_and_write` | Auto-healing 0-byte file | 1 |
| `TestStorageStressAndRecovery` | `test_truncated_json_file_recovery` | Auto-healing truncated JSON + backup | 1 |
| `TestStorageStressAndRecovery` | `test_whitespace_only_file_recovery` | Auto-healing whitespace file | 1 |
| `TestStorageStressAndRecovery` | `test_binary_garbage_handling` | Auto-healing binary bytes + backup | 1 |
| `TestStorageStressAndRecovery` | `test_missing_nested_keys_schema_auto_heal` | Adding missing root keys | 1 |
| `TestStorageStressAndRecovery` | `test_json_array_root_behavior` | Auto-healing `[]` root to dict | 1 |
| `TestStorageStressAndRecovery` | `test_json_scalar_root_behavior` | Auto-healing `123` scalar root to dict | 1 |
| `TestStorageStressAndRecovery` | `test_temp_file_leak_on_serialization_failure` | Assert zero lingering `.tmp` files | 1 |
| `TestStorageStressAndRecovery` | `test_high_concurrency_mixed_operations` | 60 concurrent tasks across operations | 1 |
| `TestStorageStressAndRecovery` | `test_streak_boundary_year_transition` | Dec 31 to Jan 01 streak | 1 |
| `TestStorageStressAndRecovery` | `test_streak_boundary_leap_year` | Feb 28 to Mar 01 leap year streak | 1 |
| `TestStorageStressAndRecovery` | `test_streak_effective_expiry_calculation` | Calendar streak expiry | 1 |
| **Total `test_fuzz_storage_config.py`** | | | **82** |

### 2.5. Grand Total Verification
$$\text{Grand Total} = 44 + 33 + 22 + 82 = \mathbf{181\text{ tests}}$$

---

## 3. Root Cause Analysis: Cross-Test Environment Pollution

### 3.1. Mechanism of Failure
Under sequential execution of the entire test suite in a single Python process:
1. `tests/test_config.py` runs first.
   - `test_load_config_valid_files` calls `load_config(..., env_path=str(temp_env_file))`.
   - `src/config.py` lines 238–239 invokes:
     ```python
     if env_path and os.path.isfile(env_path):
         load_dotenv(dotenv_path=env_path, override=False)
     ```
   - Python `dotenv` populates `os.environ["ALLOWED_CHAT_ID"] = "123456789"`.
   - Because `test_load_config_valid_files` does not use `monkeypatch` or `clean_env`, the environment variable persists in `os.environ` throughout the lifetime of the process.
2. `tests/test_storage.py` and `tests/test_m1_adversarial.py` run next.
   - Neither suite interacts with `os.environ`.
3. `tests/test_fuzz_storage_config.py` runs fourth.
   - `TestConfigBoundaryFuzzing::test_null_char_in_dotenv_file` (lines 76–86) creates an `.env` file containing:
     `ALLOWED_CHAT_ID=12345\x00extra\n`
   - It calls `load_config(str(temp_config_yaml_file), env_path=str(env_file))`.
   - Because `test_null_char_in_dotenv_file` **omitted** `clean_env: None`, `os.environ["ALLOWED_CHAT_ID"]` still equals `"123456789"`.
   - Because `load_dotenv` is executed with `override=False`, `dotenv` **skips** setting `ALLOWED_CHAT_ID` since it already exists in `os.environ`.
   - `load_config` reads `raw_chat_id = os.environ.get("ALLOWED_CHAT_ID")` -> `"123456789"`.
   - `int("123456789")` succeeds! No `ValueError` is raised!
   - `pytest.raises(ValueError, match="embedded null|ALLOWED_CHAT_ID")` fails with `Failed: DID NOT RAISE ValueError`.

### 3.2. Reproduction Matrix

| Execution Order / Scope | Result | Root Cause |
|---|---|---|
| `pytest tests/test_fuzz_storage_config.py` | **82 PASSED** | Standalone run: `ALLOWED_CHAT_ID` was not previously present in `os.environ`. `load_dotenv` loaded `12345\x00extra`. `int()` failed with `ValueError`. |
| `pytest tests/test_config.py tests/test_storage.py` | **77 PASSED** | Suites do not cross-pollute each other. |
| `pytest tests/test_m1_adversarial.py` | **22 PASSED** | Independent stress fixtures (`mkdtemp`). |
| `pytest tests/test_config.py ... tests/test_fuzz_storage_config.py` (Unified) | **1 FAILED, 180 PASSED** | `ALLOWED_CHAT_ID` leaked from `test_config.py` into `test_null_char_in_dotenv_file`. |

---

## 4. Prerequisites for 100% Unified Verification

Two concrete code changes (being formulated by Explorer 1 and Explorer 2) must be in place before executing the unified verification command:

### 4.1. Fix 1: Environment Isolation in `tests/test_fuzz_storage_config.py`
In `tests/test_fuzz_storage_config.py`, line 76:
Add `clean_env: None` to `test_null_char_in_dotenv_file`:
```python
    def test_null_char_in_dotenv_file(
        self,
        tmp_path: Path,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        clean_env: None,
    ):
```
**Mechanism**:
`clean_env` invokes `monkeypatch.delenv(var, raising=False)` for `ALLOWED_CHAT_ID`, `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, etc.
When `load_config` is called, `os.environ["ALLOWED_CHAT_ID"]` is empty. `load_dotenv` parses `env_file`, populates `12345\x00extra`, which fails integer conversion and raises `ValueError`.

### 4.2. Fix 2: Microsecond Resolution in `src/storage.py`
In `src/storage.py`, line 114:
Change timestamp format from `%Y%m%d_%H%M%S` to `%Y%m%d_%H%M%S_%f`:
```python
backup_path = f"{self.file_path}.corrupt.{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
```
**Mechanism**:
Guarantees distinct backup file paths for consecutive corruptions occurring within the same second, eliminating backup file collision and overwriting under high-frequency failure injection.

---

## 5. Verification Execution Plan

### 5.1. Execution Command
The official unified test command is:
```powershell
python -m pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py tests/test_fuzz_storage_config.py -v
```

### 5.2. Sequential Execution & Isolation Principles
Pytest executes test targets strictly in the order they are provided on the command line. To guarantee absolute deterministic execution:

1. **Test Order Independence**:
   - `test_config.py` -> `test_storage.py` -> `test_m1_adversarial.py` -> `test_fuzz_storage_config.py`
   - With `clean_env: None` added to `test_null_char_in_dotenv_file`, running the suites in **any order** (including reverse order or randomized order) will produce 181/181 passes.

2. **Filesystem Isolation**:
   - All tests use either pytest's `tmp_path` fixture or explicit `tempfile.mkdtemp` context.
   - No test modifies production paths (`data/records.json`, `.env`, `config.yaml`).
   - Every file descriptor is explicitly closed before `os.replace` or `os.remove`, avoiding NTFS file locks (`[WinError 32]`).

3. **Concurrency and Async Isolation**:
   - Every async test runs in an isolated event loop provisioned by `pytest-asyncio`.
   - Each `AtomicJsonStore` instance maintains its own dedicated `asyncio.Lock()`.
   - Thread and coroutine stress tests in `test_m1_adversarial.py` spawn up to 100 concurrent tasks and await all coroutines within the fixture's temporary boundary.

4. **Network & Mocking Isolation**:
   - Zero external HTTP or socket requests are permitted or required.
   - All environment tokens are dummy strings (`1234567890:ABCdef...`, `AIzaSyFake...`).

### 5.3. Performance & Timing Profile

| Module | Test Count | Dominant Operations | Estimated Wall Clock |
|---|---|---|---|
| `tests/test_config.py` | 44 | In-memory YAML / env parsing | ~1.0 s |
| `tests/test_storage.py` | 33 | File I/O, atomic replaces | ~0.8 s |
| `tests/test_m1_adversarial.py` | 22 | 100 concurrent tasks, 365-day loops, fault injections | ~22.0 – ~30.0 s |
| `tests/test_fuzz_storage_config.py` | 82 | Fuzz permutations, 60 mixed concurrent ops | ~2.5 s |
| **Unified Total** | **181** | **All 4 Suites** | **~26.0 – ~35.0 s** |

### 5.4. Verification Diagnostic Ladder

For incremental verification by the implementer/auditor, the following diagnostic ladder is established:

1. **Step 1: Rapid Cross-Test Pollution Probe (2 tests)**:
   ```powershell
   python -m pytest tests/test_config.py::TestLoadConfigSuccess::test_load_config_valid_files tests/test_fuzz_storage_config.py::TestConfigBoundaryFuzzing::test_null_char_in_dotenv_file -v
   ```
   *Expected*: `2 passed in < 0.5s`. Confirms `clean_env` fixture successfully isolates `test_null_char_in_dotenv_file`.

2. **Step 2: Microsecond Timestamp Backup Probe (2 tests)**:
   ```powershell
   python -m pytest tests/test_fuzz_storage_config.py::TestStorageStressAndRecovery::test_truncated_json_file_recovery tests/test_fuzz_storage_config.py::TestStorageStressAndRecovery::test_binary_garbage_handling -v
   ```
   *Expected*: `2 passed in < 0.5s`. Confirms `.corrupt.<timestamp>` backups are generated cleanly with microsecond precision.

3. **Step 3: Component Suites**:
   - `python -m pytest tests/test_config.py -v` (44 passed)
   - `python -m pytest tests/test_storage.py -v` (33 passed)
   - `python -m pytest tests/test_fuzz_storage_config.py -v` (82 passed)
   - `python -m pytest tests/test_m1_adversarial.py -v` (22 passed)

4. **Step 4: Unified Execution (Full Gate Verification)**:
   ```powershell
   python -m pytest tests/test_config.py tests/test_storage.py tests/test_m1_adversarial.py tests/test_fuzz_storage_config.py -v
   ```
   *Expected*: `======================= 181 passed in ~30s =======================` (Exit Code 0).

5. **Step 5: Windows Temporary File Residue Audit**:
   Verify no `.tmp` files linger in `data/` or `%TEMP%`:
   ```powershell
   Get-ChildItem -Path . -Filter "*.tmp" -Recurse
   ```
   *Expected*: 0 files returned.
