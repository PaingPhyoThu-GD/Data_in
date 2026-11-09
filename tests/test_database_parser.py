"""
Unit and integration tests for Database to JSON Parser.
"""

from __future__ import annotations
from pathlib import Path
import pytest

from database_parser import DatabaseParser, DatabaseConverter, DatabaseExportResult

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_database"


@pytest.fixture
def parser() -> DatabaseParser:
    return DatabaseParser()


def test_parse_sql_dump(parser: DatabaseParser) -> None:
    sql_path = SAMPLE_DIR / "sales_database.sql"
    if not sql_path.exists():
        pytest.skip("Sample SQL dump not found.")

    result = parser.parse_file(sql_path)
    assert isinstance(result, DatabaseExportResult)
    assert result.status == "success"
    assert result.format == "sql_dump"
    assert result.total_tables == 2
    assert "sales_table" in result.tables
    assert "customers" in result.tables
    assert result.tables["sales_table"].row_count == 5
    assert result.tables["customers"].row_count == 4


def test_parse_sqlite_db(parser: DatabaseParser) -> None:
    db_path = SAMPLE_DIR / "sales.db"
    if not db_path.exists():
        pytest.skip("Sample SQLite DB not found.")

    result = parser.parse_file(db_path)
    assert result.status == "success"
    assert result.format == "sqlite"
    assert result.total_tables == 2
    assert result.total_rows == 9

    # Verify column info
    sales = result.tables["sales_table"]
    col_names = [c.name for c in sales.columns]
    assert "order_id" in col_names
    assert "total_amount" in col_names
    # Check primary key flag
    pk_cols = [c.name for c in sales.columns if c.primary_key]
    assert "order_id" in pk_cols


def test_parse_csv(parser: DatabaseParser) -> None:
    csv_path = SAMPLE_DIR / "sales_table.csv"
    if not csv_path.exists():
        pytest.skip("Sample CSV not found.")

    result = parser.parse_file(csv_path)
    assert result.status == "success"
    assert result.format == "csv"
    assert result.total_tables == 1
    assert "sales_table" in result.tables
    assert result.tables["sales_table"].row_count == 5


def test_parse_excel(parser: DatabaseParser) -> None:
    xlsx_path = SAMPLE_DIR / "sales_table.xlsx"
    if not xlsx_path.exists():
        pytest.skip("Sample Excel file not found.")

    result = parser.parse_file(xlsx_path)
    assert result.status == "success"
    assert result.format == "excel"
    assert result.total_tables == 2
    assert "sales" in result.tables
    assert "customers" in result.tables
    assert result.tables["sales"].row_count == 5
    assert result.tables["customers"].row_count == 4


def test_converter_writes_json(tmp_path: Path) -> None:
    converter = DatabaseConverter()
    sql_path = SAMPLE_DIR / "sales_database.sql"
    out_json = tmp_path / "output_db.json"

    res = converter.convert_file(sql_path, out_json)
    assert out_json.exists()
    assert res.total_tables == 2

