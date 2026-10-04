"""Bot handlers module.

Exposes bot application and callback handlers from src.bot for naming compatibility.
"""

from src.bot import (
    BotApplication,
    build_application,
    make_inline_action_keyboard,
)

__all__ = [
    "BotApplication",
    "build_application",
    "make_inline_action_keyboard",
]
