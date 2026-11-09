"""
Telegram Desktop HTML chat export parser and JSON converter.
"""

from __future__ import annotations
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional
from bs4 import BeautifulSoup, Tag

from telegram_parser.models import (
    MediaItem,
    ReactionItem,
    TelegramChat,
    TelegramMessage,
)

logger = logging.getLogger(__name__)


def parse_telegram_date(date_str: str) -> Optional[str]:
    """
    Parse Telegram Desktop date title string (e.g., '02.11.2026 14:36:02 UTC+06:30')
    into standard ISO 8601 string: '2026-11-02T14:36:02+06:30'.
    """
    if not date_str:
        return None

    # Pattern: DD.MM.YYYY HH:MM:SS UTC+HH:MM
    match = re.match(
        r"^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2}):(\d{2})(?:\s+UTC([+-]\d{2}):?(\d{2}))?",
        date_str.strip(),
    )
    if match:
        day, month, year, hour, minute, second, tz_sign, tz_min = match.groups()
        iso = f"{year}-{month}-{day}T{hour}:{minute}:{second}"
        if tz_sign:
            iso += f"{tz_sign}:{tz_min}"
        return iso

    return date_str.strip()


class TelegramHTMLParser:
    """
    Parses Telegram Desktop 'messages.html' files into structured TelegramChat domain models.
    """

    def __init__(self, include_service_messages: bool = True) -> None:
        self.include_service_messages = include_service_messages

    def parse_file(self, file_path: str | Path) -> TelegramChat:
        """Parse an HTML file from path."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Telegram export file not found: {path}")

        content = path.read_text(encoding="utf-8", errors="replace")
        chat = self.parse_html(content)
        chat.export_source = str(path)
        return chat

    def parse_html(self, html_content: str) -> TelegramChat:
        """Parse raw HTML content string."""
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Chat Title
        title_elem = soup.find("div", class_="text bold")
        chat_title = title_elem.get_text(strip=True) if title_elem else "Telegram Chat"

        # 2. Iterate through message blocks
        messages: List[TelegramMessage] = []
        current_sender: Optional[str] = None
        current_service_date: Optional[str] = None

        message_nodes = soup.find_all("div", class_="message")

        for node in message_nodes:
            classes = node.get("class", [])

            # Extract numeric message ID
            raw_id = node.get("id", "")
            id_match = re.search(r"message(-?\d+)", raw_id)
            msg_id = int(id_match.group(1)) if id_match else 0

            # Handle Service Messages (Date headers, status notices)
            if "service" in classes:
                body_elem = node.find(class_="body")
                service_text = body_elem.get_text(strip=True) if body_elem else ""

                # Keep track of date if service message represents day change
                current_service_date = service_text

                if self.include_service_messages:
                    messages.append(
                        TelegramMessage(
                            id=msg_id,
                            type="service",
                            date=current_service_date,
                            text=service_text,
                            reaction_count=0,
                            reactions=[],
                        )
                    )
                continue

            # Regular Message Handling
            body_node = node.find("div", class_="body")
            if not body_node:
                continue

            # Sender Name (with consecutive .joined propagation)
            from_name_elem = body_node.find("div", class_="from_name")
            if from_name_elem:
                current_sender = from_name_elem.get_text(strip=True)
            elif "joined" in classes:
                # Inherit current_sender from previous message
                pass
            else:
                # If neither from_name nor joined, check initials or keep current
                pass

            # Date and Time
            date_elem = body_node.find("div", class_="date")
            raw_date_title = date_elem.get("title", "") if date_elem else ""
            display_time = date_elem.get_text(strip=True) if date_elem else ""
            iso_date = parse_telegram_date(raw_date_title)

            # Reply To
            reply_to_id: Optional[int] = None
            reply_elem = body_node.find("div", class_="reply_to")
            if reply_elem:
                reply_link = reply_elem.find("a")
                if reply_link:
                    link_href = reply_link.get("href", "")
                    link_onclick = reply_link.get("onclick", "")
                    rep_match = re.search(r"(\d+)", link_onclick) or re.search(r"message(\d+)", link_href)
                    if rep_match:
                        reply_to_id = int(rep_match.group(1))

            # Forwarded From
            forwarded_from: Optional[str] = None
            fwd_elem = body_node.find("div", class_="forwarded")
            if fwd_elem:
                fwd_from_elem = fwd_elem.find("div", class_="from_name")
                if fwd_from_elem:
                    forwarded_from = fwd_from_elem.get_text(strip=True)

            # Text extraction (preserve <br> line breaks)
            text_elem = body_node.find("div", class_="text")
            message_text = ""
            if text_elem:
                # Replace <br> with newlines
                for br in text_elem.find_all(["br", "br/"]):
                    br.replace_with("\n")
                message_text = text_elem.get_text().strip()

            # Media parsing
            media_item: Optional[MediaItem] = self._parse_media(body_node)

            # Reactions parsing
            reactions_list, total_reactions = self._parse_reactions(body_node)

            message_obj = TelegramMessage(
                id=msg_id,
                type="message",
                date=iso_date,
                time=display_time,
                from_name=current_sender,
                reply_to_message_id=reply_to_id,
                forwarded_from=forwarded_from,
                text=message_text,
                media=media_item,
                reaction_count=total_reactions,
                reactions=reactions_list,
            )
            messages.append(message_obj)

        return TelegramChat(
            chat_title=chat_title,
            total_messages=len(messages),
            messages=messages,
        )

    def _parse_media(self, body_node: Tag) -> Optional[MediaItem]:
        """Parse media attachment from message body if present."""
        media_wrap = body_node.find("div", class_="media_wrap")
        if not media_wrap:
            return None

        # 1. Photo
        photo_link = media_wrap.find("a", class_="photo_wrap")
        if photo_link:
            file_href = photo_link.get("href")
            img_tag = photo_link.find("img")
            thumb_src = img_tag.get("src") if img_tag else None

            # Parse width/height if present in inline style
            width, height = None, None
            style_str = img_tag.get("style", "") if img_tag else ""
            w_match = re.search(r"width:\s*(\d+)px", style_str)
            h_match = re.search(r"height:\s*(\d+)px", style_str)
            if w_match:
                width = int(w_match.group(1))
            if h_match:
                height = int(h_match.group(1))

            return MediaItem(
                type="photo",
                file_path=file_href,
                thumbnail_path=thumb_src,
                width=width,
                height=height,
            )

        # 2. Voice Message
        voice_elem = media_wrap.find("a", class_="media_voice_message")
        if voice_elem:
            return MediaItem(
                type="voice_message",
                file_path=voice_elem.get("href"),
            )

        # 3. Video
        video_elem = media_wrap.find("a", class_="video_file_wrap")
        if video_elem:
            return MediaItem(
                type="video",
                file_path=video_elem.get("href"),
            )

        # 4. Generic Document / File
        doc_elem = media_wrap.find("a", class_="media_file")
        if doc_elem:
            return MediaItem(
                type="document",
                file_path=doc_elem.get("href"),
            )

        return None

    def _parse_reactions(self, body_node: Tag) -> tuple[List[ReactionItem], int]:
        """Extract reaction emojis, counts, user names, and calculate total count."""
        reactions_elem = body_node.find(class_="reactions")
        if not reactions_elem:
            return [], 0

        reaction_items: List[ReactionItem] = []
        total_count = 0

        reaction_spans = reactions_elem.find_all(class_="reaction")
        for r_span in reaction_spans:
            emoji_elem = r_span.find(class_="emoji")
            emoji = emoji_elem.get_text(strip=True) if emoji_elem else ""
            if not emoji:
                continue

            # Users who reacted (from userpics/initials title)
            user_names = []
            for init in r_span.find_all(class_="initials"):
                title = init.get("title")
                if title:
                    user_names.append(title.strip())

            # Check explicit count badge if exists (e.g. <span class="count">2</span>)
            count_elem = r_span.find(class_="count")
            if count_elem and count_elem.get_text(strip=True).isdigit():
                count = int(count_elem.get_text(strip=True))
            elif user_names:
                count = len(user_names)
            else:
                count = 1

            total_count += count
            reaction_items.append(
                ReactionItem(
                    emoji=emoji,
                    count=count,
                    users=user_names,
                )
            )

        return reaction_items, total_count


class TelegramChatConverter:
    """
    Coordinates file ingestion, parsing, and JSON serialization.
    """

    def __init__(self, parser: Optional[TelegramHTMLParser] = None) -> None:
        self.parser = parser or TelegramHTMLParser()

    def convert(
        self,
        input_html_path: str | Path,
        output_json_path: Optional[str | Path] = None,
        indent: int = 2,
    ) -> TelegramChat:
        """
        Convert a Telegram messages.html file into a TelegramChat object
        and optionally write to a JSON file.
        """
        in_path = Path(input_html_path).resolve()
        chat = self.parser.parse_file(in_path)

        if output_json_path:
            out_path = Path(output_json_path).resolve()
        else:
            # Default to messages.json alongside input file
            out_path = in_path.with_name("messages.json")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(chat.to_json(indent=indent), encoding="utf-8")
        logger.info(f"Telegram chat converted and written to: {out_path}")

        return chat
