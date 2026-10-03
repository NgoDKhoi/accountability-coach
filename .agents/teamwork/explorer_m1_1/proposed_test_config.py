"""Unit tests for configuration loader and dataclasses (src/config.py)."""

import os
import pytest
from zoneinfo import ZoneInfo
from src.config import (
    AppConfig,
    GymScheduleConfig,
    ToeicScheduleConfig,
    MajorScheduleConfig,
    load_config,
    mask_secret,
    DEFAULT_PROMPTS,
    DEFAULT_FALLBACKS,
)


@pytest.fixture
def valid_env_vars(monkeypatch):
    """Sets standard valid environment variables."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey1234567890abcdefghijklmnopqrst")
    monkeypatch.setenv("ALLOWED_CHAT_ID", "123456789")


@pytest.fixture
def minimal_config_yaml(tmp_path):
    """Creates a minimal valid config.yaml in a temporary directory."""
    yaml_content = """
app:
  timezone: "Asia/Ho_Chi_Minh"
  history_limit: 10

limits:
  max_snoozes: 2
  snooze_duration_minutes: 15

schedules:
  gym:
    cron_days_split1: "mon,tue,thu"
    time_split1: "17:15"
    cron_days_split2: "wed,sat"
    time_split2: "16:15"
  toeic:
    time: "19:25"
    syllabus_rotation:
      - "Part 1 - Photos"
      - "Part 2 - Q&A"
      - "Part 3 - Conversations"
      - "Part 4 - Talks"
      - "Part 5 - Incomplete Sentences"
      - "Part 6 - Text Completion"
      - "Part 7 - Reading"
  major:
    time: "20:40"
"""
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(yaml_content, encoding="utf-8")
    return str(yaml_file)


class TestConfigLoading:
    def test_load_valid_config(self, valid_env_vars, minimal_config_yaml):
        cfg = load_config(config_path=minimal_config_yaml, env_path=None)
        assert isinstance(cfg, AppConfig)
        assert cfg.bot_token == "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ123456789"
        assert cfg.gemini_api_key == "AIzaSyTestKey1234567890abcdefghijklmnopqrst"
        assert cfg.allowed_chat_id == 123456789
        assert isinstance(cfg.allowed_chat_id, int)
        assert cfg.timezone == "Asia/Ho_Chi_Minh"
        assert cfg.max_snoozes == 2
        assert cfg.snooze_minutes == 15
        assert cfg.context_window_size == 10

        # Schedules
        assert cfg.gym.cron_days_split1 == "mon,tue,thu"
        assert cfg.gym.time_split1 == "17:15"
        assert cfg.gym.hour_split1 == 17
        assert cfg.gym.minute_split1 == 15
        assert cfg.gym.hour_split2 == 16
        assert cfg.gym.minute_split2 == 15

        assert cfg.toeic.time == "19:25"
        assert cfg.toeic.hour == 19
        assert cfg.toeic.minute == 25
        assert len(cfg.toeic.syllabus_rotation) == 7
        assert cfg.toeic.get_part_for_weekday(0) == "Part 1 - Photos"
        assert cfg.toeic.get_part_for_weekday(6) == "Part 7 - Reading"

        assert cfg.major.time == "20:40"
        assert cfg.major.hour == 20
        assert cfg.major.minute == 40

        # Prompts and fallbacks defaults populated
        assert "completion_praise" in cfg.prompts
        assert "offline_praise" in cfg.fallbacks

    def test_missing_telegram_bot_token(self, monkeypatch, minimal_config_yaml):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
        monkeypatch.setenv("ALLOWED_CHAT_ID", "123456")
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            load_config(config_path=minimal_config_yaml, env_path=None)

    def test_empty_telegram_bot_token(self, monkeypatch, minimal_config_yaml):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "   ")
        monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
        monkeypatch.setenv("ALLOWED_CHAT_ID", "123456")
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            load_config(config_path=minimal_config_yaml, env_path=None)

    def test_missing_gemini_api_key(self, monkeypatch, minimal_config_yaml):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid_token")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.setenv("ALLOWED_CHAT_ID", "123456")
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            load_config(config_path=minimal_config_yaml, env_path=None)

    def test_missing_allowed_chat_id(self, monkeypatch, minimal_config_yaml):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid_token")
        monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
        monkeypatch.delenv("ALLOWED_CHAT_ID", raising=False)
        with pytest.raises(ValueError, match="ALLOWED_CHAT_ID"):
            load_config(config_path=minimal_config_yaml, env_path=None)

    def test_invalid_allowed_chat_id_non_integer(self, monkeypatch, minimal_config_yaml):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid_token")
        monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
        monkeypatch.setenv("ALLOWED_CHAT_ID", "not_a_number")
        with pytest.raises(ValueError, match="ALLOWED_CHAT_ID must be a valid integer"):
            load_config(config_path=minimal_config_yaml, env_path=None)

    def test_zero_allowed_chat_id(self, monkeypatch, minimal_config_yaml):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid_token")
        monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
        monkeypatch.setenv("ALLOWED_CHAT_ID", "0")
        with pytest.raises(ValueError, match="ALLOWED_CHAT_ID cannot be zero"):
            load_config(config_path=minimal_config_yaml, env_path=None)

    def test_whitespace_and_negative_allowed_chat_id(self, monkeypatch, minimal_config_yaml):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "valid_token")
        monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
        monkeypatch.setenv("ALLOWED_CHAT_ID", "  -100123456789  ")
        cfg = load_config(config_path=minimal_config_yaml, env_path=None)
        assert cfg.allowed_chat_id == -100123456789
        assert isinstance(cfg.allowed_chat_id, int)

    def test_missing_yaml_file(self, valid_env_vars):
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config(config_path="non_existent_file.yaml", env_path=None)

    def test_invalid_yaml_syntax(self, valid_env_vars, tmp_path):
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("app:\n  timezone: [unclosed list", encoding="utf-8")
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            load_config(config_path=str(bad_yaml), env_path=None)

    def test_invalid_timezone(self, valid_env_vars, tmp_path):
        bad_tz_yaml = tmp_path / "bad_tz.yaml"
        bad_tz_yaml.write_text("app:\n  timezone: 'Invalid/City'", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid timezone"):
            load_config(config_path=str(bad_tz_yaml), env_path=None)

    def test_invalid_time_format(self, valid_env_vars, tmp_path):
        bad_time_yaml = tmp_path / "bad_time.yaml"
        bad_time_yaml.write_text("schedules:\n  gym:\n    time_split1: '25:99'", encoding="utf-8")
        with pytest.raises(ValueError, match="Invalid time value"):
            load_config(config_path=str(bad_time_yaml), env_path=None)

    def test_toeic_rotation_from_dict(self, valid_env_vars, tmp_path):
        yaml_content = """
schedules:
  toeic:
    time: "19:25"
    rotation:
      mon: "Part 1"
      tue: "Part 2"
      wed: "Part 3"
      thu: "Part 4"
      fri: "Part 5"
      sat: "Part 6"
      sun: "Part 7"
"""
        yaml_file = tmp_path / "dict_toeic.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        cfg = load_config(config_path=str(yaml_file), env_path=None)
        assert len(cfg.toeic.syllabus_rotation) == 7
        assert cfg.toeic.syllabus_rotation[0] == "Part 1"
        assert cfg.toeic.syllabus_rotation[6] == "Part 7"

    def test_toeic_rotation_invalid_length(self, valid_env_vars, tmp_path):
        yaml_content = """
schedules:
  toeic:
    time: "19:25"
    syllabus_rotation:
      - "Part 1"
      - "Part 2"
"""
        yaml_file = tmp_path / "short_toeic.yaml"
        yaml_file.write_text(yaml_content, encoding="utf-8")
        with pytest.raises(ValueError, match="TOEIC syllabus rotation must contain exactly 7 items"):
            load_config(config_path=str(yaml_file), env_path=None)


class TestHelpers:
    def test_mask_secret(self):
        assert mask_secret("1234567890abcdef") == "1234...cdef"
        assert mask_secret("short") == "***"
        assert mask_secret("") == ""
