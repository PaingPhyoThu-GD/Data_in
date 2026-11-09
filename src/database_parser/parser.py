"""
Unified Database Parser and Converter.
"""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from database_parser.models import DatabaseExportResult, TableData
from database_parser.parsers.sqlite_parser import parse_sqlite_db
from database_parser.parsers.sql_dump_parser import parse_sql_dump
from database_parser.parsers.tabular_parser import parse_csv_or_tsv, parse_excel_workbook


class DatabaseParser:
    """
    Auto-detects database export format and converts to DatabaseExportResult.
    """

    SUPPORTED_EXTENSIONS = {
        ".sql": "sql_dump",
        ".sqlite": "sqlite",
        ".db": "sqlite",
        ".sqlite3": "sqlite",
        ".csv": "csv",
        ".tsv": "tsv",
        ".xlsx": "excel",
    }

    def parse_file(self, file_path: Path | str, original_filename: Optional[str] = None) -> DatabaseExportResult:
        """
        Parses a database file from disk.
        """
        path_obj = Path(file_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Database file not found: {file_path}")

        filename = original_filename or path_obj.name
        ext = Path(filename).suffix.lower()
        db_name = Path(filename).stem

        # Magic bytes check for SQLite
        with open(path_obj, "rb") as f:
            header = f.read(16)
        if header.startswith(b"SQLite format 3"):
            ext = ".sqlite"

        fmt = self.SUPPORTED_EXTENSIONS.get(ext)
        if not fmt:
            raise ValueError(
                f"Unsupported database export format '{ext}'. "
                f"Supported extensions: {', '.join(sorted(self.SUPPORTED_EXTENSIONS.keys()))}"
            )

        tables: dict[str, TableData] = {}
        if fmt == "sqlite":
            tables = parse_sqlite_db(path_obj)
        elif fmt == "sql_dump":
            tables = parse_sql_dump(path_obj)
        elif fmt in ("csv", "tsv"):
            tbl = parse_csv_or_tsv(path_obj, filename=filename)
            tables = {tbl.table_name: tbl}
        elif fmt == "excel":
            tables = parse_excel_workbook(path_obj, filename=filename)

        total_rows = sum(t.row_count for t in tables.values())
        return DatabaseExportResult(
            status="success",
            database_name=db_name,
            export_source=filename,
            format=fmt,
            total_tables=len(tables),
            total_rows=total_rows,
            tables=tables,
        )

    def parse_bytes(self, content: bytes, filename: str) -> DatabaseExportResult:
        """
        Parses in-memory database bytes by writing to a temporary file when needed.
        """
        ext = Path(filename).suffix.lower()
        if content.startswith(b"SQLite format 3"):
            ext = ".sqlite"

        fmt = self.SUPPORTED_EXTENSIONS.get(ext)
        if not fmt:
            raise ValueError(f"Unsupported database export format: {ext}")

        if fmt == "sql_dump":
            text = content.decode("utf-8", errors="replace")
            tables = parse_sql_dump(text)
            total_rows = sum(t.row_count for t in tables.values())
            return DatabaseExportResult(
                status="success",
                database_name=Path(filename).stem,
                export_source=filename,
                format=fmt,
                total_tables=len(tables),
                total_rows=total_rows,
                tables=tables,
            )

        if fmt in ("csv", "tsv"):
            tbl = parse_csv_or_tsv(content, filename=filename)
            return DatabaseExportResult(
                status="success",
                database_name=Path(filename).stem,
                export_source=filename,
                format=fmt,
                total_tables=1,
                total_rows=tbl.row_count,
                tables={tbl.table_name: tbl},
            )

        if fmt == "excel":
            tables = parse_excel_workbook(content, filename=filename)
            total_rows = sum(t.row_count for t in tables.values())
            return DatabaseExportResult(
                status="success",
                database_name=Path(filename).stem,
                export_source=filename,
                format=fmt,
                total_tables=len(tables),
                total_rows=total_rows,
                tables=tables,
            )

        # For SQLite binary, save to temp file to query via sqlite3
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            return self.parse_file(tmp_path, original_filename=filename)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class DatabaseConverter:
    """
    Convenience wrapper to convert database files to JSON files or strings.
    """

    def __init__(self, parser: Optional[DatabaseParser] = None) -> None:
        self.parser = parser or DatabaseParser()

    def convert_file(
        self,
        input_path: str | Path,
        output_json_path: Optional[str | Path] = None,
        indent: int = 2,
    ) -> DatabaseExportResult:
        result = self.parser.parse_file(input_path)
        if output_json_path:
            out_p = Path(output_json_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, ensure_ascii=False, indent=indent)
        return result

    def convert(
        self,
        input_file_path: str | Path,
        output_json_path: Optional[str | Path] = None,
        indent: int = 2,
    ) -> DatabaseExportResult:
        """Alias for convert_file."""
        return self.convert_file(
            input_path=input_file_path,
            output_json_path=output_json_path,
            indent=indent,
        )
