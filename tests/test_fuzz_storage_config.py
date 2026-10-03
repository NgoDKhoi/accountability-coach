"""Adversarial boundary fuzzing and stress tests for Milestone 1.

Fuzzes load_config and stress-tests AtomicJsonStore against corruptions,
zero-byte files, invalid roots, permission edge cases, and high concurrency.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import stat
import pytest
import yaml

from src.config import (
    AppConfig,
    load_config,
    validate_time_format,
)
from src.storage import (
    AtomicJsonStore,
    SessionStatus,
    StreakData,
)


# =====================================================================
# 1. BOUNDARY FUZZING: load_config
# =====================================================================

class TestConfigBoundaryFuzzing:
    """Adversarial input tests for config loading and environment variables."""

    @pytest.mark.parametrize(
        "malformed_id",
        [
            "🤖_bot",
            "12345abc",
            "123-456",
            "id:12345",
            "0x123",
            "0o77",
            "NaN",
            "Infinity",
            "-inf",
            "1e5",
            "' OR 1=1 --",
            "12345;rm -rf /",
            "   ",
            "\t\r\n",
            "None",
            "null",
            "undefined",
            "true",
            "false",
        ],
    )
    def test_malformed_allowed_chat_id_rejected(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        malformed_id: str,
    ):
        env = valid_env_dict.copy()
        env["ALLOWED_CHAT_ID"] = malformed_id
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        with pytest.raises(ValueError, match="ALLOWED_CHAT_ID"):
            load_config(str(temp_config_yaml_file), env_path="none.env")

    def test_null_char_in_dotenv_file(
        self,
        tmp_path: Path,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        clean_env: None,
    ):
        env_file = tmp_path / ".env"
        # Test null byte in .env file
        env_file.write_bytes(b"TELEGRAM_BOT_TOKEN=token\nGEMINI_API_KEY=key\nALLOWED_CHAT_ID=12345\x00extra\n")
        with pytest.raises(ValueError, match="embedded null|ALLOWED_CHAT_ID"):
            load_config(str(temp_config_yaml_file), env_path=str(env_file))

    @pytest.mark.parametrize(
        "extreme_id,expected",
        [
            ("-1001234567890", -1001234567890),  # Valid Telegram Supergroup / Channel
            ("-1", -1),                          # Valid negative ID
            (str(10**25), 10**25),               # Extreme large integer
            (str(-10**25), -10**25),             # Extreme negative integer
        ],
    )
    def test_extreme_and_negative_chat_ids(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        extreme_id: str,
        expected: int,
    ):
        env = valid_env_dict.copy()
        env["ALLOWED_CHAT_ID"] = extreme_id
        for k, v in env.items():
            monkeypatch.setenv(k, v)

        cfg = load_config(str(temp_config_yaml_file), env_path="none.env")
        assert cfg.allowed_chat_id == expected

    @pytest.mark.parametrize(
        "raw_secret",
        ["", "   ", "\t\t", "\n\r"],
    )
    def test_empty_or_whitespace_tokens(
        self,
        monkeypatch: pytest.MonkeyPatch,
        clean_env: None,
        temp_config_yaml_file: Path,
        valid_env_dict: dict,
        raw_secret: str,
    ):
        # Bot token
        env1 = valid_env_dict.copy()
        env1["TELEGRAM_BOT_TOKEN"] = raw_secret
        for k, v in env1.items():
            monkeypatch.setenv(k, v)
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            load_config(str(temp_config_yaml_file), env_path="none.env")

        # Gemini API Key
        env2 = valid_env_dict.copy()
        env2["GEMINI_API_KEY"] = raw_secret
        for k, v in env2.items():
            monkeypatch.setenv(k, v)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            load_config(str(temp_config_yaml_file), env_path="none.env")

    @pytest.mark.parametrize(
        "non_dict_content",
        [
            "42\n",
            '"just a string"\n',
            "true\n",
            "null\n",
            "- item1\n- item2\n- item3\n",
        ],
    )
    def test_yaml_non_dict_root_rejected(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        non_dict_content: str,
    ):
        bad_yaml = tmp_path / "nondict.yaml"
        bad_yaml.write_text(non_dict_content, encoding="utf-8")
        with pytest.raises(ValueError, match="empty or invalid"):
            load_config(str(bad_yaml), str(temp_env_file))

    @pytest.mark.parametrize(
        "bad_section,payload",
        [
            ("app", "app: 'not a dict'\nschedules: {}"),
            ("limits", "limits: [1, 2, 3]\nschedules: {}"),
            ("schedules", "schedules: 'invalid_string'"),
            ("schedules_gym", "schedules:\n  gym: 'not a dict'"),
            ("schedules_toeic", "schedules:\n  toeic: [1, 2]"),
            ("schedules_major", "schedules:\n  major: null"),
        ],
    )
    def test_yaml_malformed_section_types(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        bad_section: str,
        payload: str,
    ):
        bad_yaml = tmp_path / f"bad_{bad_section}.yaml"
        bad_yaml.write_text(payload, encoding="utf-8")
        with pytest.raises(ValueError):
            load_config(str(bad_yaml), str(temp_env_file))

    @pytest.mark.parametrize(
        "invalid_tz",
        [
            "Mars/Phobos",
            "Invalid/Timezone",
            "GMT+99",
            "UTC+07:00",  # ZoneInfo requires tz database name, e.g. 'Etc/GMT-7' or 'Asia/Ho_Chi_Minh'
            "",
            "   ",
        ],
    )
    def test_invalid_timezones_rejected(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        invalid_tz: str,
    ):
        data = valid_yaml_dict.copy()
        data["app"] = data["app"].copy()
        data["app"]["timezone"] = invalid_tz
        cfg_file = tmp_path / "bad_tz.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="Invalid timezone"):
            load_config(str(cfg_file), str(temp_env_file))

    @pytest.mark.parametrize(
        "bad_time",
        [
            "24:00",
            "25:00",
            "00:60",
            "-01:00",
            "12:-01",
            "9:00",
            "12:00:00",
            "noon",
            "morning",
            "",
            "   ",
            "12:34:56",
        ],
    )
    def test_validate_time_format_boundaries(self, bad_time: str):
        with pytest.raises(ValueError):
            validate_time_format(bad_time, "test_field")

    def test_unquoted_yaml_sexagesimal_time(
        self,
        tmp_path: Path,
        temp_env_file: Path,
    ):
        # In YAML 1.1, unquoted '17:15' parses as integer 1035
        raw_yaml = """
app:
  timezone: "Asia/Ho_Chi_Minh"
schedules:
  gym:
    cron_days_split1: "mon,tue,thu"
    time_split1: 17:15
    cron_days_split2: "wed,sat"
    time_split2: "16:15"
    duration_minutes: 60
  toeic:
    time: "19:25"
    duration_minutes: 60
    syllabus_rotation:
      - "P1"
      - "P2"
      - "P3"
      - "P4"
      - "P5"
      - "P6"
      - "P7"
  major:
    time: "20:40"
    duration_minutes: 60
"""
        cfg_file = tmp_path / "unquoted_time.yaml"
        cfg_file.write_text(raw_yaml, encoding="utf-8")
        # Should raise clear ValueError that gym.time_split1 must be a string
        with pytest.raises(ValueError, match="must be a string"):
            load_config(str(cfg_file), str(temp_env_file))

    @pytest.mark.parametrize(
        "rotation_input",
        [
            [],
            ["P1"],
            ["P1", "P2", "P3", "P4", "P5", "P6"],
            ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"],
            "not a list",
            12345,
        ],
    )
    def test_broken_toeic_syllabus_rotations(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        rotation_input: any,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"] = data["schedules"].copy()
        data["schedules"]["toeic"] = data["schedules"]["toeic"].copy()
        data["schedules"]["toeic"]["syllabus_rotation"] = rotation_input
        cfg_file = tmp_path / "bad_rot.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        # Non-7 lists raise ValueError. Non-list non-dict falls back to default 7 items
        if isinstance(rotation_input, list) and len(rotation_input) != 7:
            with pytest.raises(ValueError, match="7 items"):
                load_config(str(cfg_file), str(temp_env_file))
        elif not isinstance(rotation_input, (list, dict)):
            # Falls back to default 7 items
            cfg = load_config(str(cfg_file), str(temp_env_file))
            assert len(cfg.toeic.syllabus_rotation) == 7

    @pytest.mark.parametrize(
        "duration_key,bad_duration",
        [
            ("gym", 0),
            ("gym", -10),
            ("toeic", 0),
            ("toeic", -60),
            ("major", 0),
            ("major", -1),
        ],
    )
    def test_negative_or_zero_durations(
        self,
        tmp_path: Path,
        temp_env_file: Path,
        valid_yaml_dict: dict,
        duration_key: str,
        bad_duration: int,
    ):
        data = valid_yaml_dict.copy()
        data["schedules"] = data["schedules"].copy()
        data["schedules"][duration_key] = data["schedules"][duration_key].copy()
        data["schedules"][duration_key]["duration_minutes"] = bad_duration
        cfg_file = tmp_path / f"bad_duration_{duration_key}.yaml"
        with open(cfg_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)

        with pytest.raises(ValueError, match="duration_minutes must be > 0"):
            load_config(str(cfg_file), str(temp_env_file))


# =====================================================================
# 2. STRESS & RECOVERY: AtomicJsonStore
# =====================================================================

@pytest.mark.asyncio
class TestStorageStressAndRecovery:
    """Stress tests and recovery verification for AtomicJsonStore."""

    async def test_zero_byte_file_recovery_and_write(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        # Create 0-byte file
        temp_records_path.write_bytes(b"")
        assert temp_records_path.stat().st_size == 0

        # Read should auto-recover default structure and rewrite file
        data = await atomic_store.load_data()
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0
        assert temp_records_path.stat().st_size > 0

        # Subsequent write should succeed without corruption
        streak = await atomic_store.record_completion("s1", "gym", "2026-10-03")
        assert streak.current_streak == 1
        assert temp_records_path.stat().st_size > 0

    async def test_truncated_json_file_recovery(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path, temp_data_dir: Path
    ):
        # Simulate power outage mid-write: truncated JSON
        temp_records_path.write_text('{"version": 1, "streak": {"cur', encoding="utf-8")

        # Load should detect JSONDecodeError, back up corrupt file, and re-init defaults
        data = await atomic_store.load_data()
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0

        # Verify a .corrupt backup file was created
        files = os.listdir(temp_data_dir)
        corrupt_backups = [f for f in files if ".corrupt." in f]
        assert len(corrupt_backups) == 1

        # File is repaired
        repaired = await atomic_store.get_streak()
        assert repaired.current_streak == 0

    async def test_whitespace_only_file_recovery(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        # Size > 0, but invalid JSON
        temp_records_path.write_text("   \t\r\n   ", encoding="utf-8")
        data = await atomic_store.load_data()
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0

    async def test_binary_garbage_handling(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path, temp_data_dir: Path
    ):
        """Stress: non-UTF8 binary bytes in records.json triggers auto-recovery and backup."""
        temp_records_path.write_bytes(b"\x00\xff\xfe\x01\x02\x03\x04\x05\x06")
        data = await atomic_store.load_data()
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0
        corrupt_backups = [f for f in os.listdir(temp_data_dir) if ".corrupt." in f]
        assert len(corrupt_backups) == 1

    async def test_missing_nested_keys_schema_auto_heal(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        # File has valid JSON but missing keys
        temp_records_path.write_text('{"version": 1}', encoding="utf-8")
        data = await atomic_store.load_data()
        assert "streak" in data
        assert "sessions" in data
        assert "active_sessions" in data
        assert "history" in data

    async def test_json_array_root_behavior(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        """Stress: JSON array '[]' root auto-recovers to default schema object."""
        temp_records_path.write_text("[]", encoding="utf-8")
        data = await atomic_store.load_data()
        assert isinstance(data, dict)
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0

    async def test_json_scalar_root_behavior(
        self, atomic_store: AtomicJsonStore, temp_records_path: Path
    ):
        """Stress: JSON scalar '123' root auto-recovers to default schema object."""
        temp_records_path.write_text("123", encoding="utf-8")
        data = await atomic_store.load_data()
        assert isinstance(data, dict)
        assert data["version"] == 1
        assert data["streak"]["current_streak"] == 0

    async def test_temp_file_leak_on_serialization_failure(
        self, atomic_store: AtomicJsonStore, temp_data_dir: Path
    ):
        """Stress: check if temp files are leaked on Windows NTFS when json.dump raises TypeError.
        Because temp_file.close() is now in a finally block, the open file handle is closed,
        allowing os.remove to delete the temp file on Windows with zero orphaned .tmp files remaining.
        """
        # Non-serializable payload
        with pytest.raises(TypeError):
            await atomic_store.save_data({"unsupported": {1, 2, 3}})

        # Check for lingering .tmp files in data/
        tmp_files = [f for f in os.listdir(temp_data_dir) if f.endswith(".tmp")]
        assert len(tmp_files) == 0

    async def test_high_concurrency_mixed_operations(
        self, atomic_store: AtomicJsonStore
    ):
        """Stress: 50 concurrent mixed tasks (completions, snoozes, skips, reads)."""
        async def completion_task(idx: int):
            await atomic_store.record_completion(
                f"session_c_{idx}", "gym", "2026-10-03"
            )

        async def snooze_task(idx: int):
            await atomic_store.record_snooze(f"session_s_{idx}", new_count=1)

        async def skip_task(idx: int):
            await atomic_store.record_skip(
                f"session_sk_{idx}",
                reason="Tired",
                classification="EXCUSE",
                timestamp_str="2026-10-03T18:00:00+07:00",
            )

        async def reader_task():
            await atomic_store.get_streak()
            await atomic_store.load_data()

        tasks = []
        for i in range(15):
            tasks.append(completion_task(i))
            tasks.append(snooze_task(i))
            tasks.append(skip_task(i))
            tasks.append(reader_task())

        # Run all 60 tasks concurrently
        await asyncio.gather(*tasks)

        final_data = await atomic_store.load_data()
        assert len(final_data["sessions"]) == 45  # 15 completions + 15 snoozes + 15 skips
        assert final_data["streak"]["current_streak"] == 1
        assert final_data["streak"]["total_completions"] == 15
        assert len(final_data["history"]) == 45

    async def test_streak_boundary_year_transition(
        self, atomic_store: AtomicJsonStore
    ):
        await atomic_store.record_completion("s1", "gym", "2025-12-31")
        st1 = await atomic_store.get_streak()
        assert st1.current_streak == 1

        await atomic_store.record_completion("s2", "toeic", "2026-01-01")
        st2 = await atomic_store.get_streak()
        assert st2.current_streak == 2
        assert st2.best_streak == 2

    async def test_streak_boundary_leap_year(
        self, atomic_store: AtomicJsonStore
    ):
        await atomic_store.record_completion("s1", "gym", "2024-02-28")
        assert (await atomic_store.get_streak()).current_streak == 1

        await atomic_store.record_completion("s2", "gym", "2024-02-29")
        assert (await atomic_store.get_streak()).current_streak == 2

        await atomic_store.record_completion("s3", "gym", "2024-03-01")
        assert (await atomic_store.get_streak()).current_streak == 3

    async def test_streak_effective_expiry_calculation(
        self, atomic_store: AtomicJsonStore
    ):
        await atomic_store.record_completion("s1", "gym", "2026-10-01")
        streak = await atomic_store.get_streak()
        assert streak.current_streak == 1

        # Same day
        assert streak.get_effective_streak("2026-10-01") == 1
        # Next day (still active)
        assert streak.get_effective_streak("2026-10-02") == 1
        # 2 days later (streak expired)
        assert streak.get_effective_streak("2026-10-03") == 0
        # 10 days later
        assert streak.get_effective_streak("2026-10-11") == 0
