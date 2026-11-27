"""
Single-contract DuckDB SQL QualityGate and Quarantine splitter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import duckdb

from .models import QualityCheckResult, QualityGateResult, QualityStatus


@dataclass(frozen=True)
class EntityRuleSpec:
    """Declarative SQL validation contract for a single Silver entity."""

    entity: str
    source_name: str
    table_name: str
    conditional: bool
    quarantine_only: bool
    rules: tuple[tuple[str, str, str], ...]  # (_rule_id, sql_predicate, _failure_reason)


ENTITY_RULE_SPECS: tuple[EntityRuleSpec, ...] = (
    EntityRuleSpec(
        entity="ocr_extractions",
        source_name="gemini_ocr",
        table_name="silver_ocr_extractions",
        conditional=False,
        quarantine_only=False,
        rules=(
            ("OCR_ITEM_ERROR", "error_message IS NOT NULL AND trim(error_message) <> ''", "OCR extraction returned an error item"),
            ("OCR_CONFIDENCE_RANGE", "confidence IS NULL OR confidence < 0.0 OR confidence > 1.0", "OCR confidence must be between 0.0 and 1.0"),
        ),
    ),
    EntityRuleSpec(
        entity="telegram_messages",
        source_name="telegram_parser",
        table_name="silver_telegram_messages",
        conditional=False,
        quarantine_only=False,
        rules=(
            ("TG_INVALID_DATE", "message_ts IS NULL", "Telegram message timestamp could not be parsed"),
            ("TG_NEGATIVE_REACTIONS", "reaction_count IS NULL OR reaction_count < 0", "Telegram reaction_count cannot be negative"),
        ),
    ),
    EntityRuleSpec(
        entity="sales_orders",
        source_name="database_parser",
        table_name="silver_sales_orders",
        conditional=True,
        quarantine_only=False,
        rules=(
            ("DB_NULL_ORDER_ID", "order_id IS NULL OR trim(order_id) = ''", "Sales order is missing order_id"),
            ("DB_NON_POSITIVE_AMOUNT", "total_amount IS NULL OR total_amount <= 0", "Sales order total_amount must be > 0"),
        ),
    ),
    EntityRuleSpec(
        entity="youtube_videos",
        source_name="youtube_parser",
        table_name="silver_youtube_videos",
        conditional=False,
        quarantine_only=False,
        rules=(
            ("YT_NEGATIVE_DURATION", "duration_seconds IS NOT NULL AND duration_seconds < 0", "YouTube video duration_seconds cannot be negative"),
            ("YT_NEGATIVE_VIEWS", "view_count IS NOT NULL AND view_count < 0", "YouTube video view_count cannot be negative"),
        ),
    ),
    EntityRuleSpec(
        entity="survey_runs",
        source_name="survey_extractor",
        table_name="silver_survey_runs",
        conditional=False,
        quarantine_only=True,
        rules=(
            ("SURVEY_TRUNCATED_RUN", "captured_responses < valid_responses", "Captured survey responses fewer than metadata.valid_responses"),
        ),
    ),
    EntityRuleSpec(
        entity="telemetry_events",
        source_name="telemetry",
        table_name="silver_telemetry_events",
        conditional=False,
        quarantine_only=False,
        rules=(
            ("TELEMETRY_INVALID_STATUS", "status_code IS NULL OR status_code < 100 OR status_code > 599", "HTTP status_code outside [100, 599]"),
            ("TELEMETRY_NEGATIVE_LATENCY", "latency_ms IS NULL OR latency_ms < 0", "Telemetry latency_ms cannot be negative"),
        ),
    ),
)

# Entities without row-level quarantine predicates still materialize Parquet directly.
PASSTHROUGH_ENTITIES: tuple[tuple[str, str], ...] = (
    ("telegram_service_notices", "silver_telegram_service_notices"),
    ("telegram_reactions", "silver_telegram_reactions"),
    ("database_tables", "silver_database_tables"),
    ("database_rows", "silver_database_rows"),
    ("sales_customers", "silver_sales_customers"),
    ("youtube_channels", "silver_youtube_channels"),
    ("surveys", "silver_surveys"),
    ("survey_questions", "silver_survey_questions"),
    ("survey_responses", "silver_survey_responses"),
    ("survey_answers", "silver_survey_answers"),
)

ENTITY_TO_SOURCE: dict[str, str] = {
    **{spec.entity: spec.source_name for spec in ENTITY_RULE_SPECS},
    "telegram_service_notices": "telegram_parser",
    "telegram_reactions": "telegram_parser",
    "database_tables": "database_parser",
    "database_rows": "database_parser",
    "sales_customers": "database_parser",
    "youtube_channels": "youtube_parser",
    "surveys": "survey_extractor",
    "survey_questions": "survey_extractor",
    "survey_responses": "survey_extractor",
    "survey_answers": "survey_extractor",
}


class QualityGate(Protocol):
    """Port for Silver validation and Quarantine splitting."""

    def evaluate_and_materialize(
        self,
        conn: duckdb.DuckDBPyConnection,
        batch_id: str,
        evaluated_at: str,
        silver_out_dir: Path,
        quarantine_root: Path,
    ) -> tuple[QualityGateResult, dict[str, Path], dict[str, Path], dict[str, int], dict[str, int]]:
        ...


class DuckDBSQLQualityGate:
    """Single-pass DuckDB SQL Quality Gate that splits Quarantine rows and writes validated Silver Parquet."""

    def evaluate_and_materialize(
        self,
        conn: duckdb.DuckDBPyConnection,
        batch_id: str,
        evaluated_at: str,
        silver_out_dir: Path,
        quarantine_root: Path,
    ) -> tuple[QualityGateResult, dict[str, Path], dict[str, Path], dict[str, int], dict[str, int]]:
        silver_out_dir.mkdir(parents=True, exist_ok=True)
        silver_paths: dict[str, Path] = {}
        quarantine_paths: dict[str, Path] = {}
        silver_counts: dict[str, int] = {}
        quarantine_counts: dict[str, int] = {}

        checks: list[QualityCheckResult] = []
        entity_statuses: dict[str, QualityStatus] = {}

        # Materialize passthrough Silver tables
        for ent_name, tbl_name in PASSTHROUGH_ENTITIES:
            out_file = silver_out_dir / f"{tbl_name}.parquet"
            escaped = out_file.as_posix().replace("'", "''")
            conn.execute(f"COPY {tbl_name} TO '{escaped}' (FORMAT PARQUET)")
            cnt = int(conn.execute(f"SELECT COUNT(*) FROM {tbl_name}").fetchone()[0])  # type: ignore[index]
            silver_paths[ent_name] = out_file
            silver_counts[ent_name] = cnt

        # Evaluate rule-bearing entities in one pass
        for spec in ENTITY_RULE_SPECS:
            pre_count = int(conn.execute(f"SELECT COUNT(*) FROM {spec.table_name}").fetchone()[0])  # type: ignore[index]
            case_rule_parts = [f"WHEN ({pred}) THEN '{rid}'" for rid, pred, _ in spec.rules]
            case_reason_parts = [f"WHEN ({pred}) THEN '{reason.replace(chr(39), chr(39)*2)}'" for _, pred, reason in spec.rules]
            any_fail_expr = " OR ".join(f"({pred})" for _, pred, _ in spec.rules)

            classified_tbl = f"_classified_{spec.entity}"
            conn.execute(
                f"""
                CREATE OR REPLACE TEMP TABLE {classified_tbl} AS
                SELECT *,
                    CASE {' '.join(case_rule_parts)} ELSE NULL END AS _q_rule_id,
                    CASE {' '.join(case_reason_parts)} ELSE NULL END AS _q_reason
                FROM {spec.table_name}
                """
            )
            q_count = int(
                conn.execute(f"SELECT COUNT(*) FROM {classified_tbl} WHERE _q_rule_id IS NOT NULL").fetchone()[0]  # type: ignore[index]
            )
            valid_count = pre_count - q_count

            if q_count > 0:
                q_dir = quarantine_root / spec.entity / f"v_{batch_id}"
                q_dir.mkdir(parents=True, exist_ok=True)
                q_file = q_dir / "quarantine.parquet"
                q_escaped = q_file.as_posix().replace("'", "''")
                orig_cols = [r[0] for r in conn.execute(f"DESCRIBE {spec.table_name}").fetchall()]
                struct_args = ", ".join(f'"{c}" := "{c}"' for c in orig_cols)
                conn.execute(
                    f"""
                    COPY (
                        SELECT
                            '{batch_id}' AS _batch_id,
                            _q_rule_id AS _rule_id,
                            _q_reason AS _failure_reason,
                            '{evaluated_at}' AS _quarantined_at,
                            to_json(struct_pack({struct_args})) AS raw_payload_json
                        FROM {classified_tbl}
                        WHERE _q_rule_id IS NOT NULL
                    ) TO '{q_escaped}' (FORMAT PARQUET)
                    """
                )
                quarantine_paths[spec.entity] = q_file
            quarantine_counts[spec.entity] = q_count

            # Write validated Silver Parquet (excluding quarantined rows) for non-quarantine-only entities
            if not spec.quarantine_only:
                clean_tbl = f"valid_{spec.table_name}"
                conn.execute(
                    f"""
                    CREATE OR REPLACE TEMP TABLE {clean_tbl} AS
                    SELECT * EXCLUDE (_q_rule_id, _q_reason)
                    FROM {classified_tbl}
                    WHERE _q_rule_id IS NULL
                    """
                )
                # Replace temp table name in DuckDB session so Gold reads only validated rows
                conn.execute(f"CREATE OR REPLACE TEMP TABLE {spec.table_name} AS SELECT * FROM {clean_tbl}")
                s_file = silver_out_dir / f"{spec.table_name}.parquet"
                s_escaped = s_file.as_posix().replace("'", "''")
                conn.execute(f"COPY {spec.table_name} TO '{s_escaped}' (FORMAT PARQUET)")
                silver_paths[spec.entity] = s_file
                silver_counts[spec.entity] = valid_count

            # Determine entity circuit-breaker status
            if spec.conditional and pre_count == 0:
                status = QualityStatus.PASSED
                msg = "Conditional schema absent; 0 rows passed"
            elif pre_count > 0 and valid_count == 0:
                status = QualityStatus.BLOCKED
                msg = f"All {pre_count} rows failed Quality Gate rules"
            elif q_count > 0:
                status = QualityStatus.PASSED_WITH_QUARANTINE
                msg = f"{q_count} row(s) routed to Quarantine; {valid_count} valid"
            else:
                status = QualityStatus.PASSED
                msg = f"All {valid_count} row(s) passed"

            entity_statuses[spec.entity] = status
            checks.append(
                QualityCheckResult(
                    entity=spec.entity,
                    _rule_id=",".join(r[0] for r in spec.rules),
                    status=status,
                    pre_commit_rows=pre_count,
                    valid_rows=valid_count,
                    quarantined_rows=q_count,
                    message=msg,
                )
            )

        if any(s == QualityStatus.BLOCKED for s in entity_statuses.values()):
            overall = QualityStatus.BLOCKED
        elif any(s == QualityStatus.PASSED_WITH_QUARANTINE for s in entity_statuses.values()):
            overall = QualityStatus.PASSED_WITH_QUARANTINE
        else:
            overall = QualityStatus.PASSED

        gate_result = QualityGateResult(
            overall_status=overall,
            entity_statuses=entity_statuses,
            checks=checks,
            total_quarantined=sum(quarantine_counts.values()),
        )
        return gate_result, silver_paths, quarantine_paths, silver_counts, quarantine_counts
