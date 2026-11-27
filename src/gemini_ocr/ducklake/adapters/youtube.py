"""
Upstream SourceAdapter for youtube_parser.
"""

from __future__ import annotations

from typing import Any

from ..config import LakehouseConfig
from ..models import BronzeEnvelope
from .base import iter_jsonl_records, iter_landing_records, make_envelope


class YouTubeAdapter:
    source_name = "youtube_parser"

    def _to_envelope(
        self,
        *,
        batch_id: str,
        ingested_at: str,
        origin: str,
        source_file: str,
        raw: dict[str, Any],
    ) -> BronzeEnvelope:
        payload = raw.get("data", raw) if isinstance(raw.get("data"), dict) else raw
        channel_info = payload.get("channel_info") or {}
        session_id = raw.get("session_id") or payload.get("session_id")
        if session_id:
            record_key = str(session_id)
        else:
            channel_key = (
                channel_info.get("channel_id")
                or channel_info.get("handle")
                or channel_info.get("channel_name")
                or "unknown"
            )
            record_key = f"{channel_key}|{payload.get('scraped_at', '')}"

        is_test = (
            channel_info.get("channel_name") == "TechPulse Explains"
            or raw.get("source") == "sample_channel.html"
        )
        return make_envelope(
            batch_id=batch_id,
            ingested_at=ingested_at,
            source_name=self.source_name,
            source_origin_type=origin,  # type: ignore[arg-type]
            source_file=source_file,
            record_key=record_key,
            payload=payload,
            is_test_artifact=is_test,
        )

    def read_records(
        self,
        config: LakehouseConfig,
        batch_id: str,
        ingested_at: str,
    ) -> list[BronzeEnvelope]:
        assert config.logs_dir is not None and config.landing_dir is not None
        envelopes: list[BronzeEnvelope] = []
        log_path = config.logs_dir / "youtube_parser_log.jsonl"
        for _, obj in iter_jsonl_records(log_path):
            envelopes.append(
                self._to_envelope(
                    batch_id=batch_id,
                    ingested_at=ingested_at,
                    origin="jsonl",
                    source_file=log_path.name,
                    raw=obj,
                )
            )
        for rel_file, obj in iter_landing_records(config.landing_dir, self.source_name):
            envelopes.append(
                self._to_envelope(
                    batch_id=batch_id,
                    ingested_at=ingested_at,
                    origin="landing_json",
                    source_file=rel_file,
                    raw=obj,
                )
            )
        return envelopes
