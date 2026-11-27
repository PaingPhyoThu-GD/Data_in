"""
Database Storage and Schema Definitions for Google Forms Survey Data.

Provides:
1. Production PostgreSQL Relational + JSONB Schema DDL.
2. Production PostgreSQL Fully-Normalized EAV Schema DDL.
3. Embedded SQLite Storage Engine for local out-of-the-box execution and testing.
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone

from .models import FieldType, QuestionMapping, SurveyMetadata, SurveyResponse


# =============================================================================
# 1. PostgreSQL Schema Design (Production Relational + JSONB)
# =============================================================================
POSTGRESQL_JSONB_SCHEMA_DDL = """
-- ============================================================================
-- Architecture 1: PostgreSQL Hybrid (Relational Meta + GIN-Indexed JSONB)
-- Best for: Ultra-fast writes, evolving survey questions, zero schema migrations
-- when users add or modify Google Forms questions.
-- ============================================================================

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

-- Indexing for high-performance querying
CREATE INDEX IF NOT EXISTS idx_survey_responses_survey_id ON survey_responses(survey_id);
CREATE INDEX IF NOT EXISTS idx_survey_responses_submitted_at ON survey_responses(submitted_at);
CREATE INDEX IF NOT EXISTS idx_survey_responses_answers_gin ON survey_responses USING GIN (answers);
"""

# =============================================================================
# 2. PostgreSQL Schema Design (Fully Normalized EAV)
# =============================================================================
POSTGRESQL_NORMALIZED_SCHEMA_DDL = """
-- ============================================================================
-- Architecture 2: Fully Normalized Relational EAV (Entity-Attribute-Value)
-- Best for: Strict relational reporting, foreign key enforcement on answers
-- ============================================================================

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

CREATE INDEX IF NOT EXISTS idx_answers_response ON survey_answers(response_id);
CREATE INDEX IF NOT EXISTS idx_answers_question ON survey_answers(question_id);
"""


# =============================================================================
# 3. Local SQLite Storage Engine
# =============================================================================
class SurveyStorage:
    """
    SQLite implementation of Survey Storage for self-contained, high-performance
    local database operations with multi-row batch inserts and transaction safety.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        if db_path is None:
            # Default to logs/surveys.db in workspace
            project_root = Path(__file__).resolve().parent.parent.parent
            log_dir = project_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = log_dir / "surveys.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS surveys (
                    survey_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    total_questions INTEGER NOT NULL DEFAULT 0,
                    total_responses INTEGER NOT NULL DEFAULT 0,
                    valid_responses INTEGER NOT NULL DEFAULT 0,
                    invalid_responses INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS survey_questions (
                    question_id TEXT PRIMARY KEY,
                    survey_id TEXT NOT NULL,
                    column_index INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    field_type TEXT NOT NULL,
                    detected_options TEXT,
                    sample_values TEXT,
                    FOREIGN KEY (survey_id) REFERENCES surveys(survey_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS survey_responses (
                    response_id TEXT PRIMARY KEY,
                    survey_id TEXT NOT NULL,
                    row_number INTEGER NOT NULL,
                    submitted_at TEXT,
                    email TEXT,
                    answers_json TEXT NOT NULL,
                    FOREIGN KEY (survey_id) REFERENCES surveys(survey_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_questions_survey ON survey_questions(survey_id);
                CREATE INDEX IF NOT EXISTS idx_responses_survey ON survey_responses(survey_id);
                CREATE INDEX IF NOT EXISTS idx_responses_submitted ON survey_responses(submitted_at);
            """)

    def save_survey(
        self,
        metadata: SurveyMetadata,
        questions: list[QuestionMapping],
        responses: list[SurveyResponse],
    ) -> None:
        """
        Atomically persist a complete survey: metadata, question definitions,
        and response rows using parameterized multi-row batch execution.
        """
        with self._get_connection() as conn:
            # 1. Insert or replace survey metadata
            conn.execute(
                """
                INSERT OR REPLACE INTO surveys 
                (survey_id, title, file_name, created_at, total_questions, total_responses, valid_responses, invalid_responses)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    metadata.survey_id,
                    metadata.title,
                    metadata.file_name,
                    metadata.created_at,
                    metadata.total_questions,
                    metadata.total_responses,
                    metadata.valid_responses,
                    metadata.invalid_responses,
                ),
            )

            # 2. Insert questions
            question_rows = [
                (
                    q.question_id,
                    metadata.survey_id,
                    q.column_index,
                    q.question_text,
                    q.field_type.value if hasattr(q.field_type, "value") else str(q.field_type),
                    json.dumps(q.detected_options, ensure_ascii=False),
                    json.dumps(q.sample_values, ensure_ascii=False),
                )
                for q in questions
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO survey_questions
                (question_id, survey_id, column_index, question_text, field_type, detected_options, sample_values)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                question_rows,
            )

            # 3. Batch insert responses
            response_rows = [
                (
                    r.response_id,
                    r.survey_id,
                    r.row_number,
                    r.submitted_at,
                    r.email,
                    json.dumps(r.answers, ensure_ascii=False),
                )
                for r in responses
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO survey_responses
                (response_id, survey_id, row_number, submitted_at, email, answers_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                response_rows,
            )

    def insert_response_batch(
        self,
        survey_id: str,
        responses: list[SurveyResponse],
    ) -> None:
        """Insert a batch of responses during streaming import."""
        if not responses:
            return
        with self._get_connection() as conn:
            response_rows = [
                (
                    r.response_id,
                    survey_id,
                    r.row_number,
                    r.submitted_at,
                    r.email,
                    json.dumps(r.answers, ensure_ascii=False),
                )
                for r in responses
            ]
            conn.executemany(
                """
                INSERT OR REPLACE INTO survey_responses
                (response_id, survey_id, row_number, submitted_at, email, answers_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                response_rows,
            )

    def get_survey(self, survey_id: str) -> Optional[dict[str, Any]]:
        """Retrieve survey metadata and questions by survey_id."""
        with self._get_connection() as conn:
            survey_cur = conn.execute(
                "SELECT * FROM surveys WHERE survey_id = ?", (survey_id,)
            )
            survey_row = survey_cur.fetchone()
            if not survey_row:
                return None

            questions_cur = conn.execute(
                "SELECT * FROM survey_questions WHERE survey_id = ? ORDER BY column_index ASC",
                (survey_id,),
            )
            questions = []
            for qr in questions_cur.fetchall():
                questions.append({
                    "question_id": qr["question_id"],
                    "column_index": qr["column_index"],
                    "question_text": qr["question_text"],
                    "field_type": qr["field_type"],
                    "detected_options": json.loads(qr["detected_options"] or "[]"),
                    "sample_values": json.loads(qr["sample_values"] or "[]"),
                })

            return {
                "metadata": dict(survey_row),
                "questions": questions,
            }

    def get_responses(
        self, survey_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Fetch paginated responses for a survey."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT response_id, survey_id, row_number, submitted_at, email, answers_json
                FROM survey_responses
                WHERE survey_id = ?
                ORDER BY row_number ASC
                LIMIT ? OFFSET ?
                """,
                (survey_id, limit, offset),
            )
            results = []
            for r in cur.fetchall():
                results.append({
                    "response_id": r["response_id"],
                    "survey_id": r["survey_id"],
                    "row_number": r["row_number"],
                    "submitted_at": r["submitted_at"],
                    "email": r["email"],
                    "answers": json.loads(r["answers_json"] or "{}"),
                })
            return results

    def list_surveys(self, limit: int = 50) -> list[dict[str, Any]]:
        """List all surveys ordered by newest first."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM surveys ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cur.fetchall()]
