"""
Unit and Integration Tests for Telemetry & Traffic Intelligence Engine.
"""

from __future__ import annotations
import hmac
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from telemetry import (
    BeaconPing,
    FileLogIngestor,
    LogDrainIngestor,
    TelemetryConverter,
    TelemetryEvent,
    TelemetryService,
    TelemetryStorage,
    extract_referrer_domain,
    generate_visitor_hash,
    parse_user_agent,
    truncate_ip,
)
from frontend.app import app

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_telemetry"
SAMPLE_NDJSON = SAMPLE_DIR / "vercel_logs_sample.ndjson"
SAMPLE_CSV = SAMPLE_DIR / "vercel_traffic_sample.csv"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_truncate_ip_and_salted_hmac() -> None:
    # IPv4 /24 truncation
    assert truncate_ip("192.168.1.144") == "192.168.1.0"
    assert truncate_ip("10.0.8.25") == "10.0.8.0"

    # IPv6 /48 truncation
    assert truncate_ip("2001:db8:85a3:8d3:1319:8a2e:370:7348") == "2001:db8:85a3::/48"

    # Daily salted hash consistency
    hash_today = generate_visitor_hash("192.168.1.144", "Mozilla/5.0", site_id="site_a", date_str="2026-11-10")
    hash_today_same_ip_diff_host = generate_visitor_hash("192.168.1.99", "Mozilla/5.0", site_id="site_a", date_str="2026-11-10")
    # Same masked /24 subnet & UA gives same hash
    assert hash_today == hash_today_same_ip_diff_host

    # Different date produces different hash (no cross-day tracking)
    hash_tomorrow = generate_visitor_hash("192.168.1.144", "Mozilla/5.0", site_id="site_a", date_str="2026-11-11")
    assert hash_today != hash_tomorrow


def test_user_agent_and_referrer_sanitizer() -> None:
    # UA parsing
    b, os, dev = parse_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36")
    assert b == "Chrome"
    assert os == "Windows"
    assert dev == "desktop"

    b_mob, os_mob, dev_mob = parse_user_agent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5) Safari/604.1")
    assert b_mob == "Safari"
    assert os_mob == "iOS"
    assert dev_mob == "mobile"

    # Referrer domain extraction
    assert extract_referrer_domain("https://www.google.com/search?q=ocr") == "google.com"
    assert extract_referrer_domain("https://github.com/org/repo") == "github.com"
    assert extract_referrer_domain("direct") == "direct"
    assert extract_referrer_domain("") == "direct"


def test_sqlite_storage_wal_and_quantiles() -> None:
    storage = TelemetryStorage(db_path=":memory:")

    events = [
        TelemetryEvent(
            id=f"e_{i}",
            site_id="test_site",
            source_mode="unit_test",
            timestamp=1700000000000 + (i * 1000),
            datetime_utc="2026-11-10T10:00:00Z",
            visitor_hash=f"v_{i % 5}",
            session_id=f"s_{i % 3}",
            path="/api/ocr" if i % 2 == 0 else "/dashboard",
            status_code=200 if i < 18 else 500,
            latency_ms=10.0 + (i * 10.0),
            duration_seconds=5.0,
            country_code="US",
            browser="Chrome",
            os="Windows",
        )
        for i in range(20)
    ]

    inserted = storage.insert_events(events)
    assert inserted == 20

    stats = storage.get_dashboard_stats(site_id="test_site")
    assert stats.total_records == 20
    assert stats.kpis.total_pageviews == 20
    assert stats.kpis.unique_visitors == 5
    assert stats.kpis.total_sessions == 3
    assert stats.kpis.p50_latency_ms > 0
    assert stats.kpis.p95_latency_ms > stats.kpis.p50_latency_ms
    assert len(stats.routes) == 2


def test_ndjson_and_csv_file_adapters() -> None:
    assert SAMPLE_NDJSON.exists(), "Sample NDJSON must exist"
    assert SAMPLE_CSV.exists(), "Sample CSV must exist"

    ingestor = FileLogIngestor()

    # NDJSON
    ndjson_events = ingestor.ingest(SAMPLE_NDJSON, site_id="ndjson_test")
    assert len(ndjson_events) >= 100
    assert all(isinstance(e, TelemetryEvent) for e in ndjson_events)
    assert any(e.status_code == 200 for e in ndjson_events)

    # CSV
    csv_events = ingestor.ingest(SAMPLE_CSV, site_id="csv_test")
    assert len(csv_events) >= 100
    assert all(isinstance(e, TelemetryEvent) for e in csv_events)


def test_log_drain_hmac_verification() -> None:
    secret = "super_secret_webhook_key_123"
    drain_ingestor = LogDrainIngestor(secret=secret)

    payload_body = b'{"id":"log_1","source":"edge","proxy":{"statusCode":200,"path":"/test"}}'
    valid_sig = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()

    assert drain_ingestor.verify_signature(payload_body, valid_sig) is True
    assert drain_ingestor.verify_signature(payload_body, "invalid_sig") is False


def test_telemetry_converter_cli_runner(tmp_path: Path) -> None:
    out_file = tmp_path / "telemetry_out.json"
    converter = TelemetryConverter(db_path=":memory:")
    payload = converter.convert_file(SAMPLE_NDJSON, output_file=out_file)

    assert out_file.exists()
    assert payload.total_records > 0
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["status"] == "success"
    assert "kpis" in data


def test_fastapi_telemetry_endpoints(client: TestClient) -> None:
    # 1. Sample loader
    resp_sample = client.post("/api/telemetry/sample")
    assert resp_sample.status_code == 200
    sample_data = resp_sample.json()
    assert sample_data["status"] == "success"
    assert sample_data["total_records"] >= 100
    assert sample_data["kpis"]["total_pageviews"] >= 100

    # 2. File import endpoint with sample CSV
    with open(SAMPLE_CSV, "rb") as f:
        resp_upload = client.post(
            "/api/telemetry/import",
            files={"file": ("traffic_test.csv", f, "text/csv")},
            data={"site_id": "upload_test"},
        )
    assert resp_upload.status_code == 200
    upload_data = resp_upload.json()
    assert upload_data["status"] == "success"
    assert upload_data["site_id"] == "upload_test"

    # 3. Beacon collection ping
    ping_payload = {"site_id": "test_site", "p": "/blog/post-1", "r": "https://google.com", "d": 12.5}
    resp_beacon = client.post(
        "/api/telemetry/collect",
        json=ping_payload,
        headers={"User-Agent": "Mozilla/5.0 Chrome/128.0", "X-Forwarded-For": "198.51.100.22"},
    )
    assert resp_beacon.status_code == 200
    assert resp_beacon.json()["status"] == "ok"

    # 4. Stats query
    resp_stats = client.get("/api/telemetry/stats")
    assert resp_stats.status_code == 200
    stats_data = resp_stats.json()
    assert "kpis" in stats_data
    assert "routes" in stats_data

    # 5. History query
    resp_hist = client.get("/api/telemetry/history")
    assert resp_hist.status_code == 200
    assert isinstance(resp_hist.json(), list)

    # 6. Log drain handshake verification
    resp_drain_ping = client.post(
        "/api/telemetry/drain",
        headers={"x-vercel-verify": "verify_token_abc123"},
    )
    assert resp_drain_ping.status_code == 200
    assert resp_drain_ping.headers.get("x-vercel-verify") == "verify_token_abc123"
