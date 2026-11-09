"""
Data models for YouTube Channel Data Extraction and Export.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class YouTubeVideo(BaseModel):
    """
    Representation of an individual YouTube video extracted from a channel.
    """
    video_id: str
    title: str
    url: str
    thumbnail_url: Optional[str] = None
    duration_text: Optional[str] = None
    duration_seconds: Optional[int] = None
    view_count_text: Optional[str] = None
    view_count: Optional[int] = None
    published_time_text: Optional[str] = None
    is_short: bool = False
    description_snippet: Optional[str] = None


class YouTubeChannelInfo(BaseModel):
    """
    Detailed metadata for a YouTube channel.
    """
    channel_id: Optional[str] = None
    channel_name: str
    handle: Optional[str] = None
    description: Optional[str] = None
    subscriber_count_text: Optional[str] = None
    subscriber_count: Optional[int] = None
    total_videos_text: Optional[str] = None
    total_videos_count: Optional[int] = None
    avatar_url: Optional[str] = None
    banner_url: Optional[str] = None
    is_verified: bool = False
    custom_url: Optional[str] = None
    joined_date_text: Optional[str] = None


class YouTubeChannelExportResult(BaseModel):
    """
    Complete exported dataset for a YouTube channel.
    """
    status: str = "success"
    channel_info: YouTubeChannelInfo
    total_videos: int = 0
    videos: list[YouTubeVideo] = Field(default_factory=list)
    scraped_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

