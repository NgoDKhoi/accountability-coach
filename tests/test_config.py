"""Unit tests for configuration loading and validation (Milestone 1)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import pytest
import yaml

from src.config import (
    AppConfig,
    GymScheduleConfig,
    MajorScheduleConfig,
    ToeicScheduleConfig,
    load_config,
    mask_secret,
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
        assert config.gym.hour_split1 == 17
        assert config.gym.minute_split1 == 15
        assert config.gym.hour_split2 == 16
        assert config.gym.minute_split2 == 15

        # TOEIC Schedule
        assert isinstance(config.toeic, ToeicScheduleConfig)
        assert config.toeic.time == "19:25"
        assert config.toeic.duration_minutes == 60
        assert len(config.toeic.syllabus_rotation) == 7
        assert config.toeic.syllabus_rotation[0] == "Part 1: Photographs"
        assert config.toeic.syllabus_rotation[6] == "Part 7: Reading Comprehension & Full Mock"
        assert config.toeic.hour == 19
        assert config.toeic.minute == 25
        assert config.toeic.get_part_for_weekday(0) == "Part 1: Photographs"

        # Major Schedule
        assert isinstance(config.major, MajorScheduleConfig)
        assert config.major.time == "20:40"
        assert config.major.duration_minutes == 60
        assert config.major.hour == 20
        assert config.major.minute == 40

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

        # Non-existent env_path should smoothly fall back to existing os.environ
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
        env[empty_var] = "   "
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(ValueError, match=empty_var):
            load_config(str(temp_config_yaml_file), env_path="none.env")


class TestYamlValidation:
    """Verifies schema validation and error reporting for config.yaml."""

    def test_missing_yaml_file(self, temp_env_file: Path):
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config("nonexistent_file_path.yaml", str(temp_env_file))

    def test_invalid_yaml_syntax(self, tmp_path: Path, temp_env_file: Path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("schedules:\n  gym:\n    time_split1: 17:15\n\tbad_tab: true", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            load_config(str(bad_file), str(temp_env_file))

    def test_empty_yaml_file(self, tmp_path: Path, temp_env_file: Path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty|invalid"):
            load_config(str(empty_file), str(temp_env_file))

    def test_missing_schedules_section(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
    ):
        data = valid_yaml_dict.copy()
        data.pop("schedules")
        cfg_file = tmp_path / "missing_schedules.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="schedules"):
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
        data["schedules"] = data["schedules"].copy()
        data["schedules"]["toeic"] = data["schedules"]["toeic"].copy()
        data["schedules"]["toeic"]["syllabus_rotation"] = [f"Part {i}" for i in range(bad_rotation_len)]
        cfg_file = tmp_path / "bad_rotation.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="7"):
            load_config(str(cfg_file), str(temp_env_file))

    def test_toeic_rotation_from_dict(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"] = data["schedules"].copy()
        data["schedules"]["toeic"] = data["schedules"]["toeic"].copy()
        data["schedules"]["toeic"]["syllabus_rotation"] = {
            "mon": "Part 1",
            "tue": "Part 2",
            "wed": "Part 3",
            "thu": "Part 4",
            "fri": "Part 5",
            "sat": "Part 6",
            "sun": "Part 7",
        }
        cfg_file = tmp_path / "dict_rotation.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        cfg = load_config(str(cfg_file), str(temp_env_file))
        assert len(cfg.toeic.syllabus_rotation) == 7
        assert cfg.toeic.syllabus_rotation[0] == "Part 1"
        assert cfg.toeic.syllabus_rotation[6] == "Part 7"

    @pytest.mark.parametrize("bad_time", ["24:00", "25:30", "12:60", "9:00", "invalid", "17:15:00"])
    def test_invalid_time_formats(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        bad_time: str,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"] = data["schedules"].copy()
        data["schedules"]["gym"] = data["schedules"]["gym"].copy()
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
        data["app"] = data["app"].copy()
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
            ("snooze_duration_minutes", 0),
            ("snooze_duration_minutes", -5),
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
        data["limits"] = data["limits"].copy()
        data["limits"][key] = bad_val
        cfg_file = tmp_path / f"bad_{key}.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match=key.split("_")[0]):
            load_config(str(cfg_file), str(temp_env_file))


class TestHelpers:
    """Verifies helper utilities in config module."""

    def test_mask_secret(self):
        assert mask_secret("1234567890abcdef") == "1234...cdef"
        assert mask_secret("short") == "***"
        assert mask_secret("") == ""

    def test_schedule_properties_and_helpers(self, temp_env_file: Path, temp_config_yaml_file: Path):
        cfg = load_config(str(temp_config_yaml_file), str(temp_env_file))
        assert cfg.telegram_bot_token == cfg.bot_token
        assert cfg.gym.hour_split1 == 17
        assert cfg.gym.minute_split1 == 15
        assert cfg.gym.hour_split2 == 16
        assert cfg.gym.minute_split2 == 15
        assert cfg.toeic.hour == 19
        assert cfg.toeic.minute == 25
        assert cfg.major.hour == 20
        assert cfg.major.minute == 40
        # Weekday rotation rollover
        assert cfg.toeic.get_part_for_weekday(7) == cfg.toeic.get_part_for_weekday(0)

