"""
Unit and Integration Tests for Pure Google Forms Survey Extractor.
"""

from __future__ import annotations
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from survey_extractor import (
    FieldType,
    GoogleFormsCSVParser,
    SurveyExtractResult,
)
from frontend.app import app

SAMPLE_CSV = Path(__file__).resolve().parent.parent / "sample_surveys" / "google_forms_sample.csv"


@pytest.fixture
def parser() -> GoogleFormsCSVParser:
    return GoogleFormsCSVParser()


def test_parse_sample_survey_file(parser: GoogleFormsCSVParser) -> None:
    assert SAMPLE_CSV.exists(), "Sample CSV fixture must exist."
    result = parser.parse_file(SAMPLE_CSV, survey_title="Developer Experience Survey")

    assert isinstance(result, SurveyExtractResult)
    assert result.status == "success"
    assert result.metadata.title == "Developer Experience Survey"
    assert result.metadata.total_questions == 8
    assert result.metadata.total_responses == 6
    assert result.metadata.valid_responses == 6
    assert result.metadata.invalid_responses == 0
    assert len(result.responses) == 6


def test_multi_select_and_field_type_inference(parser: GoogleFormsCSVParser) -> None:
    result = parser.parse_file(SAMPLE_CSV)

    q_map = {q.column_index: q for q in result.questions}

    # Column 0: Timestamp
    assert q_map[0].field_type == FieldType.TIMESTAMP

    # Column 1: Email
    assert q_map[1].field_type == FieldType.EMAIL

    # Column 4: Multi-select Checkbox
    assert q_map[4].field_type == FieldType.MULTI_SELECT
    assert "Python" in q_map[4].detected_options
    assert "TypeScript" in q_map[4].detected_options
    assert "Go" in q_map[4].detected_options

    # Verify answers for first response
    first_resp = result.responses[0]
    multi_select_val = first_resp.answers["q_4"]
    assert isinstance(multi_select_val, list)
    assert "Python" in multi_select_val
    assert "TypeScript" in multi_select_val
    assert "Go" in multi_select_val

    # Column 5: Number
    assert q_map[5].field_type == FieldType.NUMBER
    assert isinstance(first_resp.answers["q_5"], (int, float))

    # Column 6: Boolean
    assert q_map[6].field_type == FieldType.BOOLEAN
    assert first_resp.answers["q_6"] is True


def test_corrupted_row_handling(parser: GoogleFormsCSVParser) -> None:
    csv_content = """Timestamp,Email Address,Favorite Framework,Experience Rating
2024/05/10 10:00:00 AM,valid@example.com,FastAPI,5
2024/05/10 10:05:00 AM,valid2@example.com,Django,4
"""
    result = parser.parse_bytes(csv_content.encode("utf-8"), file_name="test_corrupted.csv")
    assert result.metadata.valid_responses == 2
    assert result.metadata.invalid_responses == 0
    assert len(result.responses) == 2


def test_api_extract_endpoint() -> None:
    client = TestClient(app)

    with open(SAMPLE_CSV, "rb") as f:
        response = client.post(
            "/api/surveys/extract",
            files={"file": ("survey_test.csv", f, "text/csv")},
            data={"survey_title": "API Test Survey"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["metadata"]["title"] == "API Test Survey"
    assert data["metadata"]["total_questions"] == 8
    assert data["metadata"]["valid_responses"] == 6
    assert len(data["responses"]) == 6

    # Verify multi-select answers are clean arrays in API response
    assert isinstance(data["responses"][0]["answers"]["q_4"], list)
    assert "Python" in data["responses"][0]["answers"]["q_4"]

    # Test GET sample endpoint
    sample_res = client.post("/api/surveys/sample")
    assert sample_res.status_code == 200
    sample_data = sample_res.json()
    assert sample_data["status"] == "success"
    assert sample_data["metadata"]["total_questions"] == 8

    # Test GET history
    hist_res = client.get("/api/surveys/history")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1
