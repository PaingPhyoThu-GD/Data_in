"""
Main orchestrator classes for YouTube Channel parsing and conversion to JSON.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

from youtube_parser.extractors.html_extractor import YouTubeHTMLParser
from youtube_parser.extractors.network_fetcher import fetch_channel_html, normalize_channel_url
from youtube_parser.models import YouTubeChannelExportResult


class YouTubeChannelParser:
    """
    Parser to extract structured YouTube channel information from live URLs,
    saved HTML files, or raw JSON data.
    """

    def __init__(self, html_parser: Optional[YouTubeHTMLParser] = None) -> None:
        self.html_parser = html_parser or YouTubeHTMLParser()

    def parse_html(self, html_content: str) -> YouTubeChannelExportResult:
        """Parses raw HTML string containing YouTube channel data."""
        return self.html_parser.parse(html_content)

    def parse_file(self, file_path: str | Path) -> YouTubeChannelExportResult:
        """Parses a local HTML or JSON file containing YouTube channel data."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        content = p.read_text(encoding="utf-8", errors="replace")
        return self.parse_html(content)

    def fetch_and_parse(self, query_or_url: str, timeout: int = 15) -> YouTubeChannelExportResult:
        """Fetches a YouTube channel page over the network and parses it."""
        html = fetch_channel_html(query_or_url, timeout=timeout)
        result = self.parse_html(html)
        # Ensure custom URL matches queried channel if not already set
        if not result.channel_info.custom_url:
            try:
                result.channel_info.custom_url = normalize_channel_url(query_or_url)
            except Exception:
                pass
        return result


class YouTubeChannelConverter:
    """
    Convenience wrapper to convert YouTube channels or exports to JSON files.
    """

    def __init__(self, parser: Optional[YouTubeChannelParser] = None) -> None:
        self.parser = parser or YouTubeChannelParser()

    def convert_url(
        self,
        query_or_url: str,
        output_json_path: Optional[str | Path] = None,
        indent: int = 2,
        timeout: int = 15,
    ) -> YouTubeChannelExportResult:
        result = self.parser.fetch_and_parse(query_or_url, timeout=timeout)
        if output_json_path:
            self._write_output(result, output_json_path, indent=indent)
        return result

    def convert_file(
        self,
        file_path: str | Path,
        output_json_path: Optional[str | Path] = None,
        indent: int = 2,
    ) -> YouTubeChannelExportResult:
        result = self.parser.parse_file(file_path)
        if output_json_path:
            self._write_output(result, output_json_path, indent=indent)
        return result

    def _write_output(
        self,
        result: YouTubeChannelExportResult,
        output_json_path: str | Path,
        indent: int = 2,
    ) -> None:
        out_p = Path(output_json_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=indent)

