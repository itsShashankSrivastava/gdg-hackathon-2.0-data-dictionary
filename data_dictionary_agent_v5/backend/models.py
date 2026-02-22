"""Pydantic schemas for API request / response validation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Request models ─────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    db_type: str = Field(..., description="Database type (postgresql, mysql, sqlite, …)")
    host: Optional[str] = None
    port: Optional[int] = None
    database: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    account: Optional[str] = None
    warehouse: Optional[str] = None
    schema_name: Optional[str] = Field(None, alias="schema")
    filepath: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str
    question: str
    conversation_history: List[Dict[str, str]] = []


class ExportRequest(BaseModel):
    session_id: str
    format: str = Field("markdown", description="json | markdown | html")


class AnalyzeQualityRequest(BaseModel):
    session_id: str
    table_name: Optional[str] = None  # None = all tables
    schema_name: Optional[str] = None


class GenerateAISummaryRequest(BaseModel):
    session_id: str
    table_name: Optional[str] = None  # None = all tables
    schema_name: Optional[str] = None


class ExtractSchemaRequest(BaseModel):
    session_id: str
    schema_name: Optional[str] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)


# ── Response models ────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    status: str
    message: str


class ConnectResponse(BaseModel):
    status: str
    session_id: str
    database_name: str
    database_type: str
    schemas: List[str]
    table_count: int


class ColumnOut(BaseModel):
    name: str
    data_type: str
    nullable: bool
    default: Optional[str] = None
    primary_key: bool = False
    foreign_key: Optional[Dict[str, str]] = None
    unique: bool = False
    comment: Optional[str] = None
    description: Optional[str] = None


class ConstraintOut(BaseModel):
    name: str
    constraint_type: str
    columns: List[str] = []
    referenced_table: Optional[str] = None
    referenced_columns: Optional[List[str]] = None


class IndexOut(BaseModel):
    name: str
    columns: List[str]
    unique: bool = False


class RelationshipOut(BaseModel):
    type: str
    from_table: str
    from_columns: List[str]
    to_table: str
    to_columns: Optional[List[str]] = None


class TableOut(BaseModel):
    name: str
    schema_name: Optional[str] = Field(None, alias="schema")
    table_type: str = "TABLE"
    columns: List[ColumnOut] = []
    constraints: List[ConstraintOut] = []
    indexes: List[IndexOut] = []
    row_count: int = 0
    comment: Optional[str] = None
    relationships: List[RelationshipOut] = []

    class Config:
        populate_by_name = True


class SchemaResponse(BaseModel):
    database_name: str
    database_type: str
    schemas: List[str]
    tables: List[TableOut]
    total_tables: int
    page: int
    page_size: int
    total_pages: int


class QualityColumnOut(BaseModel):
    column_name: str
    data_type: str
    description: str = ""
    total_count: int = 0
    null_count: int = 0
    distinct_count: int = 0
    completeness: float = 0.0
    uniqueness: float = 0.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    median_value: Optional[float] = None
    std_dev: Optional[float] = None
    earliest_value: Optional[str] = None
    latest_value: Optional[str] = None
    freshness: Optional[str] = None
    most_common_values: List[Dict[str, Any]] = []


class QualityTableOut(BaseModel):
    table_name: str
    schema_name: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    overall_completeness: float = 0.0
    primary_key_health: float = 0.0
    duplicate_row_estimate: float = 0.0
    data_freshness: Optional[str] = None
    latest_timestamp: Optional[str] = None
    freshness_column: Optional[str] = None
    quality_score: float = 0.0
    issues: List[str] = []
    recommendations: List[str] = []
    columns: List[QualityColumnOut] = []


class QualityResponse(BaseModel):
    session_id: str
    tables: Dict[str, QualityTableOut]


class AISummaryResponse(BaseModel):
    session_id: str
    database_summary: Optional[Dict[str, Any]] = None
    table_summaries: Dict[str, Dict[str, Any]] = {}


class ChatResponse(BaseModel):
    answer: str
    intent: Optional[str] = None


class ExportResponse(BaseModel):
    format: str
    content: str
    filename: str
