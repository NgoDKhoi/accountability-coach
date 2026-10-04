"""Configuration loader and schema definitions for Autonomous Telegram Coach.

Strictly decouples secrets (.env) from operational parameters (config.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Dict, List, Optional, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv
import yaml


# =====================================================================
# Default Templates and Fallback Dictionaries
# =====================================================================

DEFAULT_SYSTEM_PROMPT: str = (
    "Bạn là Huấn Luyện Viên Kỷ Luật Cá Nhân (AI Accountability Coach) dành riêng cho một sinh viên IT kiêm lập trình viên game.\n"
    "Phong cách: Trực tiếp, súc tích, mang tư duy kỹ thuật/thực tế, hơi mỉa mai và châm biếm sắc sảo trước sự trì hoãn/lý do bao biện, nhưng nhiệt tình ghi nhận và tôn trọng kỷ luật hành động thực chất.\n"
    "QUY TẮC BẮT BUỘC: Mỗi câu trả lời KHÔNG ĐƯỢC QUÁ 2-3 câu ngắn gọn. Không dài dòng, không nói đạo lý sáo rỗng. Luôn thúc đẩy hành động ngay lập tức."
)

DEFAULT_PROMPTS: Dict[str, str] = {
    "system_instruction": DEFAULT_SYSTEM_PROMPT,
    "completion_praise": (
        "Người dùng vừa hoàn thành phiên {session_name} ({detail}). Streak hiện tại: {streak} ngày liên tiếp.\n"
        "Hãy gửi một câu khen ngợi ngắn gọn (tối đa 2 câu), ghi nhận tính kỷ luật thực chiến của một kỹ sư."
    ),
    "snooze_warning_1": (
        "Người dùng vừa xin lùi 15 phút lần thứ 1 cho phiên {session_name}.\n"
        "Hãy cảnh báo ngắn gọn (tối đa 2 câu) theo phong cách mỉa mai nhẹ về việc trì hoãn, nhắc nhở họ chỉ còn đúng 1 lần lùi nữa."
    ),
    "snooze_warning_2": (
        "Người dùng đã lùi 15 phút lần thứ 2 (ĐÃ ĐẠT GIỚI HẠN TỐI ĐA) cho phiên {session_name}.\n"
        "Hãy ra lệnh dứt khoát, gay gắt (tối đa 2 câu): Hết giờ dây dưa, dẹp điện thoại và bắt tay vào việc ngay lập tức!"
    ),
    "skip_evaluator": (
        "Người dùng muốn bỏ phiên {session_name} ({detail}) với lý do: \"{reason}\".\n"
        "Nhiệm vụ:\n"
        "1. Đánh giá xem đây là lý do bất khả kháng chính đáng (bệnh tật, cấp cứu, sự cố khẩn cấp) hay chỉ là lý do bao biện/lười biếng/trì hoãn.\n"
        "2. Nếu là BAO BIỆN: Bóc trần lý do bằng 1 câu châm biếm sắc bén, và ép thực hiện 'micro-habit 2 phút' (ví dụ: mở sách đọc 2 phút hoặc làm 5 cái chống đẩy) để không đứt chuỗi. Bắt đầu bằng [EXCUSE].\n"
        "3. Nếu là CHÍNH ĐÁNG: Đồng ý cho nghỉ ngơi phục hồi, yêu cầu ngày mai quay lại với 200% năng lượng. Bắt đầu bằng [LEGITIMATE].\n"
        "Quy tắc: Tối đa 2-3 câu ngắn gọn."
    ),
    "excuse_evaluation": (
        "Phân tích lý do người dùng xin nghỉ và bẻ gãy lý do nếu lười biếng."
    ),
    "congratulation": (
        "Khen ngợi ngắn gọn sự kỷ luật và giữ đúng streak cam kết."
    ),
}

DEFAULT_FALLBACKS: Dict[str, str] = {
    "offline_coach": "AI tạm thời gián đoạn, nhưng kỷ luật của bạn thì không! Làm việc ngay.",
    "offline_congrats": "Xuất sắc! Đã ghi nhận hoàn thành buổi học/tập hôm nay.",
    "offline_excuse": "Lý do đã được ghi nhận. Nghỉ ngơi và quay lại kỷ luật vào ngày mai.",
    "offline_praise": "✅ Đã ghi nhận hoàn thành! Kỷ luật tạo nên bản lĩnh. Tiếp tục giữ vững chuỗi streak nhé!",
    "offline_snooze_1": "⏳ Đã lùi 15 phút (Lần 1/2). Bạn còn đúng một cơ hội lùi giờ nữa. Đừng để sự trì hoãn chiến thắng!",
    "offline_snooze_2": "⚠️ ĐÃ ĐẠT GIỚI HẠN LÙI GIỜ (Lần 2/2)! Nghiêm túc dẹp điện thoại và bắt tay vào việc ngay!",
    "offline_skip_excuse": "🛑 Lý do chưa thuyết phục! Hãy làm ngay micro-habit 2 phút: mở tài liệu hoặc hít đất 5 cái trước khi nghỉ!",
    "offline_skip_legitimate": "🛑 Đã ghi nhận nghỉ có lý do chính đáng. Nghỉ ngơi phục hồi và ngày mai quay lại với 200% kỷ luật!",
    "offline_error": "🤖 AI Coach tạm thời mất kết nối mạng, nhưng kỷ luật của bạn thì không được ngắt quãng. Bắt tay vào việc ngay đi!",
}

DEFAULT_TOEIC_ROTATION: List[str] = [
    "Part 1 - Photographs (Mô tả hình ảnh)",
    "Part 2 - Question-Response (Hỏi & Đáp)",
    "Part 3 - Short Conversations (Đối thoại ngắn)",
    "Part 4 - Short Talks (Bài nói ngắn)",
    "Part 5 - Incomplete Sentences (Ngữ pháp & Từ vựng)",
    "Part 6 - Text Completion (Điền đoạn văn)",
    "Part 7 - Reading Comprehension & Full Mock Review",
]


# =====================================================================
# Configuration Dataclasses
# =====================================================================

@dataclass(frozen=True)
class GymScheduleConfig:
    cron_days_split1: str  # e.g. 'mon,tue,thu'
    time_split1: str       # e.g. '17:15'
    cron_days_split2: str  # e.g. 'wed,sat'
    time_split2: str       # e.g. '16:15'
    duration_minutes: int = 60
    name: str = "Gym Session"
    window_split1: str = "17:30 – 18:30"
    window_split2: str = "16:30 – 17:30"
    message_template: str = (
        "🏋️‍♂️ *GIỜ TẬP GYM ĐÃ ĐẾN!*\n"
        "Khung giờ tập: `{window}`\n"
        "Chuẩn bị đồ tập, nạp năng lượng và rời bàn làm việc ngay nào!"
    )

    @property
    def hour_split1(self) -> int:
        return int(self.time_split1.split(":")[0])

    @property
    def minute_split1(self) -> int:
        return int(self.time_split1.split(":")[1])

    @property
    def hour_split2(self) -> int:
        return int(self.time_split2.split(":")[0])

    @property
    def minute_split2(self) -> int:
        return int(self.time_split2.split(":")[1])


@dataclass(frozen=True)
class ToeicScheduleConfig:
    time: str              # e.g. '19:25'
    duration_minutes: int = 60
    syllabus_rotation: List[str] = field(default_factory=list)  # 7 parts (Mon-Sun)
    name: str = "TOEIC Study Session"
    window: str = "19:30 – 20:30"
    message_template: str = (
        "📚 *GIỜ HỌC TOEIC!*\n"
        "Chủ đề hôm nay: *{topic}*\n"
        "Khung giờ học: `{window}`\n"
        "Bật Pomodoro 25/5 và tập trung cao độ, không lướt mạng xã hội!"
    )

    @property
    def hour(self) -> int:
        return int(self.time.split(":")[0])

    @property
    def minute(self) -> int:
        return int(self.time.split(":")[1])

    def get_part_for_weekday(self, weekday: int) -> str:
        """Returns the syllabus topic for weekday (0 = Monday, ..., 6 = Sunday)."""
        if not self.syllabus_rotation:
            return "TOEIC Practice"
        idx = weekday % len(self.syllabus_rotation)
        return self.syllabus_rotation[idx]


@dataclass(frozen=True)
class MajorScheduleConfig:
    time: str              # e.g. '20:40'
    duration_minutes: int = 60
    name: str = "Major Subject Study & Game Dev"
    window: str = "20:45 – 21:45"
    message_template: str = (
        "💻 *GIỜ CÀY CHUYÊN NGÀNH & GAME DEV!*\n"
        "Khung giờ: `{window}`\n"
        "Đào sâu kiến trúc game engine, tối ưu thuật toán và commit code chất lượng!"
    )

    @property
    def hour(self) -> int:
        return int(self.time.split(":")[0])

    @property
    def minute(self) -> int:
        return int(self.time.split(":")[1])


@dataclass(frozen=True)
class AppConfig:
    bot_token: str
    gemini_api_key: str
    allowed_chat_id: int
    timezone: str          # 'Asia/Ho_Chi_Minh'
    max_snoozes: int       # 2
    snooze_minutes: int    # 15
    context_window_size: int  # 10
    gym: GymScheduleConfig
    toeic: ToeicScheduleConfig
    major: MajorScheduleConfig
    prompts: Dict[str, str]
    fallbacks: Dict[str, str]
    gemini_model: str = "gemini-2.5-flash"
    data_dir: str = "data"
    records_file: str = "data/records.json"
    micro_habit_duration_minutes: int = 2
    system_prompt: str = ""
    google_calendar_ical_url: Optional[str] = None

    @property
    def telegram_bot_token(self) -> str:
        return self.bot_token


# =====================================================================
# Validation and Helper Functions
# =====================================================================

def validate_time_format(time_str: str, field_name: str) -> None:
    """Validates that time_str is strictly in HH:MM format and within 00:00 - 23:59."""
    if not isinstance(time_str, str):
        raise ValueError(f"{field_name} must be a string, got {type(time_str).__name__}")
    match = re.match(r"^(\d{2}):(\d{2})$", time_str.strip())
    if not match:
        raise ValueError(f"Invalid time format for {field_name}: '{time_str}'. Expected HH:MM format.")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time value for {field_name}: '{time_str}'. Hour must be 0-23, minute 0-59.")


def mask_secret(secret: str, visible_prefix: int = 4, visible_suffix: int = 4) -> str:
    """Masks secret token for safe logging without exposing credentials."""
    if not secret:
        return ""
    if len(secret) <= (visible_prefix + visible_suffix):
        return "***"
    return f"{secret[:visible_prefix]}...{secret[-visible_suffix:]}"


# =====================================================================
# Main Configuration Loader
# =====================================================================

def load_config(config_path: str = "config.yaml", env_path: Optional[str] = ".env") -> AppConfig:
    """Loads and validates configuration from environment variables (.env) and config.yaml.

    Args:
        config_path: Path to the YAML configuration file. Defaults to 'config.yaml'.
        env_path: Path to the .env file. Defaults to '.env'.

    Returns:
        Validated AppConfig instance.

    Raises:
        FileNotFoundError: If config_path does not exist on disk.
        ValueError: If required secrets are missing, invalid, or validation fails.
    """
    # 1. Load environment variables from env_path if file exists
    # Does not overwrite already set os.environ (supports test fixtures / container envs)
    if env_path and os.path.isfile(env_path):
        load_dotenv(dotenv_path=env_path, override=False)

    # 2. Extract and validate required secrets
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("Missing required environment variable: TELEGRAM_BOT_TOKEN")

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise ValueError("Missing required environment variable: GEMINI_API_KEY")

    raw_chat_id = os.environ.get("ALLOWED_CHAT_ID", "").strip()
    if not raw_chat_id:
        raise ValueError("Missing required environment variable: ALLOWED_CHAT_ID")
    try:
        allowed_chat_id = int(raw_chat_id)
    except ValueError:
        raise ValueError(f"ALLOWED_CHAT_ID must be a valid integer, got '{raw_chat_id}'")
    if allowed_chat_id == 0:
        raise ValueError("ALLOWED_CHAT_ID cannot be zero")

    # 3. Read YAML configuration
    # Optional override via CONFIG_PATH env var if config_path was left as default
    if config_path == "config.yaml" and "CONFIG_PATH" in os.environ:
        config_path = os.environ["CONFIG_PATH"]

    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse YAML configuration from {config_path}: {e}")

    if not yaml_data or not isinstance(yaml_data, dict):
        raise ValueError(f"Configuration file {config_path} is empty or invalid.")

    # 4. Extract and validate app section
    app_data = yaml_data.get("app", {})
    if not isinstance(app_data, dict):
        raise ValueError("The 'app' section in config must be a mapping.")

    timezone_str = app_data.get("timezone", "Asia/Ho_Chi_Minh")
    try:
        ZoneInfo(timezone_str)
    except (ZoneInfoNotFoundError, Exception):
        raise ValueError(f"Invalid timezone '{timezone_str}' specified in configuration.")

    history_limit = int(app_data.get("history_limit", app_data.get("context_window_size", 10)))
    if history_limit < 1:
        raise ValueError(f"history_limit / context_window_size must be >= 1, got {history_limit}")

    data_dir = app_data.get("data_dir", os.environ.get("DATA_DIR", "data"))
    records_file = app_data.get("records_file", os.environ.get("RECORDS_FILE", os.path.join(data_dir, "records.json")))

    # 5. Extract and validate limits section
    limits_data = yaml_data.get("limits", {})
    if not isinstance(limits_data, dict):
        raise ValueError("The 'limits' section in config must be a mapping.")

    max_snoozes_val = limits_data.get("max_snoozes", app_data.get("max_snoozes", 2))
    max_snoozes = int(max_snoozes_val)
    if max_snoozes < 0:
        raise ValueError(f"max_snoozes must be >= 0, got {max_snoozes}")

    snooze_minutes_val = limits_data.get(
        "snooze_duration_minutes",
        limits_data.get("snooze_minutes", app_data.get("snooze_minutes", 15)),
    )
    snooze_minutes = int(snooze_minutes_val)
    if snooze_minutes <= 0:
        raise ValueError(f"snooze_minutes must be > 0, got {snooze_minutes}")

    micro_habit_duration = int(limits_data.get("micro_habit_duration_minutes", 2))

    # 6. Extract and validate schedules section
    if "schedules" not in yaml_data:
        raise ValueError("Missing required section in config: 'schedules'")
    schedules = yaml_data.get("schedules")
    if not isinstance(schedules, dict):
        raise ValueError("The 'schedules' section in config must be a mapping.")

    # Gym Schedule
    if "gym" not in schedules:
        raise ValueError("Missing required schedule subsection: 'gym'")
    gym_data = schedules["gym"]
    if not isinstance(gym_data, dict):
        raise ValueError("Schedule 'gym' must be a mapping.")

    if "triggers" in gym_data and isinstance(gym_data["triggers"], list) and len(gym_data["triggers"]) >= 2:
        t1 = gym_data["triggers"][0]
        t2 = gym_data["triggers"][1]
        t1_days = ",".join(t1["days"]) if isinstance(t1.get("days"), list) else t1.get("days", "mon,tue,thu")
        t2_days = ",".join(t2["days"]) if isinstance(t2.get("days"), list) else t2.get("days", "wed,sat")
        cron_days_split1 = gym_data.get("cron_days_split1", t1_days)
        time_split1 = gym_data.get("time_split1", t1.get("time", "17:15"))
        window_split1 = gym_data.get("window_split1", t1.get("window_display", "17:30 – 18:30"))
        cron_days_split2 = gym_data.get("cron_days_split2", t2_days)
        time_split2 = gym_data.get("time_split2", t2.get("time", "16:15"))
        window_split2 = gym_data.get("window_split2", t2.get("window_display", "16:30 – 17:30"))
    else:
        cron_days_split1 = gym_data.get("cron_days_split1", "mon,tue,thu")
        time_split1 = gym_data.get("time_split1", "17:15")
        window_split1 = gym_data.get("window_split1", "17:30 – 18:30")
        cron_days_split2 = gym_data.get("cron_days_split2", "wed,sat")
        time_split2 = gym_data.get("time_split2", "16:15")
        window_split2 = gym_data.get("window_split2", "16:30 – 17:30")

    validate_time_format(time_split1, "gym.time_split1")
    validate_time_format(time_split2, "gym.time_split2")
    gym_duration = int(gym_data.get("duration_minutes", 60))
    if gym_duration <= 0:
        raise ValueError(f"gym duration_minutes must be > 0, got {gym_duration}")
    gym_name = gym_data.get("name", "Gym Session")
    gym_template = gym_data.get("message_template", (
        "🏋️‍♂️ *GIỜ TẬP GYM ĐÃ ĐẾN!*\n"
        "Khung giờ tập: `{window}`\n"
        "Chuẩn bị đồ tập, nạp năng lượng và rời bàn làm việc ngay nào!"
    ))

    gym_config = GymScheduleConfig(
        cron_days_split1=cron_days_split1,
        time_split1=time_split1,
        cron_days_split2=cron_days_split2,
        time_split2=time_split2,
        duration_minutes=gym_duration,
        name=gym_name,
        window_split1=window_split1,
        window_split2=window_split2,
        message_template=gym_template,
    )

    # TOEIC Schedule
    if "toeic" not in schedules:
        raise ValueError("Missing required schedule subsection: 'toeic'")
    toeic_data = schedules["toeic"]
    if not isinstance(toeic_data, dict):
        raise ValueError("Schedule 'toeic' must be a mapping.")

    toeic_time = toeic_data.get("time", toeic_data.get("trigger_time", "19:25"))
    validate_time_format(toeic_time, "toeic.time")
    toeic_duration = int(toeic_data.get("duration_minutes", 60))
    if toeic_duration <= 0:
        raise ValueError(f"toeic duration_minutes must be > 0, got {toeic_duration}")
    toeic_name = toeic_data.get("name", "TOEIC Study Session")
    toeic_window = toeic_data.get("window", "19:30 – 20:30")
    toeic_template = toeic_data.get("message_template", (
        "📚 *GIỜ HỌC TOEIC!*\n"
        "Chủ đề hôm nay: *{topic}*\n"
        "Khung giờ học: `{window}`\n"
        "Bật Pomodoro 25/5 và tập trung cao độ, không lướt mạng xã hội!"
    ))

    raw_rotation = toeic_data.get("syllabus_rotation", toeic_data.get("rotation", None))
    if raw_rotation is None:
        raw_rotation = yaml_data.get("toeic_syllabus", DEFAULT_TOEIC_ROTATION)

    if isinstance(raw_rotation, dict):
        days_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if any(k in raw_rotation for k in days_order):
            toeic_rotation = [str(raw_rotation.get(d, f"Part {i+1}")) for i, d in enumerate(days_order)]
        elif any(k in raw_rotation for k in [0, 1, 2, 3, 4, 5, 6, "0", "1", "2", "3", "4", "5", "6"]):
            toeic_rotation = [str(raw_rotation.get(i, raw_rotation.get(str(i), f"Part {i+1}"))) for i in range(7)]
        else:
            toeic_rotation = list(raw_rotation.values())
    elif isinstance(raw_rotation, list):
        toeic_rotation = [str(item) for item in raw_rotation]
    else:
        toeic_rotation = list(DEFAULT_TOEIC_ROTATION)

    if len(toeic_rotation) != 7:
        raise ValueError(
            f"TOEIC syllabus rotation must contain exactly 7 items (one for each day), got {len(toeic_rotation)}"
        )

    toeic_config = ToeicScheduleConfig(
        time=toeic_time,
        duration_minutes=toeic_duration,
        syllabus_rotation=toeic_rotation,
        name=toeic_name,
        window=toeic_window,
        message_template=toeic_template,
    )

    # Major Subject Schedule
    if "major" not in schedules:
        raise ValueError("Missing required schedule subsection: 'major'")
    major_data = schedules["major"]
    if not isinstance(major_data, dict):
        raise ValueError("Schedule 'major' must be a mapping.")

    major_time = major_data.get("time", major_data.get("trigger_time", "20:40"))
    validate_time_format(major_time, "major.time")
    major_duration = int(major_data.get("duration_minutes", 60))
    if major_duration <= 0:
        raise ValueError(f"major duration_minutes must be > 0, got {major_duration}")
    major_name = major_data.get("name", "Major Subject Study & Game Dev")
    major_window = major_data.get("window", "20:45 – 21:45")
    major_template = major_data.get("message_template", (
        "💻 *GIỜ CÀY CHUYÊN NGÀNH & GAME DEV!*\n"
        "Khung giờ: `{window}`\n"
        "Đào sâu kiến trúc game engine, tối ưu thuật toán và commit code chất lượng!"
    ))

    major_config = MajorScheduleConfig(
        time=major_time,
        duration_minutes=major_duration,
        name=major_name,
        window=major_window,
        message_template=major_template,
    )

    # 7. AI Coach Section
    ai_coach_data = yaml_data.get("ai_coach", yaml_data.get("coach", {}))
    if not isinstance(ai_coach_data, dict):
        ai_coach_data = {}
    gemini_model = ai_coach_data.get("model", "gemini-2.5-flash")
    system_prompt = ai_coach_data.get("system_prompt", DEFAULT_SYSTEM_PROMPT).strip()

    # Prompts: support both top-level 'prompts' and nested 'ai_coach.prompts'
    prompts = dict(DEFAULT_PROMPTS)
    source_prompts = yaml_data.get("prompts") or ai_coach_data.get("prompts", {})
    if isinstance(source_prompts, dict):
        for k, v in source_prompts.items():
            if v:
                prompts[k] = str(v).strip()

    # Fallbacks: support both top-level 'fallbacks' and nested 'ai_coach.fallbacks'
    fallbacks = dict(DEFAULT_FALLBACKS)
    source_fallbacks = yaml_data.get("fallbacks") or ai_coach_data.get("fallbacks", {})
    if isinstance(source_fallbacks, dict):
        for k, v in source_fallbacks.items():
            if v:
                fallbacks[k] = str(v).strip()

    # 8. Google Calendar iCal configuration (Optional)
    google_calendar_ical_url = os.environ.get("GOOGLE_CALENDAR_ICAL_URL", "").strip() or None
    if not google_calendar_ical_url and "google_calendar" in yaml_data:
        gc_data = yaml_data.get("google_calendar")
        if isinstance(gc_data, dict):
            google_calendar_ical_url = gc_data.get("ical_url", None)

    # 9. Instantiate and return AppConfig
    return AppConfig(
        bot_token=bot_token,
        gemini_api_key=gemini_api_key,
        allowed_chat_id=allowed_chat_id,
        timezone=timezone_str,
        max_snoozes=max_snoozes,
        snooze_minutes=snooze_minutes,
        context_window_size=history_limit,
        gym=gym_config,
        toeic=toeic_config,
        major=major_config,
        prompts=prompts,
        fallbacks=fallbacks,
        gemini_model=gemini_model,
        data_dir=data_dir,
        records_file=records_file,
        micro_habit_duration_minutes=micro_habit_duration,
        system_prompt=system_prompt,
        google_calendar_ical_url=google_calendar_ical_url,
    )
