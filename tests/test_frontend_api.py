"""
Tests for Frontend Middleware API routes.
"""

from __future__ import annotations
import io
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from frontend.app import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_serve_index_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Gemini Myanmar" in response.text


def test_get_api_config(client: TestClient) -> None:
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "default_prompt" in data
    assert "default_batch_size" in data
    assert "model_name" in data
    assert "has_api_key" in data


def test_get_api_history(client: TestClient) -> None:
    response = client.get("/api/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_post_api_ocr_mock_mode(client: TestClient) -> None:
    # Create fake image in memory
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"

    files = [
        ("files", ("test_sample.png", io.BytesIO(fake_png), "image/png"))
    ]
    data = {
        "content": "Test OCR Prompt",
        "file_per_batch": "3",
        "mock": "true",
    }

    response = client.post("/api/ocr", files=files, data=data)
    assert response.status_code == 200
    res_json = response.json()

    assert res_json["status"] == "success"
    assert res_json["total_files"] == 1
    assert len(res_json["results"]) == 1
    assert res_json["results"][0]["basename"] == "test_sample.png"
    assert "url" in res_json["results"][0]


def test_post_api_telegram_convert(client: TestClient) -> None:
    sample_html_path = Path(__file__).resolve().parent.parent / "telegram_msg_html" / "messages.html"
    if not sample_html_path.exists():
        pytest.skip("Sample telegram messages.html not found.")

    with open(sample_html_path, "rb") as f:
        files = [
            ("file", ("messages.html", f, "text/html"))
        ]
        data = {
            "include_service": "true"
        }
        response = client.post("/api/telegram/convert", files=files, data=data)

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "success"
    assert res_json["chat_title"] == "Min Thike Tun"
    assert res_json["total_messages"] > 0
    assert "messages" in res_json
    assert "reaction_count" in res_json["messages"][0]
    assert "session_id" in res_json


def test_get_api_telegram_history(client: TestClient) -> None:
    response = client.get("/api/telegram/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "chat_title" in data[0]
        assert "total_messages" in data[0]


def test_post_api_telegram_attach_photos(client: TestClient) -> None:
    # 1. Convert chat to get a session_id
    sample_html_path = Path(__file__).resolve().parent.parent / "telegram_msg_html" / "messages.html"
    if not sample_html_path.exists():
        pytest.skip("Sample telegram messages.html not found.")

    with open(sample_html_path, "rb") as f:
        conv_res = client.post("/api/telegram/convert", files=[("file", ("messages.html", f, "text/html"))])
    assert conv_res.status_code == 200
    session_id = conv_res.json()["session_id"]

    # 2. Attach a mock photo matching a media filename
    fake_jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb"
    photo_filename = "photo_1258@05-11-2026_20-20-34.jpg"
    files = [
        ("photos", (photo_filename, io.BytesIO(fake_jpg), "image/jpeg"))
    ]
    data = {
        "session_id": session_id
    }
    attach_res = client.post("/api/telegram/attach-photos", files=files, data=data)
    assert attach_res.status_code == 200
    res_json = attach_res.json()
    assert res_json["status"] == "success"
    assert res_json["attached_count"] == 1
    assert photo_filename in res_json["url_map"]


def test_post_api_database_convert(client: TestClient) -> None:
    sample_sql_path = Path(__file__).resolve().parent.parent / "sample_database" / "sales_database.sql"
    if not sample_sql_path.exists():
        pytest.skip("Sample SQL database file not found.")

    with open(sample_sql_path, "rb") as f:
        files = [
            ("file", ("sales_database.sql", f, "application/sql"))
        ]
        response = client.post("/api/database/convert", files=files)

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "success"
    assert res_json["format"] == "sql_dump"
    assert res_json["total_tables"] == 2
    assert "sales_table" in res_json["tables"]
    assert "session_id" in res_json


def test_get_api_database_history(client: TestClient) -> None:
    response = client.get("/api/database/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "database_name" in data[0]
        assert "total_tables" in data[0]


def test_post_api_youtube_sample(client: TestClient) -> None:
    response = client.post("/api/youtube/sample")
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "success"
    assert "channel_info" in res_json
    assert res_json["total_videos"] > 0
    assert "session_id" in res_json


def test_post_api_youtube_fetch_file(client: TestClient) -> None:
    sample_html_path = Path(__file__).resolve().parent.parent / "sample_youtube" / "sample_channel.html"
    if not sample_html_path.exists():
        pytest.skip("Sample youtube channel HTML not found.")

    with open(sample_html_path, "rb") as f:
        files = [
            ("file", ("sample_channel.html", f, "text/html"))
        ]
        response = client.post("/api/youtube/fetch", files=files)

    assert response.status_code == 200
    res_json = response.json()
    assert res_json["status"] == "success"
    assert res_json["channel_info"]["channel_name"] == "TechPulse Explains"
    assert res_json["total_videos"] == 3
    assert "session_id" in res_json


def test_get_api_youtube_history(client: TestClient) -> None:
    response = client.get("/api/youtube/history")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)





