"""
Data models for Database to JSON conversion.
"""

from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Metadata describing a database table column."""
    name: str
    type: str = "TEXT"
    primary_key: bool = False
    nullable: bool = True


class TableData(BaseModel):
    """Represents a database table with schema metadata and row records."""
    table_name: str
    row_count: int = 0
    columns: list[ColumnInfo] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class DatabaseExportResult(BaseModel):
    """Complete result representing one or more converted tables from a database export."""
    status: str = "success"
    database_name: str
    export_source: str
    format: str  # "sqlite", "sql_dump", "csv", "excel"
    total_tables: int = 0
    total_rows: int = 0
    tables: dict[str, TableData] = Field(default_factory=dict)

