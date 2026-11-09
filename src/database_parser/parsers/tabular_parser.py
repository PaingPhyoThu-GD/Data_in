"""
Tabular database export parser (.csv, .tsv, .xlsx).
"""

from __future__ import annotations
import csv
import io
from pathlib import Path
from typing import Any

from database_parser.models import ColumnInfo, TableData


def _infer_type(value: Any) -> str:
    """Infers an SQL-like type string from a Python value."""
    if value is None:
        return "TEXT"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    val_str = str(value).strip()
    if val_str.isdigit():
        return "INTEGER"
    try:
        float(val_str)
        return "REAL"
    except ValueError:
        return "TEXT"


def parse_csv_or_tsv(content_or_path: str | bytes | Path, filename: str = "table") -> TableData:
    """
    Parses a CSV or TSV file into a TableData object.
    Auto-detects delimiter and infers column types.
    """
    if isinstance(content_or_path, Path) or (
        isinstance(content_or_path, str) and Path(content_or_path).is_file()
    ):
        with open(content_or_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()
    elif isinstance(content_or_path, bytes):
        raw_text = content_or_path.decode("utf-8", errors="replace")
    else:
        raw_text = str(content_or_path)

    table_name = Path(filename).stem or "table"

    # Detect delimiter
    sample = raw_text[:4096]
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(sample)
        delimiter = dialect.delimiter
    except Exception:
        if "\t" in sample and "," not in sample:
            delimiter = "\t"

    reader = csv.reader(io.StringIO(raw_text), delimiter=delimiter)
    headers = []
    rows = []

    for i, row in enumerate(reader):
        if not row or all(c.strip() == "" for c in row):
            continue
        if not headers:
            headers = [c.strip() or f"col_{j+1}" for j, c in enumerate(row)]
            continue

        record = {}
        for j, col_name in enumerate(headers):
            val = row[j].strip() if j < len(row) else None
            # Attempt numeric conversion
            if val is not None:
                if val.isdigit():
                    record[col_name] = int(val)
                else:
                    try:
                        record[col_name] = float(val)
                    except ValueError:
                        record[col_name] = val
            else:
                record[col_name] = None
        rows.append(record)

    # Infer column types from first non-null values
    columns: list[ColumnInfo] = []
    for col_name in headers:
        inferred = "TEXT"
        for r in rows:
            if r.get(col_name) is not None:
                inferred = _infer_type(r[col_name])
                break
        columns.append(ColumnInfo(name=col_name, type=inferred))

    return TableData(
        table_name=table_name,
        row_count=len(rows),
        columns=columns,
        rows=rows,
    )


def parse_excel_workbook(file_bytes_or_path: bytes | Path | str, filename: str = "database") -> dict[str, TableData]:
    """
    Parses an Excel (.xlsx) file, mapping each sheet to a separate TableData.
    """
    import openpyxl

    if isinstance(file_bytes_or_path, (bytes, bytearray)):
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes_or_path), data_only=True)
    else:
        wb = openpyxl.load_workbook(str(file_bytes_or_path), data_only=True)

    tables: dict[str, TableData] = {}

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        headers: list[str] = []
        rows: list[dict[str, Any]] = []

        for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
            if not row or all(cell is None for cell in row):
                continue
            if not headers:
                headers = [str(cell).strip() if cell is not None else f"col_{j+1}" for j, cell in enumerate(row)]
                continue

            record: dict[str, Any] = {}
            for j, col_name in enumerate(headers):
                val = row[j] if j < len(row) else None
                record[col_name] = val
            rows.append(record)

        columns: list[ColumnInfo] = []
        for col_name in headers:
            inferred = "TEXT"
            for r in rows:
                if r.get(col_name) is not None:
                    inferred = _infer_type(r[col_name])
                    break
            columns.append(ColumnInfo(name=col_name, type=inferred))

        sanitized_table_name = sheet_name.strip().replace(" ", "_").lower()
        tables[sanitized_table_name] = TableData(
            table_name=sanitized_table_name,
            row_count=len(rows),
            columns=columns,
            rows=rows,
        )

    return tables

