"""
Domain data models for Telegram Chat exports.
"""

from __future__ import annotations
import json
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ReactionItem(BaseModel):
    """Individual reaction detail for a message."""
    emoji: str = Field(..., description="Reaction emoji character")
    count: int = Field(default=1, description="Number of users who reacted with this emoji")
    users: List[str] = Field(default_factory=list, description="Names of users who reacted if available")


class MediaItem(BaseModel):
    """Media attachment detail (photo, voice, video, document, etc.)."""
    type: str = Field(default="photo", description="Type of media (photo, voice_message, video, file, sticker)")
    file_path: Optional[str] = Field(default=None, description="Relative path to media file")
    thumbnail_path: Optional[str] = Field(default=None, description="Relative path to thumbnail image")
    width: Optional[int] = Field(default=None, description="Image/video width in pixels")
    height: Optional[int] = Field(default=None, description="Image/video height in pixels")


class TelegramMessage(BaseModel):
    """Parsed Telegram message record."""
    id: int = Field(..., description="Numeric message identifier")
    type: str = Field(default="message", description="Type of message ('message' or 'service')")
    date: Optional[str] = Field(default=None, description="ISO-formatted or full timestamp")
    time: Optional[str] = Field(default=None, description="Display time string (e.g. '14:36')")
    from_name: Optional[str] = Field(default=None, description="Sender name")
    reply_to_message_id: Optional[int] = Field(default=None, description="Referenced reply message ID")
    forwarded_from: Optional[str] = Field(default=None, description="Original sender if message was forwarded")
    text: str = Field(default="", description="Text content with formatting preserved")
    media: Optional[MediaItem] = Field(default=None, description="Attached media information")
    reaction_count: int = Field(default=0, description="Total count of reactions on this message")
    reactions: List[ReactionItem] = Field(default_factory=list, description="List of reactions on this message")


class TelegramChat(BaseModel):
    """Root container representing parsed Telegram chat export."""
    chat_title: str = Field(default="", description="Name of the channel, group, or contact")
    export_source: Optional[str] = Field(default=None, description="Source file or path of exported HTML")
    total_messages: int = Field(default=0, description="Total count of messages parsed")
    messages: List[TelegramMessage] = Field(default_factory=list, description="List of chat messages")

    def to_dict(self) -> dict[str, Any]:
        """Convert chat model to python dictionary."""
        return self.model_dump()

    def to_json(self, indent: int = 2) -> str:
        """Serialize chat model to formatted JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

