"""
Telegram Chat Export Parser Package.
Converts Telegram Desktop HTML exports (messages.html) into structured JSON.
"""

from telegram_parser.models import (
    MediaItem,
    ReactionItem,
    TelegramChat,
    TelegramMessage,
)
from telegram_parser.parser import (
    TelegramChatConverter,
    TelegramHTMLParser,
    parse_telegram_date,
)

__all__ = [
    "TelegramHTMLParser",
    "TelegramChatConverter",
    "TelegramChat",
    "TelegramMessage",
    "ReactionItem",
    "MediaItem",
    "parse_telegram_date",
]

