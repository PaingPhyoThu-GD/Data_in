"""
SQLite Database Parser (.db, .sqlite, .sqlite3).
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any

from database_parser.models import ColumnInfo, TableData


def parse_sqlite_db(db_path: Path | str) -> dict[str, TableData]:
    """
    Parses all user tables from a SQLite database file.
    Returns a dictionary of {table_name: TableData}.
    """
    path_obj = Path(db_path)
    if not path_obj.exists():
        raise FileNotFoundError(f"SQLite file not found: {db_path}")

    conn = sqlite3.connect(str(path_obj))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables: dict[str, TableData] = {}
    try:
        # Get list of user tables (ignoring sqlite internal tables)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        table_names = [row["name"] for row in cursor.fetchall()]

        for tbl_name in table_names:
            # Inspect columns via PRAGMA table_info
            cursor.execute(f"PRAGMA table_info(\"{tbl_name}\")")
            col_rows = cursor.fetchall()
            columns: list[ColumnInfo] = []
            for col in col_rows:
                # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
                columns.append(
                    ColumnInfo(
                        name=col["name"],
                        type=col["type"] or "TEXT",
                        primary_key=bool(col["pk"]),
                        nullable=not bool(col["notnull"]),
                    )
                )

            # Fetch rows
            cursor.execute(f"SELECT * FROM \"{tbl_name}\"")
            rows: list[dict[str, Any]] = []
            for r in cursor.fetchall():
                rows.append(dict(r))

            tables[tbl_name] = TableData(
                table_name=tbl_name,
                row_count=len(rows),
                columns=columns,
                rows=rows,
            )

    finally:
        conn.close()

    return tables

