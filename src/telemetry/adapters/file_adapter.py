"""
File Ingestion Adapter (Pathway B) for NDJSON, CSV, and JSON access/traffic logs.
Supports Vercel CLI logs, Cloudflare logs, Nginx/Caddy access logs, and generic CSVs.
"""

from __future__ import annotations
import csv
import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Union

from ..models import TelemetryEvent
from ..sanitizer import (
    extract_referrer_domain,
    generate_visitor_hash,
    parse_user_agent,
    truncate_ip,
)
from .base import BaseIngestor


class FileLogIngestor(BaseIngestor):
    """
    Ingests log files (NDJSON, CSV, JSON) offline line-by-line.
    Extracts, normalizes, and sanitizes all events into unified TelemetryEvents.
    """

    def ingest(
        self,
        raw_data: Union[str, bytes, Path],
        site_id: str = "default",
    ) -> list[TelemetryEvent]:
        """
        Main entry point for file ingestion.
        Accepts file path, raw text string, or byte content.
        """
        if isinstance(raw_data, Path) or (isinstance(raw_data, str) and len(raw_data) < 1024 and Path(raw_data).exists()):
            with open(raw_data, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        elif isinstance(raw_data, bytes):
            content = raw_data.decode("utf-8-sig", errors="replace")
        else:
            content = str(raw_data)

        content = content.strip()
        if not content:
            return []

        # 1. Try parsing as JSON array
        if content.startswith("[") and content.endswith("]"):
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    return self._parse_json_list(data, site_id)
            except json.JSONDecodeError:
                pass

        # 2. Check if content is NDJSON (starts with '{' on line 1)
        first_line = content.splitlines()[0].strip()
        if first_line.startswith("{") and first_line.endswith("}"):
            return self._parse_ndjson(content, site_id)

        # 3. Default to CSV
        return self._parse_csv(content, site_id)

    def _parse_ndjson(self, content: str, site_id: str) -> list[TelemetryEvent]:
        """Parse line-delimited JSON (Vercel CLI / Drain format)."""
        events: list[TelemetryEvent] = []

        for line_num, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                event = self._normalize_record(record, site_id, source_mode="ndjson_file")
                if event:
                    events.append(event)
            except Exception:
                continue

        return events

    def _parse_json_list(self, data: list[dict[str, Any]], site_id: str) -> list[TelemetryEvent]:
        """Parse array of JSON objects."""
        events: list[TelemetryEvent] = []
        for record in data:
            if isinstance(record, dict):
                event = self._normalize_record(record, site_id, source_mode="json_array")
                if event:
                    events.append(event)
        return events

    def _parse_csv(self, content: str, site_id: str) -> list[TelemetryEvent]:
        """Parse CSV access/traffic logs with dynamic column mapping."""
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            return []

        # Find column mappings
        col_map = self._infer_csv_columns(reader.fieldnames)
        events: list[TelemetryEvent] = []

        for row in reader:
            try:
                path = row.get(col_map.get("path", ""), "/").strip() or "/"
                status_raw = row.get(col_map.get("status", ""), "200")
                try:
                    status_code = int(float(status_raw))
                except Exception:
                    status_code = 200

                latency_raw = row.get(col_map.get("latency", ""), "0")
                try:
                    latency_ms = float(latency_raw)
                except Exception:
                    latency_ms = 0.0

                ip = row.get(col_map.get("ip", ""), "127.0.0.1")
                ua = row.get(col_map.get("user_agent", ""), "Mozilla/5.0")
                referrer = row.get(col_map.get("referrer", ""), "")
                country = row.get(col_map.get("country", ""), "UNKNOWN").upper()
                duration = float(row.get(col_map.get("duration", ""), "0.0") or 0.0)

                ts_raw = row.get(col_map.get("timestamp", ""), "")
                ts_ms = self._parse_timestamp_ms(ts_raw)

                date_str = datetime.utcfromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d")
                visitor_hash = generate_visitor_hash(ip, ua, site_id=site_id, date_str=date_str)
                browser, os_name, dev_type = parse_user_agent(ua)

                session_id = f"s_{visitor_hash}_{ts_ms // (30 * 60 * 1000)}"

                events.append(
                    TelemetryEvent(
                        id=str(uuid.uuid4()),
                        site_id=site_id,
                        source_mode="csv_file",
                        timestamp=ts_ms,
                        datetime_utc=datetime.utcfromtimestamp(ts_ms / 1000.0).isoformat() + "Z",
                        visitor_hash=visitor_hash,
                        session_id=session_id,
                        path=path,
                        method=row.get(col_map.get("method", ""), "GET").upper() or "GET",
                        status_code=status_code,
                        latency_ms=latency_ms,
                        duration_seconds=duration,
                        referrer=referrer,
                        referrer_domain=extract_referrer_domain(referrer),
                        country_code=country if len(country) <= 3 else country[:2],
                        browser=browser,
                        os=os_name,
                        device_type=dev_type,
                    )
                )
            except Exception:
                continue

        return events

    def _normalize_record(
        self,
        record: dict[str, Any],
        site_id: str,
        source_mode: str,
    ) -> TelemetryEvent | None:
        """
        Normalize standard Vercel JSON log record or generic object.
        """
        # Look for nested proxy object (Vercel Log Drain / CLI structure)
        proxy = record.get("proxy", {})
        if not isinstance(proxy, dict):
            proxy = {}

        path = proxy.get("path") or record.get("path") or record.get("requestPath") or "/"
        method = proxy.get("method") or record.get("method") or "GET"
        status_code = proxy.get("statusCode") or record.get("statusCode") or record.get("status") or 200
        try:
            status_code = int(status_code)
        except Exception:
            status_code = 200

        latency_ms = (
            proxy.get("executionTime")
            or proxy.get("duration")
            or record.get("executionTime")
            or record.get("latency")
            or record.get("latency_ms")
            or 0.0
        )
        try:
            latency_ms = float(latency_ms)
        except Exception:
            latency_ms = 0.0

        # User Agent (in Vercel, proxy.userAgent is often an array or string)
        ua_raw = proxy.get("userAgent") or record.get("userAgent") or record.get("user_agent") or ""
        if isinstance(ua_raw, list):
            ua_str = ua_raw[0] if ua_raw else ""
        else:
            ua_str = str(ua_raw)

        # Client IP
        ip = proxy.get("clientIp") or record.get("clientIp") or record.get("ip") or "127.0.0.1"

        # Referrer
        referrer = (
            proxy.get("referer")
            or proxy.get("referrer")
            or record.get("referer")
            or record.get("referrer")
            or record.get("referrerHostname")
            or ""
        )

        country = (
            proxy.get("country")
            or proxy.get("region")
            or record.get("country")
            or record.get("country_code")
            or "UNKNOWN"
        )
        if isinstance(country, str):
            country = country.upper()
            if len(country) > 2 and not country.startswith("SFO") and not country.startswith("IAD"):
                country = country[:2]

        ts_raw = record.get("timestamp") or record.get("time") or record.get("date")
        ts_ms = self._parse_timestamp_ms(ts_raw)

        duration = float(record.get("duration_seconds") or proxy.get("duration_seconds") or 0.0)

        date_str = datetime.utcfromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d")
        visitor_hash = generate_visitor_hash(ip, ua_str, site_id=site_id, date_str=date_str)
        browser, os_name, dev_type = parse_user_agent(ua_str)
        session_id = f"s_{visitor_hash}_{ts_ms // (30 * 60 * 1000)}"

        return TelemetryEvent(
            id=str(record.get("id") or uuid.uuid4()),
            site_id=site_id,
            source_mode=source_mode,
            timestamp=ts_ms,
            datetime_utc=datetime.utcfromtimestamp(ts_ms / 1000.0).isoformat() + "Z",
            visitor_hash=visitor_hash,
            session_id=session_id,
            path=str(path),
            method=str(method).upper(),
            status_code=status_code,
            latency_ms=latency_ms,
            duration_seconds=duration,
            referrer=str(referrer),
            referrer_domain=extract_referrer_domain(str(referrer)),
            country_code=str(country),
            browser=browser,
            os=os_name,
            device_type=dev_type,
        )

    def _infer_csv_columns(self, fieldnames: list[str]) -> dict[str, str]:
        """Find corresponding column names from header row."""
        mapping: dict[str, str] = {}
        for fn in fieldnames:
            fn_low = fn.strip().lower()
            if any(k in fn_low for k in ("path", "url", "route", "uri", "endpoint")):
                mapping["path"] = fn
            elif any(k in fn_low for k in ("status", "status_code", "code")):
                mapping["status"] = fn
            elif any(k in fn_low for k in ("latency", "duration_ms", "time_taken", "response_time")):
                mapping["latency"] = fn
            elif any(k in fn_low for k in ("ip", "client_ip", "remote_addr")):
                mapping["ip"] = fn
            elif any(k in fn_low for k in ("user_agent", "useragent", "ua")):
                mapping["user_agent"] = fn
            elif any(k in fn_low for k in ("referrer", "referer")):
                mapping["referrer"] = fn
            elif any(k in fn_low for k in ("country", "geo")):
                mapping["country"] = fn
            elif any(k in fn_low for k in ("time", "date", "timestamp", "ts")):
                mapping["timestamp"] = fn
            elif fn_low in ("method", "http_method"):
                mapping["method"] = fn
            elif any(k in fn_low for k in ("dwell", "duration_sec", "visit_duration")):
                mapping["duration"] = fn
        return mapping

    def _parse_timestamp_ms(self, val: Any) -> int:
        """Parse ISO string, unix timestamp seconds or milliseconds."""
        if not val:
            return int(datetime.utcnow().timestamp() * 1000)

        # Numeric check
        if isinstance(val, (int, float)):
            if val < 10_000_000_000:  # Seconds
                return int(val * 1000)
            return int(val)

        val_str = str(val).strip()
        try:
            f = float(val_str)
            if f < 10_000_000_000:
                return int(f * 1000)
            return int(f)
        except ValueError:
            pass

        # Try ISO format
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%b/%Y:%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(val_str[:26], fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

        return int(datetime.utcnow().timestamp() * 1000)
