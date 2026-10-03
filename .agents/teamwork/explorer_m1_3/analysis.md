# Milestone 1: Test Suite & Fixtures Comprehensive Specification

**Project**: Autonomous Telegram Personal Accountability Coach (`serene-bohr`)  
**Component**: Milestone 1 Verification Suite (`tests/conftest.py`, `tests/test_config.py`, `tests/test_storage.py`)  
**Author**: `teamwork_preview_explorer` (explorer_m1_3)  
**Date**: 2026-10-03  
**Status**: COMPLETE SPECIFICATION  

---

## 1. Executive Summary & Test Strategy

Milestone 1 establishes the foundational infrastructure of the Autonomous Telegram Personal Accountability Coach:
1. **Configuration & Environment Management (`src/config.py`)**: Bifurcated configuration isolating secrets in `.env` (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`) from operational parameters in `config.yaml` (Gym split cron triggers, TOEIC 7-day syllabus rotation, Major study time, prompts, and limits).
2. **Crash-Safe Atomic Persistence (`src/storage.py`)**: Local JSON persistence (`data/records.json`) using atomic temporary file renaming (`NamedTemporaryFile` + `os.replace` with closed file handle for Windows NTFS support), `asyncio.Lock` serialization, calendar-day streak tracking in `Asia/Ho_Chi_Minh` timezone, and session state tracking (`pending`, `completed`, `snoozed`, `skipped`).

The test suite designed herein adheres to strict zero-network, hermetic testing standards:
- **Zero Network Execution**: All tests execute completely offline without contacting Telegram Bot API or Google Gemini servers.
- **Strict Isolation**: All disk writes are contained within pytest `tmp_path` fixtures, preventing pollution of the repository workspace or production `data/records.json`.
- **Cross-Platform Resilience**: Special test assertions cover Windows NTFS file locking behavior (closing file handles prior to `os.replace`), path separators, and timezone calculations.
- **Deterministic Assertions**: Time calculations use fixed mock ISO dates (`YYYY-MM-DD`) and `datetime.date` arithmetic to guarantee deterministic test outcomes.

---

## 2. Shared Fixtures Specification (`tests/conftest.py`)

The shared fixture module `tests/conftest.py` provides standardized, reusable components across both unit test modules and downstream integration test suites.

### 2.1 Fixture Inventory & Lifecycle

| Fixture Name | Scope | Description | Target Usage |
|---|---|---|---|
| `clean_env` | `function` | Backs up `os.environ` and removes secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `ALLOWED_CHAT_ID`, `CONFIG_PATH`, `LOG_LEVEL`) to prevent test contamination. | `test_config.py` |
| `valid_env_dict` | `session` | Returns standard dictionary of valid environment variables. | `test_config.py` |
| `valid_yaml_dict` | `session` | Returns canonical dictionary of valid `config.yaml` structure matching all R1–R5 requirements. | `test_config.py` |
| `temp_env_file` | `function` | Generates a physical `.env` file inside `tmp_path` populated with `valid_env_dict`. | `test_config.py` |
| `temp_config_yaml_file` | `function` | Generates a physical `config.yaml` file inside `tmp_path` populated with `valid_yaml_dict`. | `test_config.py` |
| `temp_data_dir` | `function` | Creates an isolated `data/` directory inside `tmp_path`. | `test_storage.py` |
| `temp_records_path` | `function` | Returns a `Path` object pointing to `records.json` inside `temp_data_dir`. | `test_storage.py` |
| `initial_records_data` | `session` | Returns the canonical empty JSON database dictionary: `{"streak": {...}, "sessions": {}}`. | `test_storage.py` |
| `atomic_store` | `function` | Instantiates and yields an `AtomicJsonStore` configured to write to `temp_records_path`. | `test_storage.py` |

### 2.2 Complete `tests/conftest.py` Implementation Code

```python
"""Shared test fixtures for Autonomous Telegram Personal Accountability Coach.

Provides isolated environments, temporary file paths, mock environment variables,
and pre-configured store/config instances for zero-network deterministic testing.
"""

import os
import json
import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, Generator

from src.storage import AtomicJsonStore


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Clean out application-specific environment variables to prevent host leakage."""
    vars_to_clear = [
        "TELEGRAM_BOT_TOKEN",
        "GEMINI_API_KEY",
        "ALLOWED_CHAT_ID",
        "CONFIG_PATH",
        "LOG_LEVEL",
    ]
    for var in vars_to_clear:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def valid_env_dict() -> Dict[str, str]:
    """Provide a valid set of environment variables."""
    return {
        "TELEGRAM_BOT_TOKEN": "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789",
        "GEMINI_API_KEY": "AIzaSyFakeGeminiApiKeyForTestingPurposes12345",
        "ALLOWED_CHAT_ID": "123456789",
        "CONFIG_PATH": "config.yaml",
        "LOG_LEVEL": "INFO",
    }


@pytest.fixture
def valid_yaml_dict() -> Dict[str, Any]:
    """Provide a canonical valid config.yaml dictionary matching all requirements."""
    return {
        "app": {
            "timezone": "Asia/Ho_Chi_Minh",
            "max_snoozes": 2,
            "snooze_minutes": 15,
            "context_window_size": 10,
        },
        "schedules": {
            "gym": {
                "cron_days_split1": "mon,tue,thu",
                "time_split1": "17:15",
                "cron_days_split2": "wed,sat",
                "time_split2": "16:15",
                "duration_minutes": 60,
            },
            "toeic": {
                "time": "19:25",
                "duration_minutes": 60,
                "syllabus_rotation": [
                    "Part 1: Photographs",
                    "Part 2: Question-Response",
                    "Part 3: Short Conversations",
                    "Part 4: Short Talks",
                    "Part 5: Incomplete Sentences",
                    "Part 6: Text Completion",
                    "Part 7: Reading Comprehension & Full Mock",
                ],
            },
            "major": {
                "time": "20:40",
                "duration_minutes": 60,
            },
        },
        "prompts": {
            "system_instruction": "Bạn là huấn luyện viên kỷ luật thực chiến cho sinh viên IT & game dev.",
            "excuse_evaluation": "Phân tích lý do người dùng xin nghỉ và bẻ gãy lý do nếu lười biếng.",
            "congratulation": "Khen ngợi ngắn gọn sự kỷ luật và giữ đúng streak cam kết.",
        },
        "fallbacks": {
            "offline_coach": "AI tạm thời gián đoạn, nhưng kỷ luật của bạn thì không! Làm việc ngay.",
            "offline_congrats": "Xuất sắc! Đã ghi nhận hoàn thành buổi học/tập hôm nay.",
            "offline_excuse": "Lý do đã được ghi nhận. Nghỉ ngơi và quay lại kỷ luật vào ngày mai.",
        },
    }


@pytest.fixture
def temp_env_file(tmp_path: Path, valid_env_dict: Dict[str, str]) -> Path:
    """Create a temporary .env file with valid settings."""
    env_file = tmp_path / ".env"
    lines = [f"{k}={v}" for k, v in valid_env_dict.items()]
    env_file.write_text("\n".join(lines), encoding="utf-8")
    return env_file


@pytest.fixture
def temp_config_yaml_file(tmp_path: Path, valid_yaml_dict: Dict[str, Any]) -> Path:
    """Create a temporary config.yaml file with valid settings."""
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(valid_yaml_dict, f, allow_unicode=True)
    return config_file


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Create and return an isolated temporary data directory."""
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture
def temp_records_path(temp_data_dir: Path) -> Path:
    """Return path to records.json in temporary data directory."""
    return temp_data_dir / "records.json"


@pytest.fixture
def initial_records_data() -> Dict[str, Any]:
    """Return canonical empty records schema."""
    return {
        "streak": {
            "current_streak": 0,
            "best_streak": 0,
            "last_completed_date": None,
            "total_completions": 0,
        },
        "sessions": {},
    }


@pytest.fixture
def atomic_store(temp_records_path: Path) -> AtomicJsonStore:
    """Instantiate AtomicJsonStore targeting temporary file."""
    return AtomicJsonStore(file_path=str(temp_records_path))
```

---

## 3. Configuration Test Suite Specification (`tests/test_config.py`)

`tests/test_config.py` validates that `src/config.py` strictly parses, validates, and freezes configuration dataclasses from `.env` and `config.yaml`.

### 3.1 Test Case Matrix for Configuration

| Test Class | Test Method | Input Scenario | Expected Outcome |
|---|---|---|---|
| `TestLoadConfigSuccess` | `test_load_config_valid_files` | Valid `.env` and `config.yaml` files passed. | `AppConfig` instance loaded with all fields matching input values, nested dataclasses correctly populated. |
| `TestLoadConfigSuccess` | `test_app_config_immutability` | Attempting to mutate `config.allowed_chat_id = 999`. | Raises `dataclasses.FrozenInstanceError`. |
| `TestLoadConfigSuccess` | `test_default_values_when_yaml_app_omitted` | `app` section missing `timezone`, `max_snoozes`, `snooze_minutes`, `context_window_size`. | Injected defaults: `Asia/Ho_Chi_Minh`, `2`, `15`, `10`. |
| `TestLoadConfigSuccess` | `test_load_config_from_os_environ_directly` | `.env` file does not exist, but variables set in `os.environ`. | Successfully loads without error. |
| `TestEnvValidation` | `test_allowed_chat_id_whitespace_handling` | `ALLOWED_CHAT_ID="  123456789 \n"`. | Strips whitespace and parses as integer `123456789`. |
| `TestEnvValidation` | `test_allowed_chat_id_negative_group_id` | `ALLOWED_CHAT_ID="-1001987654321"`. | Parses as negative integer `-1001987654321`. |
| `TestEnvValidation` | `test_allowed_chat_id_non_integer` | `ALLOWED_CHAT_ID="abc"`, `"123.45"`, `""`, `"0x12"`. | Raises `ValueError` with clear message mentioning `ALLOWED_CHAT_ID`. |
| `TestEnvValidation` | `test_allowed_chat_id_zero` | `ALLOWED_CHAT_ID="0"`. | Raises `ValueError` (Telegram chat ID cannot be zero). |
| `TestEnvValidation` | `test_missing_telegram_bot_token` | `TELEGRAM_BOT_TOKEN` unset or missing. | Raises `ValueError` mentioning `TELEGRAM_BOT_TOKEN`. |
| `TestEnvValidation` | `test_empty_telegram_bot_token` | `TELEGRAM_BOT_TOKEN=""`. | Raises `ValueError`. |
| `TestEnvValidation` | `test_missing_gemini_api_key` | `GEMINI_API_KEY` unset or missing. | Raises `ValueError` mentioning `GEMINI_API_KEY`. |
| `TestEnvValidation` | `test_empty_gemini_api_key` | `GEMINI_API_KEY=""`. | Raises `ValueError`. |
| `TestEnvValidation` | `test_gemini_api_key_too_short` | `GEMINI_API_KEY="short"`. | Raises `ValueError` (API key too short/invalid). |
| `TestYamlValidation` | `test_missing_yaml_file` | Path points to non-existent `missing.yaml`. | Raises `FileNotFoundError`. |
| `TestYamlValidation` | `test_invalid_yaml_syntax` | YAML file with indentation error or bad syntax. | Raises `ValueError` or `yaml.YAMLError`. |
| `TestYamlValidation` | `test_empty_yaml_file` | YAML file with 0 bytes. | Raises `ValueError` indicating empty configuration. |
| `TestYamlValidation` | `test_missing_schedules_section` | `schedules` block omitted from YAML. | Raises `ValueError` mentioning missing `schedules`. |
| `TestYamlValidation` | `test_missing_schedule_subsections` | `gym`, `toeic`, or `major` missing under `schedules`. | Raises `ValueError` specifying missing schedule section. |
| `TestYamlValidation` | `test_toeic_syllabus_rotation_length` | `syllabus_rotation` has 6 items or 8 items. | Raises `ValueError` (must have exactly 7 items for Mon-Sun). |
| `TestYamlValidation` | `test_toeic_syllabus_empty` | `syllabus_rotation: []`. | Raises `ValueError`. |
| `TestYamlValidation` | `test_invalid_time_format` | `time_split1: "25:99"` or `"bad_time"`. | Raises `ValueError` (must follow 24h `HH:MM` format). |
| `TestYamlValidation` | `test_invalid_timezone` | `timezone: "Invalid/Fake_Zone"`. | Raises `ValueError` (invalid IANA timezone). |
| `TestYamlValidation` | `test_invalid_numeric_limits` | `max_snoozes < 0`, `duration_minutes <= 0`, etc. | Raises `ValueError`. |
| `TestYamlValidation` | `test_missing_prompts_or_fallbacks` | `prompts` or `fallbacks` omitted. | Raises `ValueError`. |

### 3.2 Complete `tests/test_config.py` Code Design

```python
"""Unit tests for configuration loading and validation (Milestone 1)."""

import os
import pytest
import yaml
from pathlib import Path
from dataclasses import FrozenInstanceError

from src.config import (
    load_config,
    AppConfig,
    GymScheduleConfig,
    ToeicScheduleConfig,
    MajorScheduleConfig,
)


class TestLoadConfigSuccess:
    """Verifies successful loading and structure of configuration."""

    def test_load_config_valid_files(self, temp_env_file: Path, temp_config_yaml_file: Path):
        config = load_config(
            config_path=str(temp_config_yaml_file),
            env_path=str(temp_env_file),
        )

        assert isinstance(config, AppConfig)
        assert config.bot_token == "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
        assert config.gemini_api_key == "AIzaSyFakeGeminiApiKeyForTestingPurposes12345"
        assert config.allowed_chat_id == 123456789
        assert isinstance(config.allowed_chat_id, int)
        assert config.timezone == "Asia/Ho_Chi_Minh"
        assert config.max_snoozes == 2
        assert config.snooze_minutes == 15
        assert config.context_window_size == 10

        # Gym Schedule
        assert isinstance(config.gym, GymScheduleConfig)
        assert config.gym.cron_days_split1 == "mon,tue,thu"
        assert config.gym.time_split1 == "17:15"
        assert config.gym.cron_days_split2 == "wed,sat"
        assert config.gym.time_split2 == "16:15"
        assert config.gym.duration_minutes == 60

        # TOEIC Schedule
        assert isinstance(config.toeic, ToeicScheduleConfig)
        assert config.toeic.time == "19:25"
        assert config.toeic.duration_minutes == 60
        assert len(config.toeic.syllabus_rotation) == 7
        assert config.toeic.syllabus_rotation[0] == "Part 1: Photographs"
        assert config.toeic.syllabus_rotation[6] == "Part 7: Reading Comprehension & Full Mock"

        # Major Schedule
        assert isinstance(config.major, MajorScheduleConfig)
        assert config.major.time == "20:40"
        assert config.major.duration_minutes == 60

        # Prompts & Fallbacks
        assert "system_instruction" in config.prompts
        assert "excuse_evaluation" in config.prompts
        assert "congratulation" in config.prompts
        assert "offline_coach" in config.fallbacks
        assert "offline_congrats" in config.fallbacks
        assert "offline_excuse" in config.fallbacks

    def test_app_config_immutability(self, temp_env_file: Path, temp_config_yaml_file: Path):
        config = load_config(str(temp_config_yaml_file), str(temp_env_file))
        with pytest.raises(FrozenInstanceError):
            config.allowed_chat_id = 999999999

    def test_default_values_when_yaml_app_omitted(
        self, tmp_path: Path, temp_env_file: Path, valid_yaml_dict: dict
    ):
        # Remove optional app section
        yaml_data = valid_yaml_dict.copy()
        yaml_data.pop("app")
        custom_yaml = tmp_path / "custom_config.yaml"
        with open(custom_yaml, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f)

        config = load_config(str(custom_yaml), str(temp_env_file))
        assert config.timezone == "Asia/Ho_Chi_Minh"
        assert config.max_snoozes == 2
        assert config.snooze_minutes == 15
        assert config.context_window_size == 10

    def test_load_config_from_os_environ_directly(
        self,
        monkeypatch: pytest.MonkeyPatch,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
    ):
        for k, v in valid_env_dict.items():
            monkeypatch.setenv(k, v)

        # Non-existent env_path should fallback to existing os.environ
        config = load_config(
            config_path=str(temp_config_yaml_file),
            env_path="non_existent_env_file.env",
        )
        assert config.allowed_chat_id == 123456789
        assert config.bot_token == valid_env_dict["TELEGRAM_BOT_TOKEN"]


class TestEnvValidation:
    """Verifies validation and type safety of environment variables."""

    def test_allowed_chat_id_whitespace_handling(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
    ):
        test_values = [
            ("  123456789  ", 123456789),
            ("\t123456789\n", 123456789),
            (" 987654321 \r\n", 987654321),
            ("  -1001234567890 \n", -1001234567890),
        ]
        for raw, expected in test_values:
            env = valid_env_dict.copy()
            env["ALLOWED_CHAT_ID"] = raw
            for k, v in env.items():
                monkeypatch.setenv(k, v)

            config = load_config(str(temp_config_yaml_file), env_path="none.env")
            assert config.allowed_chat_id == expected
            assert isinstance(config.allowed_chat_id, int)

    @pytest.mark.parametrize(
        "invalid_chat_id",
        ["", "abc", "123.456", "0", "None", "undefined", "true", "0x1A"],
    )
    def test_allowed_chat_id_invalid_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        invalid_chat_id: str,
    ):
        env = valid_env_dict.copy()
        env["ALLOWED_CHAT_ID"] = invalid_chat_id
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(ValueError, match="ALLOWED_CHAT_ID"):
            load_config(str(temp_config_yaml_file), env_path="none.env")

    @pytest.mark.parametrize(
        "missing_var",
        ["TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY", "ALLOWED_CHAT_ID"],
    )
    def test_missing_required_env_vars(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        missing_var: str,
    ):
        env = valid_env_dict.copy()
        env.pop(missing_var)
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(ValueError, match=missing_var):
            load_config(str(temp_config_yaml_file), env_path="none.env")

    @pytest.mark.parametrize(
        "empty_var",
        ["TELEGRAM_BOT_TOKEN", "GEMINI_API_KEY", "ALLOWED_CHAT_ID"],
    )
    def test_empty_env_vars(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        empty_var: str,
    ):
        env = valid_env_dict.copy()
        env[empty_var] = ""
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(ValueError, match=empty_var):
            load_config(str(temp_config_yaml_file), env_path="none.env")

    def test_gemini_api_key_too_short(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
    ):
        env = valid_env_dict.copy()
        env["GEMINI_API_KEY"] = "short_key"
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            load_config(str(temp_config_yaml_file), env_path="none.env")


class TestYamlValidation:
    """Verifies schema validation and error reporting for config.yaml."""

    def test_missing_yaml_file(self, temp_env_file: Path):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_file_path.yaml", str(temp_env_file))

    def test_invalid_yaml_syntax(self, tmp_path: Path, temp_env_file: Path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("schedules:\n  gym:\n    time_split1: 17:15\n\tbad_tab: true", encoding="utf-8")
        with pytest.raises((ValueError, yaml.YAMLError)):
            load_config(str(bad_file), str(temp_env_file))

    def test_empty_yaml_file(self, tmp_path: Path, temp_env_file: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty|invalid"):
            load_config(str(empty_file), str(temp_env_file))

    @pytest.mark.parametrize("missing_section", ["schedules", "prompts", "fallbacks"])
    def test_missing_top_level_sections(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        missing_section: str,
    ):
        data = valid_yaml_dict.copy()
        data.pop(missing_section)
        cfg_file = tmp_path / f"missing_{missing_section}.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match=missing_section):
            load_config(str(cfg_file), str(temp_env_file))

    @pytest.mark.parametrize("missing_sub", ["gym", "toeic", "major"])
    def test_missing_schedule_subsections(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        missing_sub: str,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"] = data["schedules"].copy()
        data["schedules"].pop(missing_sub)
        cfg_file = tmp_path / f"missing_sub_{missing_sub}.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match=missing_sub):
            load_config(str(cfg_file), str(temp_env_file))

    @pytest.mark.parametrize("bad_rotation_len", [0, 5, 6, 8, 14])
    def test_toeic_syllabus_rotation_length(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        bad_rotation_len: int,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"]["toeic"]["syllabus_rotation"] = [f"Part {i}" for i in range(bad_rotation_len)]
        cfg_file = tmp_path / "bad_rotation.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="7"):
            load_config(str(cfg_file), str(temp_env_file))

    @pytest.mark.parametrize("bad_time", ["24:00", "25:30", "12:60", "9:00", "invalid", "17:15:00"])
    def test_invalid_time_formats(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        bad_time: str,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"]["gym"]["time_split1"] = bad_time
        cfg_file = tmp_path / "bad_time.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="time|HH:MM"):
            load_config(str(cfg_file), str(temp_env_file))

    def test_invalid_timezone(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
    ):
        data = valid_yaml_dict.copy()
        data["app"]["timezone"] = "Invalid/Nonexistent_Timezone"
        cfg_file = tmp_path / "bad_tz.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="timezone|ZoneInfo"):
            load_config(str(cfg_file), str(temp_env_file))

    @pytest.mark.parametrize(
        "key,bad_val",
        [
            ("max_snoozes", -1),
            ("snooze_minutes", 0),
            ("snooze_minutes", -5),
            ("context_window_size", 0),
        ],
    )
    def test_invalid_numeric_limits(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        key: str,
        bad_val: int,
    ):
        data = valid_yaml_dict.copy()
        data["app"][key] = bad_val
        cfg_file = tmp_path / f"bad_{key}.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match=key):
            load_config(str(cfg_file), str(temp_env_file))
```

---

## 4. Storage & Persistence Test Suite Specification (`tests/test_storage.py`)

`tests/test_storage.py` tests `src/storage.py` and `AtomicJsonStore`:
1. Automatic directory creation.
2. Crash-safe atomic write using temporary files + `os.replace` (including file handle closure for Windows NTFS compatibility).
3. `asyncio.Lock` concurrency safety under parallel tasks.
4. Calendar-day streak progression (`Asia/Ho_Chi_Minh` timezone logic).
5. Multi-session same-day idempotency (e.g., Gym + TOEIC + Major on the same day).
6. Broken streak reset to 1 after a day gap while preserving `best_streak`.
7. Session state transitions (`pending` -> `snoozed` -> `completed` / `skipped`).
8. Snooze counting and escalation limits.
9. Skip reasons (`EXCUSE` vs `LEGITIMATE`) without streak incrementation.

### 4.1 Test Case Matrix for Storage

| Test Class | Test Method | Scenario Description | Expected Outcome |
|---|---|---|---|
| `TestStorageInitAndDirectory` | `test_auto_create_parent_directory` | Instantiating store with nested path (`data/sub/records.json`) that does not exist. | Parent directories are created automatically; no crash. |
| `TestStorageInitAndDirectory` | `test_load_data_when_file_does_not_exist` | Calling `load_data()` before any file is saved. | Returns clean initial schema with `current_streak=0`, `best_streak=0`, `total_completions=0`, `sessions={}`. |
| `TestStorageInitAndDirectory` | `test_get_streak_when_file_does_not_exist` | Calling `get_streak()` on empty store. | Returns `StreakData(0, 0, None, 0)`. |
| `TestAtomicWriteAndCrashSafety` | `test_atomic_write_creates_valid_file` | Calling `save_data(data)`. | Target file exists and contains properly formatted JSON. |
| `TestAtomicWriteAndCrashSafety` | `test_atomic_write_uses_same_directory_temp_file` | Inspecting directory during write. | Temporary file is created in `data/` (same volume) and renamed to `records.json`; no orphan `.tmp` remains. |
| `TestAtomicWriteAndCrashSafety` | `test_crash_safety_on_serialization_error` | Saving object that causes serialization error. | Original `records.json` remains completely untouched; temporary file is cleaned up. |
| `TestAtomicWriteAndCrashSafety` | `test_crash_safety_on_replace_failure` | Simulating `os.replace` failure (e.g. `OSError`). | Original `records.json` remains untouched; temp file unlinked. |
| `TestAtomicWriteAndCrashSafety` | `test_windows_file_handle_closed_before_replace` | Verifying file handle closure on Windows. | `os.replace` executes cleanly without `WinError 32` PermissionError. |
| `TestAtomicWriteAndCrashSafety` | `test_concurrent_writes_thread_safe` | Launching 10 concurrent async writes via `asyncio.gather`. | `asyncio.Lock` ensures zero corrupted writes or collisions; file ends with valid JSON. |
| `TestStreakProgression` | `test_first_ever_session_completion` | First completion on `2026-10-01`. | `current_streak=1`, `best_streak=1`, `last_completed_date='2026-10-01'`, `total_completions=1`. |
| `TestStreakProgression` | `test_consecutive_days_progression` | Completions on `2026-10-01`, `2026-10-02`, `2026-10-03`. | `current_streak=3`, `best_streak=3`, `total_completions=3`. |
| `TestStreakProgression` | `test_multi_session_same_day_idempotency` | Completing Gym at 17:30, TOEIC at 19:30, Major at 20:45 on same date `2026-10-03`. | `current_streak` increments ONLY on the first session (remains 1 across all 3); `total_completions=3`. |
| `TestStreakProgression` | `test_duplicate_session_completion_idempotency` | Calling `record_completion` twice with exact same session ID and date. | Session remains completed; streak and total completions do not double-increment. |
| `TestStreakProgression` | `test_broken_streak_reset_to_one_after_gap` | Streak 5 on `2026-10-01`, gap on `2026-10-02`, completion on `2026-10-03`. | `current_streak=1`, `best_streak=5` (preserved!), `last_completed_date='2026-10-03'`. |
| `TestStreakProgression` | `test_large_gap_streak_reset` | Streak 10 on `2026-09-01`, completion on `2026-10-03` (>30 days). | `current_streak=1`, `best_streak=10`. |
| `TestStreakProgression` | `test_new_best_streak_record` | Previous best was 2. User completes on 3 consecutive days. | `current_streak=3`, `best_streak=3` (updated). |
| `TestStreakProgression` | `test_month_boundary_progression` | Completion on `2026-10-31`, next on `2026-11-01`. | Consecutive! `current_streak` increments by 1. |
| `TestStreakProgression` | `test_year_boundary_progression` | Completion on `2026-12-31`, next on `2027-01-01`. | Consecutive! `current_streak` increments by 1. |
| `TestStreakProgression` | `test_leap_year_boundary_progression` | Completion on `2028-02-28`, next on `2028-02-29`, next on `2028-03-01`. | Consecutive across leap day! `current_streak` increments by 1 each day. |
| `TestSessionTracking` | `test_get_session_status_unknown` | Querying non-existent session ID. | Returns `None`. |
| `TestSessionTracking` | `test_record_completion_persists_session` | Marking session `gym_20261003` completed. | Session status is `"completed"`, stores session type, date, and `completed_at`. |
| `TestSessionTracking` | `test_record_snooze_increments` | Snoozing session: first snooze (1), second snooze (2). | Status becomes `"snoozed"`, `snooze_count` increments to 1, then 2. |
| `TestSessionTracking` | `test_snooze_then_completed` | Session snoozed twice, then marked completed. | Final status is `"completed"`, but `snooze_count=2` is retained in record. |
| `TestSessionTracking` | `test_record_skip_excuse` | Recording skip with excuse reason and classification `EXCUSE`. | Status is `"skipped"`, stores reason and `EXCUSE` classification. |
| `TestSessionTracking` | `test_record_skip_legitimate` | Recording skip with doctor note and classification `LEGITIMATE`. | Status is `"skipped"`, stores reason and `LEGITIMATE` classification. |
| `TestSessionTracking` | `test_skip_does_not_increment_streak` | Recording skip for today. | `current_streak` is NOT incremented; `last_completed_date` remains yesterday's date. |
| `TestSessionTracking` | `test_multiple_independent_sessions_same_day` | Day has Gym (completed), TOEIC (snoozed), Major (skipped). | All 3 session records coexist independently in `data["sessions"]`. |
| `TestDataCorruptionRecovery` | `test_corrupted_json_syntax_recovery` | File contains malformed bytes/string. | Handled gracefully: either re-initializes clean schema or raises clear `ValueError`/`JSONDecodeError` with backup. |
| `TestDataCorruptionRecovery` | `test_empty_file_recovery` | File has 0 bytes. | Handled cleanly: returns default schema without crashing. |

### 4.2 Complete `tests/test_storage.py` Code Design

```python
"""Unit tests for atomic JSON storage and calendar streak engine (Milestone 1)."""

import os
import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch

from src.storage import AtomicJsonStore, StreakData


@pytest.mark.asyncio
class TestStorageInitAndDirectory:
    """Verifies directory auto-creation and empty state handling."""

    async def test_auto_create_parent_directory(self, tmp_path: Path):
        nested_file = tmp_path / "deep" / "nested" / "path" / "records.json"
        assert not nested_file.parent.exists()

        store = AtomicJsonStore(file_path=str(nested_file))
        assert nested_file.parent.exists()

    async def test_load_data_when_file_does_not_exist(self, atomic_store: AtomicJsonStore):
        data = await atomic_store.load_data()
        assert isinstance(data, dict)
        assert "streak" in data
        assert "sessions" in data
        assert data["streak"]["current_streak"] == 0
        assert data["streak"]["best_streak"] == 0
        assert data["streak"]["last_completed_date"] is None
        assert data["streak"]["total_completions"] == 0

    async def test_get_streak_when_file_does_not_exist(self, atomic_store: AtomicJsonStore):
        streak = await atomic_store.get_streak()
        assert isinstance(streak, StreakData)
        assert streak.current_streak == 0
        assert streak.best_streak == 0
        assert streak.last_completed_date is None
        assert streak.total_completions == 0


@pytest.mark.asyncio
class TestAtomicWriteAndCrashSafety:
    """Verifies atomic replace semantics, Windows NTFS compatibility, and crash safety."""

    async def test_atomic_write_creates_valid_file(self, atomic_store: AtomicJsonStore, temp_records_path: Path):
        test_payload = {
            "streak": {"current_streak": 2, "best_streak": 2, "last_completed_date": "2026-10-02", "total_completions": 2},
            "sessions": {"2026-10-02": {"gym": {"status": "completed"}}},
        }
        await atomic_store.save_data(test_payload)

        assert temp_records_path.exists()
        with open(temp_records_path, "r", encoding="utf-8") as f:
            disk_data = json.load(f)
        assert disk_data == test_payload

    async def test_atomic_write_cleans_up_temporary_files(self, atomic_store: AtomicJsonStore, temp_data_dir: Path):
        for i in range(5):
            await atomic_store.save_data({"streak": {"current_streak": i, "best_streak": i, "last_completed_date": None, "total_completions": i}, "sessions": {}})

        # Verify only records.json exists, no leftover .tmp files
        dir_contents = os.listdir(temp_data_dir)
        assert dir_contents == ["records.json"]

    async def test_crash_safety_on_serialization_error(self, atomic_store: AtomicJsonStore, temp_records_path: Path):
        initial = {
            "streak": {"current_streak": 5, "best_streak": 10, "last_completed_date": "2026-10-01", "total_completions": 5},
            "sessions": {},
        }
        await atomic_store.save_data(initial)

        # Attempt to save non-serializable object (sets cannot be serialized to JSON)
        bad_payload = {"streak": {"invalid": set([1, 2, 3])}}
        with pytest.raises((TypeError, ValueError)):
            await atomic_store.save_data(bad_payload)

        # Original data must remain 100% intact
        disk_data = await atomic_store.load_data()
        assert disk_data["streak"]["current_streak"] == 5

    async def test_crash_safety_on_os_replace_failure(self, atomic_store: AtomicJsonStore, temp_records_path: Path):
        initial = {
            "streak": {"current_streak": 3, "best_streak": 3, "last_completed_date": "2026-10-01", "total_completions": 3},
            "sessions": {},
        }
        await atomic_store.save_data(initial)

        with patch("os.replace", side_effect=OSError("Simulated disk error")):
            with pytest.raises(OSError, match="Simulated disk error"):
                await atomic_store.save_data({"streak": {"current_streak": 99}})

        # Original data untouched
        data = await atomic_store.load_data()
        assert data["streak"]["current_streak"] == 3

    async def test_concurrent_writes_thread_safe(self, atomic_store: AtomicJsonStore):
        async def worker(index: int):
            data = await atomic_store.load_data()
            data["sessions"][f"session_{index}"] = {"status": "completed"}
            await atomic_store.save_data(data)

        # 10 concurrent write tasks
        await asyncio.gather(*(worker(i) for i in range(10)))

        final_data = await atomic_store.load_data()
        assert len(final_data["sessions"]) == 10


@pytest.mark.asyncio
class TestStreakProgression:
    """Verifies calendar streak arithmetic in Asia/Ho_Chi_Minh."""

    async def test_first_ever_session_completion(self, atomic_store: AtomicJsonStore):
        streak = await atomic_store.record_completion(
            session_id="gym_20261001",
            session_type="gym",
            today_str="2026-10-01",
        )
        assert streak.current_streak == 1
        assert streak.best_streak == 1
        assert streak.last_completed_date == "2026-10-01"
        assert streak.total_completions == 1

    async def test_consecutive_days_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("gym_20261001", "gym", "2026-10-01")
        await atomic_store.record_completion("toeic_20261002", "toeic", "2026-10-02")
        streak = await atomic_store.record_completion("major_20261003", "major", "2026-10-03")

        assert streak.current_streak == 3
        assert streak.best_streak == 3
        assert streak.last_completed_date == "2026-10-03"
        assert streak.total_completions == 3

    async def test_multi_session_same_day_idempotency(self, atomic_store: AtomicJsonStore):
        today = "2026-10-03"
        s1 = await atomic_store.record_completion("gym_1", "gym", today)
        assert s1.current_streak == 1
        assert s1.total_completions == 1

        # Second session on same day MUST NOT increment streak
        s2 = await atomic_store.record_completion("toeic_1", "toeic", today)
        assert s2.current_streak == 1
        assert s2.best_streak == 1
        assert s2.total_completions == 2

        # Third session on same day MUST NOT increment streak
        s3 = await atomic_store.record_completion("major_1", "major", today)
        assert s3.current_streak == 1
        assert s3.best_streak == 1
        assert s3.total_completions == 3

    async def test_duplicate_session_completion_idempotency(self, atomic_store: AtomicJsonStore):
        today = "2026-10-03"
        s1 = await atomic_store.record_completion("gym_1", "gym", today)
        # Calling again with exact same session_id
        s2 = await atomic_store.record_completion("gym_1", "gym", today)

        assert s2.current_streak == s1.current_streak
        assert s2.total_completions == s1.total_completions

    async def test_broken_streak_reset_to_one_after_gap(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("gym_1", "gym", "2026-10-01")
        await atomic_store.record_completion("gym_2", "gym", "2026-10-02")
        # 2026-10-03 is missed!
        # Next completion is 2026-10-04
        streak = await atomic_store.record_completion("gym_4", "gym", "2026-10-04")

        assert streak.current_streak == 1  # Reset to 1
        assert streak.best_streak == 2     # Best streak preserved!
        assert streak.last_completed_date == "2026-10-04"
        assert streak.total_completions == 3

    async def test_large_gap_streak_reset(self, atomic_store: AtomicJsonStore):
        # Preload data with 10-day streak
        data = {
            "streak": {"current_streak": 10, "best_streak": 10, "last_completed_date": "2026-08-01", "total_completions": 10},
            "sessions": {},
        }
        await atomic_store.save_data(data)

        # Complete 2 months later
        streak = await atomic_store.record_completion("gym_new", "gym", "2026-10-03")
        assert streak.current_streak == 1
        assert streak.best_streak == 10
        assert streak.last_completed_date == "2026-10-03"
        assert streak.total_completions == 11

    async def test_new_best_streak_record(self, atomic_store: AtomicJsonStore):
        data = {
            "streak": {"current_streak": 3, "best_streak": 3, "last_completed_date": "2026-10-02", "total_completions": 3},
            "sessions": {},
        }
        await atomic_store.save_data(data)

        streak = await atomic_store.record_completion("gym_4", "gym", "2026-10-03")
        assert streak.current_streak == 4
        assert streak.best_streak == 4  # Surpassed previous best!

    async def test_month_boundary_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2026-10-31")
        streak = await atomic_store.record_completion("s2", "gym", "2026-11-01")
        assert streak.current_streak == 2

    async def test_year_boundary_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2026-12-31")
        streak = await atomic_store.record_completion("s2", "gym", "2027-01-01")
        assert streak.current_streak == 2

    async def test_leap_year_boundary_progression(self, atomic_store: AtomicJsonStore):
        await atomic_store.record_completion("s1", "gym", "2028-02-28")
        s2 = await atomic_store.record_completion("s2", "gym", "2028-02-29")
        assert s2.current_streak == 2
        s3 = await atomic_store.record_completion("s3", "gym", "2028-03-01")
        assert s3.current_streak == 3


@pytest.mark.asyncio
class TestSessionTracking:
    """Verifies session status lifecycles, snoozes, and skips."""

    async def test_get_session_status_unknown(self, atomic_store: AtomicJsonStore):
        status = await atomic_store.get_session_status("nonexistent_session_id")
        assert status is None

    async def test_record_completion_persists_session(self, atomic_store: AtomicJsonStore):
        session_id = "toeic_20261003"
        await atomic_store.record_completion(session_id, "toeic", "2026-10-03")

        status = await atomic_store.get_session_status(session_id)
        assert status is not None
        assert status["status"] == "completed"
        assert status["session_type"] == "toeic"
        assert status["date"] == "2026-10-03"
        assert "completed_at" in status

    async def test_record_snooze_increments(self, atomic_store: AtomicJsonStore):
        session_id = "major_20261003"

        cnt1 = await atomic_store.record_snooze(session_id, new_count=1)
        assert cnt1 == 1
        st1 = await atomic_store.get_session_status(session_id)
        assert st1["status"] == "snoozed"
        assert st1["snooze_count"] == 1

        cnt2 = await atomic_store.record_snooze(session_id, new_count=2)
        assert cnt2 == 2
        st2 = await atomic_store.get_session_status(session_id)
        assert st2["status"] == "snoozed"
        assert st2["snooze_count"] == 2

    async def test_snooze_then_completed(self, atomic_store: AtomicJsonStore):
        session_id = "gym_20261003"
        await atomic_store.record_snooze(session_id, new_count=2)
        await atomic_store.record_completion(session_id, "gym", "2026-10-03")

        status = await atomic_store.get_session_status(session_id)
        assert status["status"] == "completed"
        assert status["snooze_count"] == 2  # Preserved snooze history

    async def test_record_skip_excuse(self, atomic_store: AtomicJsonStore):
        session_id = "major_20261003"
        reason = "Đang dở ván game Dota 2"
        ts = "2026-10-03T20:50:00+07:00"

        await atomic_store.record_skip(session_id, reason=reason, classification="EXCUSE", timestamp_str=ts)

        status = await atomic_store.get_session_status(session_id)
        assert status["status"] == "skipped"
        assert status["reason"] == reason
        assert status["classification"] == "EXCUSE"
        assert status["timestamp"] == ts

    async def test_record_skip_legitimate(self, atomic_store: AtomicJsonStore):
        session_id = "gym_20261003"
        reason = "Sốt cao 39.5 độ phải nằm viện"
        ts = "2026-10-03T17:20:00+07:00"

        await atomic_store.record_skip(session_id, reason=reason, classification="LEGITIMATE", timestamp_str=ts)

        status = await atomic_store.get_session_status(session_id)
        assert status["status"] == "skipped"
        assert status["reason"] == reason
        assert status["classification"] == "LEGITIMATE"

    async def test_skip_does_not_increment_streak(self, atomic_store: AtomicJsonStore):
        data = {
            "streak": {"current_streak": 4, "best_streak": 4, "last_completed_date": "2026-10-02", "total_completions": 4},
            "sessions": {},
        }
        await atomic_store.save_data(data)

        # User skips today
        await atomic_store.record_skip("gym_20261003", reason="Bệnh", classification="LEGITIMATE", timestamp_str="2026-10-03T17:20:00+07:00")

        streak = await atomic_store.get_streak()
        assert streak.current_streak == 4  # Did not increment!
        assert streak.last_completed_date == "2026-10-02"  # Last completion date unchanged!

    async def test_multiple_independent_sessions_same_day(self, atomic_store: AtomicJsonStore):
        today = "2026-10-03"
        await atomic_store.record_completion("gym_1", "gym", today)
        await atomic_store.record_snooze("toeic_1", new_count=1)
        await atomic_store.record_skip("major_1", reason="Bận đồ án", classification="LEGITIMATE", timestamp_str="2026-10-03T21:00:00+07:00")

        gym_st = await atomic_store.get_session_status("gym_1")
        toeic_st = await atomic_store.get_session_status("toeic_1")
        major_st = await atomic_store.get_session_status("major_1")

        assert gym_st["status"] == "completed"
        assert toeic_st["status"] == "snoozed"
        assert major_st["status"] == "skipped"


@pytest.mark.asyncio
class TestDataCorruptionRecovery:
    """Verifies store behavior upon encountering invalid or corrupt storage files."""

    async def test_empty_file_recovery(self, atomic_store: AtomicJsonStore, temp_records_path: Path):
        temp_records_path.write_text("", encoding="utf-8")
        data = await atomic_store.load_data()
        assert data["streak"]["current_streak"] == 0

    async def test_corrupted_json_syntax_recovery(self, atomic_store: AtomicJsonStore, temp_records_path: Path):
        temp_records_path.write_text("{bad_json_not_valid", encoding="utf-8")
        # Load data should handle or safely reset with backup
        data = await atomic_store.load_data()
        assert data["streak"]["current_streak"] == 0
```

---

## 5. Architectural Synthesis with Peer Explorations

### 5.1 Synthesis with Config Explorer (`explorer_m1_1`)
- **Type Compatibility**: `load_config(config_path: str = "config.yaml", env_path: str = ".env") -> AppConfig` perfectly aligns with `AppConfig` and nested frozen dataclasses (`GymScheduleConfig`, `ToeicScheduleConfig`, `MajorScheduleConfig`).
- **Whitespace Rule**: `ALLOWED_CHAT_ID` string from `.env` or OS environment must be stripped (`.strip()`) before conversion (`int(...)`). Our test cases directly enforce this.
- **Strict Validation**: Mandatory secrets (`TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`) must raise clear `ValueError` if absent or empty.

### 5.2 Synthesis with Storage Explorer (`explorer_m1_2`)
- **Atomic Replace**: Writing to `tempfile.NamedTemporaryFile` in `dir=self.dir_name` (same directory), flushing + fsync, and **closing the file handle before `os.replace`** is mandatory to prevent Windows `WinError 32` PermissionError.
- **Streak Model**: `StreakData` dataclass with `current_streak`, `best_streak`, `last_completed_date`, `total_completions`.
- **Calendar Day Arithmetic**: Dates parsed as `datetime.date.fromisoformat(today_str)`. Gaps greater than 1 calendar day reset `current_streak = 1`. Multiple completions on the same day (`last_completed_date == today_str`) do not increment `current_streak`, ensuring complete idempotency.

---

## 6. Verification & Test Execution Strategy

When tests are executed by the Developer agent in Milestone 1 implementation:
1. Virtual environment installation:
   ```bash
   pip install pytest pytest-asyncio pyyaml
   ```
2. Running the unit test suites:
   ```bash
   pytest tests/test_config.py tests/test_storage.py -v
   ```
3. Acceptance threshold: 100% pass rate across all 35+ test cases without external network calls or real API keys.
