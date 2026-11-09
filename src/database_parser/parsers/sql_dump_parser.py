"""
SQL Dump Parser (.sql).
Executes SQL statements in an isolated SQLite memory sandbox and extracts structured tables.
"""

from __future__ import annotations
import re
import sqlite3
from pathlib import Path
from typing import Any

from database_parser.models import ColumnInfo, TableData


def clean_sql_for_sqlite(sql_text: str) -> str:
    """
    Cleans MySQL/PostgreSQL/SQLite dump statements to be compatible with SQLite.
    Strips vendor-specific directives, comments, and options.
    """
    # Remove block comments /* ... */ including MySQL conditional comments /*! ... */
    cleaned = re.sub(r"/\*!?[^*]*\*+(?:[^/*][^*]*\*+)*/", "", sql_text)

    # Remove single line comments starting with -- or #
    cleaned = re.sub(r"--[^\r\n]*", "", cleaned)
    cleaned = re.sub(r"#[^\r\n]*", "", cleaned)

    # Replace backticks with double quotes for identifiers
    cleaned = cleaned.replace("`", '"')

    # Remove MySQL table options at the end of CREATE TABLE (e.g. ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;)
    cleaned = re.sub(
        r"\)\s*(?:ENGINE\s*=\s*\w+)?\s*(?:AUTO_INCREMENT\s*=\s*\d+)?\s*(?:DEFAULT\s+CHARSET\s*=\s*\w+)?\s*(?:COLLATE\s*=\s*[\w_]+)?\s*;",
        ");",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Replace MySQL types with SQLite compatible types
    cleaned = re.sub(r"\bAUTO_INCREMENT\b", "PRIMARY KEY AUTOINCREMENT", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bUNSIGNED\b", "", cleaned, flags=re.IGNORECASE)

    # Remove PostgreSQL specific SET statements, LOCK/UNLOCK TABLES, DROP TABLE IF EXISTS
    lines = []
    for line in cleaned.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        lower = trimmed.lower()
        if (
            lower.startswith("set ")
            or lower.startswith("lock tables")
            or lower.startswith("unlock tables")
            or lower.startswith("pragma ")
        ):
            continue
        lines.append(line)

    return "\n".join(lines)


def parse_sql_dump(sql_content_or_path: str | Path) -> dict[str, TableData]:
    """
    Parses a SQL dump string or file by executing it in an in-memory SQLite sandbox.
    Returns a dictionary of {table_name: TableData}.
    """
    if isinstance(sql_content_or_path, Path) or (
        isinstance(sql_content_or_path, str) and Path(sql_content_or_path).is_file()
    ):
        with open(sql_content_or_path, "r", encoding="utf-8", errors="replace") as f:
            raw_sql = f.read()
    else:
        raw_sql = str(sql_content_or_path)

    cleaned_sql = clean_sql_for_sqlite(raw_sql)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables: dict[str, TableData] = {}
    try:
        # Try executing the whole script first
        try:
            cursor.executescript(cleaned_sql)
        except sqlite3.Error:
            # Fallback: execute statement by statement, skipping any statement with unsupported syntax
            statements = [s.strip() for s in cleaned_sql.split(";") if s.strip()]
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except sqlite3.Error:
                    continue

        # Extract user tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        table_names = [row["name"] for row in cursor.fetchall()]

        for tbl_name in table_names:
            cursor.execute(f"PRAGMA table_info(\"{tbl_name}\")")
            col_rows = cursor.fetchall()
            columns: list[ColumnInfo] = []
            for col in col_rows:
                columns.append(
                    ColumnInfo(
                        name=col["name"],
                        type=col["type"] or "TEXT",
                        primary_key=bool(col["pk"]),
                        nullable=not bool(col["notnull"]),
                    )
                )

            cursor.execute(f"SELECT * FROM \"{tbl_name}\"")
            rows: list[dict[str, Any]] = [dict(r) for r in cursor.fetchall()]

            tables[tbl_name] = TableData(
                table_name=tbl_name,
                row_count=len(rows),
                columns=columns,
                rows=rows,
            )

    finally:
        conn.close()

    return tables

