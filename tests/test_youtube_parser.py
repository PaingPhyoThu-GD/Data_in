"""
Unit and integration tests for Service 4: YouTube Channel Data to JSON Parser.
"""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from youtube_parser import (
    YouTubeChannelConverter,
    YouTubeChannelParser,
    YouTubeHTMLParser,
    normalize_channel_url,
)
from youtube_parser.extractors.html_extractor import (
    parse_count_text_to_int,
    parse_duration_to_seconds,
)


@pytest.fixture
def sample_html_path() -> Path:
    return Path(__file__).resolve().parent.parent / "sample_youtube" / "sample_channel.html"


@pytest.fixture
def sample_json_path() -> Path:
    return Path(__file__).resolve().parent.parent / "sample_youtube" / "sample_channel.json"


def test_parse_duration_to_seconds() -> None:
    assert parse_duration_to_seconds("14:25") == 865
    assert parse_duration_to_seconds("1:02:15") == 3735
    assert parse_duration_to_seconds("0:58") == 58
    assert parse_duration_to_seconds(None) is None
    assert parse_duration_to_seconds("invalid") is None


def test_parse_count_text_to_int() -> None:
    assert parse_count_text_to_int("18.5M subscribers") == 18500000
    assert parse_count_text_to_int("450K views") == 450000
    assert parse_count_text_to_int("1,234 views") == 1234
    assert parse_count_text_to_int("2.4M views") == 2400000
    assert parse_count_text_to_int(None) is None


def test_normalize_channel_url() -> None:
    assert normalize_channel_url("@veritasium") == "https://www.youtube.com/@veritasium/videos"
    assert normalize_channel_url("mkbhd") == "https://www.youtube.com/@mkbhd/videos"
    assert (
        normalize_channel_url("https://www.youtube.com/@veritasium")
        == "https://www.youtube.com/@veritasium/videos"
    )
    assert (
        normalize_channel_url("https://www.youtube.com/@veritasium/videos")
        == "https://www.youtube.com/@veritasium/videos"
    )


def test_parse_sample_channel_html(sample_html_path: Path) -> None:
    assert sample_html_path.exists()
    parser = YouTubeChannelParser()
    result = parser.parse_file(sample_html_path)

    assert result.status == "success"
    info = result.channel_info
    assert info.channel_name == "TechPulse Explains"
    assert info.subscriber_count_text == "1.45M subscribers"
    assert info.subscriber_count == 1450000
    assert info.is_verified is True
    assert result.total_videos == 3
    assert len(result.videos) == 3

    # Check first video
    v1 = result.videos[0]
    assert "Autonomous Multi-Agent AI Systems" in v1.title
    assert v1.video_id == "v_ai_agent_01"
    assert v1.duration_text == "18:42"
    assert v1.duration_seconds == 1122
    assert v1.view_count == 482000
    assert v1.is_short is False

    # Check short video
    v_short = result.videos[2]
    assert v_short.video_id == "v_short_python_tip"
    assert v_short.is_short is True


def test_parse_sample_channel_json(sample_json_path: Path) -> None:
    assert sample_json_path.exists()
    parser = YouTubeChannelParser()
    result = parser.parse_file(sample_json_path)

    assert result.status == "success"
    assert result.channel_info.handle == "@TechPulseOfficial"
    assert result.total_videos == 8
    assert len(result.videos) == 8


def test_converter_writes_valid_json(sample_html_path: Path, tmp_path: Path) -> None:
    converter = YouTubeChannelConverter()
    out_file = tmp_path / "output_test_channel.json"

    result = converter.convert_file(sample_html_path, output_json_path=out_file)
    assert out_file.exists()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["status"] == "success"
    assert data["channel_info"]["channel_name"] == "TechPulse Explains"
    assert len(data["videos"]) == 3


def test_invalid_html_raises_value_error() -> None:
    parser = YouTubeChannelParser()
    with pytest.raises(ValueError, match="Could not extract ytInitialData"):
        parser.parse_html("<html><body><h1>Not a youtube page</h1></body></html>")

