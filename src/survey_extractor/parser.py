"""
Google Forms CSV Parser Engine.

Features:
- Dynamic Row 1 header extraction.
- Intelligent column data type detection (Timestamp, Email, Multi-Select, Number, Boolean, Text).
- Robust comma-separated multi-select splitting and trimming.
- Pure in-memory extraction into structured JSON (SurveyExtractResult).
- Resilient row validation and error diagnostics.
"""

from __future__ import annotations
import csv
import io
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import (
    FieldType,
    QuestionMapping,
    RowParsingError,
    SurveyExtractResult,
    SurveyMetadata,
    SurveyResponse,
)

# Common Google Forms datetime patterns
DATETIME_PATTERNS = [
    "%Y/%m/%d %I:%M:%S %p %Z",
    "%Y/%m/%d %I:%M:%S %p",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %I:%M:%S %p",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
]

EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-\.]+$")


class GoogleFormsCSVParser:
    """
    Universal extractor for Google Forms CSV exports.
    Extracts structured JSON directly in-memory without persistent database storage.
    """

    def __init__(self, sample_rows_for_inference: int = 50) -> None:
        self.sample_rows_for_inference = sample_rows_for_inference

    def parse_file(
        self,
        file_path: str | Path,
        survey_title: Optional[str] = None,
    ) -> SurveyExtractResult:
        """
        Parse a CSV file on disk directly into a structured SurveyExtractResult.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Survey CSV file not found: {path}")

        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return self.parse_text_stream(
                f,
                file_name=path.name,
                survey_title=survey_title or path.stem,
            )

    def parse_bytes(
        self,
        content_bytes: bytes,
        file_name: str = "survey_export.csv",
        survey_title: Optional[str] = None,
    ) -> SurveyExtractResult:
        """
        Parse CSV content from in-memory bytes (e.g. HTTP file upload).
        """
        text = content_bytes.decode("utf-8-sig", errors="replace")
        stream = io.StringIO(text)
        return self.parse_text_stream(
            stream,
            file_name=file_name,
            survey_title=survey_title or Path(file_name).stem,
        )

    def parse_text_stream(
        self,
        stream: Iterable[str],
        file_name: str,
        survey_title: str,
    ) -> SurveyExtractResult:
        """
        Core streaming parser for an open text stream.
        """
        reader = csv.reader(stream)
        try:
            raw_headers = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty.")

        # Clean headers
        headers = [h.strip() for h in raw_headers]
        if not headers or all(len(h) == 0 for h in headers):
            raise ValueError("CSV header row is invalid or empty.")

        # Buffer initial sample rows for type inference
        sample_rows: list[list[str]] = []
        remaining_rows: list[list[str]] = []

        for row in reader:
            if not row or all(len(cell.strip()) == 0 for cell in row):
                continue
            if len(sample_rows) < self.sample_rows_for_inference:
                sample_rows.append(row)
            else:
                remaining_rows.append(row)

        survey_id = f"srv_{uuid.uuid4().hex[:10]}"

        # Infer questions mapping
        questions = self._infer_questions(headers, sample_rows)

        # Process all rows in memory
        all_responses: list[SurveyResponse] = []
        errors: list[RowParsingError] = []
        row_num = 2  # Row 1 is header, data starts at Row 2

        all_raw_rows = sample_rows + remaining_rows

        for row in all_raw_rows:
            try:
                response = self._parse_row(row, row_num, survey_id, questions, len(headers))
                all_responses.append(response)
            except Exception as exc:
                errors.append(
                    RowParsingError(
                        row_number=row_num,
                        error_message=str(exc),
                        raw_row=row,
                    )
                )
            row_num += 1

        metadata = SurveyMetadata(
            survey_id=survey_id,
            title=survey_title,
            file_name=file_name,
            total_questions=len(questions),
            total_responses=len(all_responses) + len(errors),
            valid_responses=len(all_responses),
            invalid_responses=len(errors),
        )

        return SurveyExtractResult(
            status="success",
            survey_id=survey_id,
            metadata=metadata,
            questions=questions,
            responses=all_responses,
            sample_responses=all_responses[:5],  # First 5 sample responses preview
            errors=errors,
        )

    def _infer_questions(
        self, headers: list[str], sample_rows: list[list[str]]
    ) -> list[QuestionMapping]:
        """
        Dynamically analyze header labels and sample cell data to infer field types.
        """
        questions: list[QuestionMapping] = []

        for idx, header in enumerate(headers):
            question_id = f"q_{idx}"
            col_samples = [
                row[idx].strip()
                for row in sample_rows
                if idx < len(row) and row[idx].strip()
            ]

            field_type = self._detect_field_type(header, col_samples)
            detected_options: list[str] = []

            # If multi-select, gather detected options
            if field_type == FieldType.MULTI_SELECT:
                options_set: set[str] = set()
                for s in col_samples:
                    parts = [p.strip() for p in s.split(",") if p.strip()]
                    options_set.update(parts)
                detected_options = sorted(list(options_set))

            questions.append(
                QuestionMapping(
                    question_id=question_id,
                    column_index=idx,
                    question_text=header if header else f"Column {idx + 1}",
                    field_type=field_type,
                    detected_options=detected_options,
                    sample_values=col_samples[:3],
                )
            )

        return questions

    def _detect_field_type(self, header: str, samples: list[str]) -> FieldType:
        """
        Determine the most appropriate FieldType based on header name and data distribution.
        """
        header_lower = header.lower().strip()

        # 1. Check for Timestamp
        if header_lower in ("timestamp", "submitted at", "submission date"):
            return FieldType.TIMESTAMP

        # 2. Check for Email
        if "email" in header_lower or "e-mail" in header_lower:
            return FieldType.EMAIL

        if not samples:
            return FieldType.TEXT

        # Check if sample looks like timestamp
        if all(self._try_parse_datetime(s) is not None for s in samples[:10]):
            return FieldType.TIMESTAMP

        # Check if sample looks like email
        if all(EMAIL_REGEX.match(s) for s in samples[:10]):
            return FieldType.EMAIL

        # Check if multi-select: contains commas in multiple sample rows
        comma_rows = [s for s in samples if "," in s]
        if len(comma_rows) >= 1 and (
            len(comma_rows) / len(samples) > 0.2 or any("check all" in header_lower or "select all" in header_lower for _ in [1])
        ):
            return FieldType.MULTI_SELECT

        # Check if number
        if all(self._is_number(s) for s in samples):
            return FieldType.NUMBER

        # Check if boolean
        if all(s.lower() in ("true", "false", "yes", "no", "y", "n") for s in samples):
            return FieldType.BOOLEAN

        return FieldType.TEXT

    def _parse_row(
        self,
        row: list[str],
        row_num: int,
        survey_id: str,
        questions: list[QuestionMapping],
        expected_cols: int,
    ) -> SurveyResponse:
        """
        Parse and type-cast a single CSV row into a structured SurveyResponse.
        """
        response_id = f"resp_{uuid.uuid4().hex[:12]}"
        submitted_at: Optional[str] = None
        email: Optional[str] = None
        answers: dict[str, Any] = {}

        for q in questions:
            raw_val = row[q.column_index].strip() if q.column_index < len(row) else ""
            if not raw_val:
                answers[q.question_id] = None
                continue

            parsed_val: Any = raw_val

            if q.field_type == FieldType.TIMESTAMP:
                dt = self._try_parse_datetime(raw_val)
                if dt:
                    parsed_val = dt.isoformat()
                    if submitted_at is None:
                        submitted_at = parsed_val
                else:
                    parsed_val = raw_val

            elif q.field_type == FieldType.EMAIL:
                parsed_val = raw_val.lower()
                if email is None:
                    email = parsed_val

            elif q.field_type == FieldType.MULTI_SELECT:
                # Split comma-separated string cleanly into array
                options = [opt.strip() for opt in raw_val.split(",") if opt.strip()]
                parsed_val = options

            elif q.field_type == FieldType.NUMBER:
                try:
                    if "." in raw_val:
                        parsed_val = float(raw_val)
                    else:
                        parsed_val = int(raw_val)
                except ValueError:
                    parsed_val = raw_val

            elif q.field_type == FieldType.BOOLEAN:
                lower_val = raw_val.lower()
                if lower_val in ("true", "yes", "1", "y"):
                    parsed_val = True
                elif lower_val in ("false", "no", "0", "n"):
                    parsed_val = False
                else:
                    parsed_val = raw_val

            answers[q.question_id] = parsed_val

        return SurveyResponse(
            response_id=response_id,
            survey_id=survey_id,
            row_number=row_num,
            submitted_at=submitted_at,
            email=email,
            answers=answers,
        )

    def _try_parse_datetime(self, value: str) -> Optional[datetime]:
        """Attempt to parse date/time string with common Google Forms patterns."""
        v = value.strip()
        # Clean timezone names like GMT+6:30 or MST if present
        v_clean = re.sub(r"\s+GMT[+-]\d+(:\d+)?", "", v)
        for pattern in DATETIME_PATTERNS:
            try:
                return datetime.strptime(v_clean, pattern)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            pass
        return None

    def _is_number(self, value: str) -> bool:
        """Check if string is a valid integer or float."""
        try:
            float(value)
            return True
        except ValueError:
            return False
