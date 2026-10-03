"""Shared test fixtures for Autonomous Telegram Personal Accountability Coach.

Provides isolated environments, temporary file paths, mock environment variables,
and pre-configured store/config instances for zero-network deterministic testing.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Generator
import pytest
import yaml

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
        "DATA_DIR",
        "RECORDS_FILE",
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
        "limits": {
            "max_snoozes": 2,
            "snooze_duration_minutes": 15,
            "micro_habit_duration_minutes": 2,
        },
        "schedules": {
            "gym": {
                "name": "Gym Session",
                "cron_days_split1": "mon,tue,thu",
                "time_split1": "17:15",
                "cron_days_split2": "wed,sat",
                "time_split2": "16:15",
                "duration_minutes": 60,
            },
            "toeic": {
                "name": "TOEIC Study Session",
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
                "name": "Major Subject Study & Game Dev",
                "time": "20:40",
                "duration_minutes": 60,
            },
        },
        "prompts": {
            "system_instruction": "Bạn là huấn luyện viên kỷ luật thực chiến cho sinh viên IT & game dev.",
            "completion_praise": "Khen ngợi ngắn gọn sự kỷ luật và giữ đúng streak cam kết.",
            "snooze_warning_1": "Cảnh báo nhẹ khi lùi giờ lần 1.",
            "snooze_warning_2": "Cảnh báo gắt khi lùi giờ lần 2.",
            "skip_evaluator": "Đánh giá lý do nghỉ.",
            "excuse_evaluation": "Phân tích lý do người dùng xin nghỉ và bẻ gãy lý do nếu lười biếng.",
            "congratulation": "Khen ngợi ngắn gọn sự kỷ luật và giữ đúng streak cam kết.",
        },
        "fallbacks": {
            "offline_coach": "AI tạm thời gián đoạn, nhưng kỷ luật của bạn thì không! Làm việc ngay.",
            "offline_congrats": "Xuất sắc! Đã ghi nhận hoàn thành buổi học/tập hôm nay.",
            "offline_excuse": "Lý do đã được ghi nhận. Nghỉ ngơi và quay lại kỷ luật vào ngày mai.",
            "offline_praise": "Đã ghi nhận hoàn thành! Tiếp tục giữ chuỗi.",
            "offline_snooze_1": "Đã lùi 15 phút lần 1.",
            "offline_snooze_2": "Đã lùi 15 phút lần 2.",
            "offline_skip_excuse": "Lý do chưa thuyết phục.",
            "offline_skip_legitimate": "Đã ghi nhận nghỉ có lý do.",
            "offline_error": "Mất kết nối tạm thời.",
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
        "version": 1,
        "streak": {
            "current_streak": 0,
            "best_streak": 0,
            "last_completed_date": None,
            "total_completions": 0,
        },
        "sessions": {},
        "active_sessions": {},
        "awaiting_reason": None,
        "history": [],
    }


@pytest.fixture
def atomic_store(temp_records_path: Path) -> AtomicJsonStore:
    """Instantiate AtomicJsonStore targeting temporary file."""
    return AtomicJsonStore(file_path=str(temp_records_path))


# =====================================================================
# Additional E2E Offline Mock Fixtures
# =====================================================================

from src.config import load_config, AppConfig
from tests.mock_services import (
    MockTelegramBot,
    MockGeminiClient,
    MockGenerateContentResponse,
    make_text_update,
    make_callback_update,
    make_inline_action_keyboard,
    get_ai_coach_class,
    get_scheduler_class,
    get_build_application_fn,
    DefaultAICoachService,
    DefaultSchedulerService,
    DefaultBotApplication,
)


@pytest.fixture
def app_config(temp_config_yaml_file: Path, temp_env_file: Path) -> AppConfig:
    """Load fully validated AppConfig instance targeting temp config and env files."""
    return load_config(
        config_path=str(temp_config_yaml_file),
        env_path=str(temp_env_file),
    )


@pytest.fixture
def mock_bot(app_config: AppConfig) -> MockTelegramBot:
    """Zero-network mock Telegram bot instance."""
    return MockTelegramBot(token=app_config.bot_token)


@pytest.fixture
def mock_gemini_client(app_config: AppConfig) -> MockGeminiClient:
    """Zero-network mock Gemini client instance."""
    return MockGeminiClient(api_key=app_config.gemini_api_key)


@pytest.fixture
def mock_gemini_error_client(app_config: AppConfig) -> MockGeminiClient:
    """Mock Gemini client configured to trigger network/timeout errors."""
    return MockGeminiClient(api_key=app_config.gemini_api_key, error_mode="timeout")


@pytest.fixture
def scheduler_service(app_config: AppConfig) -> Any:
    """Instantiate scheduler service conforming to PROJECT.md interface contract."""
    cls = get_scheduler_class()
    return cls(timezone_str=app_config.timezone)


@pytest.fixture
def coach_service(
    app_config: AppConfig,
    mock_gemini_client: MockGeminiClient,
    valid_yaml_dict: Dict[str, Any],
) -> Any:
    """Instantiate AI Coach service conforming to PROJECT.md interface contract."""
    cls = get_ai_coach_class()
    return cls(
        api_key=app_config.gemini_api_key,
        model_name=app_config.gemini_model,
        config=valid_yaml_dict,
        client=mock_gemini_client,
    )


@pytest.fixture
def bot_application(
    app_config: AppConfig,
    atomic_store: AtomicJsonStore,
    coach_service: Any,
    scheduler_service: Any,
    mock_bot: MockTelegramBot,
) -> Any:
    """Instantiate Bot Application adhering to PTB Application contract."""
    build_fn = get_build_application_fn()
    app = build_fn(app_config, atomic_store, coach_service, scheduler_service)
    if hasattr(app, "bot"):
        app.bot = mock_bot
    return app
