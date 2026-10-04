"""Composition root and application entrypoint for Autonomous Telegram Personal Accountability Coach.

Orchestrates configuration loading, persistence initialization, AI coach service,
proactive APScheduler jobs, Telegram bot application, and graceful Windows/Unix shutdown.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
from pathlib import Path
import signal
import sys
from typing import Any, Optional, Tuple
from zoneinfo import ZoneInfo

# Ensure project root directory is on sys.path so 'src.*' imports succeed
# regardless of whether executed as `python src/main.py`, `python -m src.main`, or from external directories.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import AppConfig, load_config
from src.storage import AtomicJsonStore
from src.coach import AICoachService
from src.scheduler import SchedulerService
from src.bot import BotApplication, build_application, make_inline_action_keyboard

logger = logging.getLogger("main")


async def format_proactive_message(config: AppConfig, session_type: str, session_name: str) -> str:
    """Formats markdown reminder text based on schedule configuration."""
    now = datetime.now(ZoneInfo(config.timezone))
    weekday = now.weekday()
    weekday_names = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

    if session_type == "gym":
        gym_cfg = config.gym
        window = getattr(gym_cfg, "window_split1", "17:30 – 18:30") if weekday in (0, 1, 3) else getattr(gym_cfg, "window_split2", "16:30 – 17:30")
        template = getattr(gym_cfg, "message_template", None)
        if template:
            return template.format(window=window)
        return f"🏋️‍♂️ *GIỜ TẬP GYM ĐÃ ĐẾN!*\nKhung giờ: `{window}`\nChuẩn bị đồ tập và bắt đầu ngay nào!"

    elif session_type == "toeic":
        toeic_cfg = config.toeic
        part = toeic_cfg.get_part_for_weekday(weekday) if hasattr(toeic_cfg, "get_part_for_weekday") else "Part 1"
        window = getattr(toeic_cfg, "window", "19:30 – 20:30")
        template = getattr(toeic_cfg, "message_template", None)
        if template:
            try:
                return template.format(
                    window=window,
                    topic=part,
                    part_topic=part,
                    weekday_name=weekday_names[weekday],
                )
            except KeyError:
                return f"📚 *GIỜ HỌC TOEIC!*\nChủ đề: *{part}*\nKhung giờ: `{window}`"
        return f"📚 *GIỜ HỌC TOEIC!*\nChủ đề: *{part}*\nKhung giờ: `{window}`"

    elif session_type == "major":
        major_cfg = config.major
        window = getattr(major_cfg, "window", "20:45 – 21:45")
        template = getattr(major_cfg, "message_template", None)
        if template:
            return template.format(window=window)
        return f"💻 *GIỜ CÀY CHUYÊN NGÀNH & GAME DEV!*\nKhung giờ: `{window}`"

    return f"⏰ *NHẮC NHỞ HOÀN THÀNH PHIÊN*: {session_name}"


async def send_proactive_reminder(
    bot: Any,
    config: AppConfig,
    session_type: str,
    session_name: str,
) -> None:
    """Dispatches proactive reminder with 3 inline action buttons to allowed chat."""
    now = datetime.now(ZoneInfo(config.timezone))
    session_id = f"{session_type}_{now.strftime('%Y%m%d')}"
    text = await format_proactive_message(config, session_type, session_name)
    keyboard = make_inline_action_keyboard(session_id)

    try:
        await bot.send_message(
            chat_id=config.allowed_chat_id,
            text=text,
            reply_markup=keyboard,
        )
        logger.info("Proactive reminder dispatched for %s (%s).", session_type, session_id)
    except Exception as exc:
        logger.error("Failed to dispatch proactive reminder: %s", exc, exc_info=True)


def create_system(
    config: Optional[AppConfig] = None,
    storage: Optional[AtomicJsonStore] = None,
    coach: Optional[AICoachService] = None,
    scheduler: Optional[SchedulerService] = None,
    bot: Optional[Any] = None,
) -> Tuple[BotApplication, SchedulerService, AppConfig]:
    """Assembles all application subsystems with dependency injection."""
    if config is None:
        config = load_config()

    if storage is None:
        storage = AtomicJsonStore(file_path=getattr(config, "records_file", "data/records.json"))

    if coach is None:
        coach = AICoachService(
            api_key=config.gemini_api_key,
            model_name=getattr(config, "gemini_model", "gemini-2.5-flash"),
            config=config,
        )

    if scheduler is None:
        scheduler = SchedulerService(timezone_str=config.timezone)

    bot_app = build_application(
        config=config,
        storage=storage,
        coach=coach,
        scheduler=scheduler,
    )
    if bot is not None and hasattr(bot_app, "bot"):
        bot_app.bot = bot

    # Wire proactive cron triggers with push callback
    async def _on_cron_trigger(session_type: str, session_name: str) -> None:
        await bot_app.send_session_reminder(session_type, session_name)

    scheduler.register_scheduled_jobs(config, _on_cron_trigger)
    return bot_app, scheduler, config


async def run_async(
    config: Optional[AppConfig] = None,
    stop_event: Optional[asyncio.Event] = None,
    bot: Optional[Any] = None,
) -> None:
    """Runs the asynchronous bot loop and proactive scheduler."""
    bot_app, scheduler, app_config = create_system(config=config, bot=bot)

    scheduler.start()
    logger.info("Proactive scheduler started in %s timezone.", app_config.timezone)

    try:
        await bot_app.initialize()
        await bot_app.start()
        if bot_app.updater and bot is None:
            try:
                await bot_app.updater.start_polling()
            except Exception as exc:
                logger.warning("Could not start updater polling (offline/mock environment): %s", exc)

        if bot_app.updater and getattr(bot_app.updater, "running", False):
            logger.info("Bot application active. Listening for updates from Telegram...")
        elif bot is None:
            logger.warning(
                "Bot application dang chay o che do offline (chua ket noi duoc toi api.telegram.org).\n"
                "-> Neu ban o Viet Nam, hay bat Cloudflare WARP (1.1.1.1) hoac VPN tren may de ket noi toi Telegram!"
            )
        if stop_event is None:
            stop_event = asyncio.Event()

        await stop_event.wait()
    finally:
        logger.info("Initiating graceful shutdown...")
        scheduler.shutdown()
        if bot_app.updater and getattr(bot_app.updater, "running", False):
            try:
                await bot_app.updater.stop()
            except Exception as exc:
                logger.debug("Updater stop note: %s", exc)
        if getattr(bot_app, "running", False):
            try:
                await bot_app.stop()
            except Exception as exc:
                logger.debug("BotApp stop note: %s", exc)
        try:
            await bot_app.shutdown()
        except Exception as exc:
            logger.debug("BotApp shutdown note: %s", exc)
        logger.info("Shutdown completed cleanly.")


def main() -> None:
    """Command-line entrypoint with Windows & Unix safe signal handling."""
    logging.basicConfig(
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Booting Autonomous Telegram Personal Accountability Coach...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _on_signal(sig: int, frame: Any) -> None:
        logger.info("Signal %s received. Stopping...", sig)
        loop.call_soon_threadsafe(stop_event.set)

    for sig_name in ("SIGINT", "SIGTERM"):
        if hasattr(signal, sig_name):
            try:
                signal.signal(getattr(signal, sig_name), _on_signal)
            except (ValueError, AttributeError) as exc:
                logger.debug("Could not register signal %s: %s", sig_name, exc)

    try:
        loop.run_until_complete(run_async(stop_event=stop_event))
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process halted by user.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
