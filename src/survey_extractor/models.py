"""
Data models and Schema Definitions for Google Forms Survey Data Extraction.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class FieldType(str, Enum):
    TIMESTAMP = "timestamp"
    EMAIL = "email"
    MULTI_SELECT = "multi_select"
    NUMBER = "number"
    BOOLEAN = "boolean"
    TEXT = "text"


class QuestionMapping(BaseModel):
    """
    Metadata mapping an exported CSV column header to a structured question.
    """
    question_id: str
    column_index: int
    question_text: str
    field_type: FieldType
    detected_options: list[str] = Field(default_factory=list)
    sample_values: list[Any] = Field(default_factory=list)


class SurveyResponse(BaseModel):
    """
    Individual response submission parsed from a survey row.
    """
    response_id: str
    survey_id: str
    row_number: int
    submitted_at: Optional[str] = None
    email: Optional[str] = None
    answers: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary mapping question_id to typed answer (string, number, list[str] for multi-select).",
    )


class SurveyMetadata(BaseModel):
    """
    Overview metadata for an imported survey dataset.
    """
    survey_id: str
    title: str
    file_name: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    total_questions: int = 0
    total_responses: int = 0
    valid_responses: int = 0
    invalid_responses: int = 0


class RowParsingError(BaseModel):
    """
    Validation or parsing error detected in a specific row.
    """
    row_number: int
    error_message: str
    raw_row: Optional[list[str]] = None


class SurveyExtractResult(BaseModel):
    """
    Complete in-memory payload returned upon survey CSV extraction.
    """
    status: str = "success"
    survey_id: str
    metadata: SurveyMetadata
    questions: list[QuestionMapping]
    responses: list[SurveyResponse] = Field(
        default_factory=list,
        description="Complete list of all parsed survey responses.",
    )
    sample_responses: list[SurveyResponse] = Field(
        default_factory=list,
        description="First 5 sample responses for fast UI rendering.",
    )
    errors: list[RowParsingError] = Field(default_factory=list)


# Backwards compatibility alias
SurveyImportResult = SurveyExtractResult


# =============================================================================
# Architectural Schema DDL Reference (PostgreSQL)
# For users wishing to pipe the extracted JSON into external databases.
# =============================================================================
POSTGRESQL_JSONB_SCHEMA_DDL = """
-- Architecture: PostgreSQL Hybrid (Relational Meta + GIN-Indexed JSONB)
CREATE TABLE IF NOT EXISTS surveys (
    survey_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_questions INT NOT NULL DEFAULT 0,
    total_responses INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS survey_questions (
    question_id VARCHAR(64) PRIMARY KEY,
    survey_id VARCHAR(64) NOT NULL REFERENCES surveys(survey_id) ON DELETE CASCADE,
    column_index INT NOT NULL,
    question_text TEXT NOT NULL,
    field_type VARCHAR(32) NOT NULL,
    detected_options JSONB DEFAULT '[]'::jsonb,
    CONSTRAINT uq_survey_question_col UNIQUE (survey_id, column_index)
);

CREATE TABLE IF NOT EXISTS survey_responses (
    response_id VARCHAR(64) PRIMARY KEY,
    survey_id VARCHAR(64) NOT NULL REFERENCES surveys(survey_id) ON DELETE CASCADE,
    row_number INT NOT NULL,
    submitted_at TIMESTAMPTZ,
    email VARCHAR(255),
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_survey_response_row UNIQUE (survey_id, row_number)
);

CREATE INDEX IF NOT EXISTS idx_survey_responses_survey_id ON survey_responses(survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_responses_submitted_at ON survey_responses(submitted_at);
CREATE INDEX IF NOT EXISTS idx_survey_responses_answers_gin ON survey_responses USING GIN (answers);
"""

POSTGRESQL_NORMALIZED_SCHEMA_DDL = """
-- Architecture: Fully Normalized Relational EAV
CREATE TABLE IF NOT EXISTS surveys (
    survey_id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS survey_questions (
    question_id VARCHAR(64) PRIMARY KEY,
    survey_id VARCHAR(64) NOT NULL REFERENCES surveys(survey_id) ON DELETE CASCADE,
    column_index INT NOT NULL,
    question_text TEXT NOT NULL,
    field_type VARCHAR(32) NOT NULL
);

CREATE TABLE IF NOT EXISTS survey_responses (
    response_id VARCHAR(64) PRIMARY KEY,
    survey_id VARCHAR(64) NOT NULL REFERENCES surveys(survey_id) ON DELETE CASCADE,
    row_number INT NOT NULL,
    submitted_at TIMESTAMPTZ,
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS survey_answers (
    answer_id BIGSERIAL PRIMARY KEY,
    response_id VARCHAR(64) NOT NULL REFERENCES survey_responses(response_id) ON DELETE CASCADE,
    question_id VARCHAR(64) NOT NULL REFERENCES survey_questions(question_id) ON DELETE CASCADE,
    text_value TEXT,
    number_value NUMERIC,
    array_value TEXT[],
    date_value TIMESTAMPTZ
);
"""
