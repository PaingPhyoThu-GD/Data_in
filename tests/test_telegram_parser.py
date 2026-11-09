"""
Unit and integration tests for Telegram Chat HTML-to-JSON Parser.
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from telegram_parser import (
    TelegramChatConverter,
    TelegramHTMLParser,
    parse_telegram_date,
)

SAMPLE_HTML_PATH = Path("telegram_msg_html/messages.html")


def test_parse_telegram_date_format() -> None:
    raw = "02.11.2026 14:36:02 UTC+06:30"
    iso = parse_telegram_date(raw)
    assert iso == "2026-11-02T14:36:02+06:30"


def test_parse_sample_telegram_chat() -> None:
    assert SAMPLE_HTML_PATH.exists(), "Sample telegram_msg_html/messages.html must exist."

    parser = TelegramHTMLParser(include_service_messages=True)
    chat = parser.parse_file(SAMPLE_HTML_PATH)

    # 1. Chat title
    assert chat.chat_title == "Min Thike Tun"
    assert chat.total_messages > 10

    # 2. Check first regular message
    msg_1 = next(m for m in chat.messages if m.id == 145331)
    assert msg_1.from_name == "Min Thike Tun"
    assert "channel ထောင်ဖို့" in msg_1.text
    assert msg_1.time == "14:36"

    # 3. Check consecutive joined message inherits sender
    msg_2 = next(m for m in chat.messages if m.id == 145332)
    assert msg_2.from_name == "Min Thike Tun"
    assert "မနက်ဖြန် စထောင်ကြမလား" in msg_2.text

    # 4. Check reactions and reaction_count
    reacted_msgs = [m for m in chat.messages if m.reaction_count > 0]
    assert len(reacted_msgs) >= 2
    for rm in reacted_msgs:
        assert len(rm.reactions) > 0
        assert len(rm.reactions[0].emoji) > 0
        assert rm.reaction_count >= 1

    # 5. Check replies
    reply_msgs = [m for m in chat.messages if m.reply_to_message_id is not None]
    assert len(reply_msgs) >= 2
    assert any(m.reply_to_message_id == 145338 for m in reply_msgs)

    # 6. Check media attachments
    media_msgs = [m for m in chat.messages if m.media is not None]
    assert len(media_msgs) >= 1
    photo_msg = media_msgs[0]
    assert photo_msg.media is not None
    assert photo_msg.media.type == "photo"
    assert photo_msg.media.file_path is not None
    assert "photos/" in photo_msg.media.file_path


def test_converter_writes_valid_json(tmp_path: Path) -> None:
    converter = TelegramChatConverter()
    output_file = tmp_path / "output_messages.json"

    chat = converter.convert(
        input_html_path=SAMPLE_HTML_PATH,
        output_json_path=output_file,
        indent=2,
    )

    assert output_file.exists()
    data = json.loads(output_file.read_text(encoding="utf-8"))

    assert data["chat_title"] == "Min Thike Tun"
    assert data["total_messages"] == len(chat.messages)
    assert isinstance(data["messages"], list)


def test_exclude_service_messages() -> None:
    parser_with_service = TelegramHTMLParser(include_service_messages=True)
    chat_all = parser_with_service.parse_file(SAMPLE_HTML_PATH)

    parser_no_service = TelegramHTMLParser(include_service_messages=False)
    chat_no_service = parser_no_service.parse_file(SAMPLE_HTML_PATH)

    assert chat_no_service.total_messages < chat_all.total_messages
    assert all(m.type != "service" for m in chat_no_service.messages)
