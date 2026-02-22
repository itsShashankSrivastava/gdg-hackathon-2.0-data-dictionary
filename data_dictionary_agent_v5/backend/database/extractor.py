"""
Schema extractor – scalable for 10 000+ table enterprise databases.

Key design:
  - Batch extraction in configurable chunks
  - Generator-based iteration to keep memory flat
  - Progress callbacks for UI feedback
  - Structured logging for every batch
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, List, Optional

import json

from ..config import TABLE_BATCH_SIZE
from ..exceptions import SchemaExtractionError, TableExtractionError
from ..logger import get_logger
from .connector import DatabaseConnector

logger = get_logger("database.extractor")


# ---------------------------------------------------------------------------
# Metadata dataclasses (simple, serialisable)
# ---------------------------------------------------------------------------

@dataclass
class ColumnMeta:
    name: str
    data_type: str
    nullable: bool
    default: Optional[str] = None
    primary_key: bool = False
    foreign_key: Optional[Dict[str, str]] = None
    unique: bool = False
    comment: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConstraintMeta:
    name: str
    constraint_type: str
    columns: List[str] = field(default_factory=list)
    referenced_table: Optional[str] = None
    referenced_columns: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndexMeta:
    name: str
    columns: List[str] = field(default_factory=list)
    unique: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableMeta:
    name: str
    schema: Optional[str] = None
    table_type: str = "TABLE"
    columns: List[ColumnMeta] = field(default_factory=list)
    constraints: List[ConstraintMeta] = field(default_factory=list)
    indexes: List[IndexMeta] = field(default_factory=list)
    row_count: int = 0
    comment: Optional[str] = None
    relationships: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "schema": self.schema,
            "table_type": self.table_type,
            "columns": [c.to_dict() for c in self.columns],
            "constraints": [c.to_dict() for c in self.constraints],
            "indexes": [i.to_dict() for i in self.indexes],
            "row_count": self.row_count,
            "comment": self.comment,
            "relationships": self.relationships,
        }


@dataclass
class DatabaseMeta:
    database_name: str
    database_type: str
    extraction_timestamp: str
    schemas: List[str] = field(default_factory=list)
    tables: List[TableMeta] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        tables_count = sum(1 for t in self.tables if t.table_type == "TABLE")
        views_count = sum(1 for t in self.tables if t.table_type == "VIEW")
        return {
            "total_tables": tables_count,
            "total_views": views_count,
            "total_columns": sum(len(t.columns) for t in self.tables),
            "total_relationships": sum(len(t.relationships) for t in self.tables),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "database_name": self.database_name,
            "database_type": self.database_type,
            "extraction_timestamp": self.extraction_timestamp,
            "schemas": self.schemas,
            "tables": [t.to_dict() for t in self.tables],
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


# ---------------------------------------------------------------------------
# Column description heuristics (KISS – simple if/else rules)
# ---------------------------------------------------------------------------

def _describe_column(name: str, dtype: str, table: str = "",
                     is_pk: bool = False, is_fk: bool = False,
                     is_unique: bool = False) -> str:
    """Generate a human-readable description from column name / type patterns."""
    low = name.lower()
    tl = dtype.lower() if dtype else ""

    if is_pk:
        return f"Primary key identifier for {table or 'this table'}"
    if is_fk:
        entity = low.replace("_id", "").replace("id", "").strip("_") or "related"
        return f"Foreign key reference to {entity} table"

    # Common patterns
    if low.endswith("_id") or low == "id":
        entity = low.replace("_id", "").replace("_", " ").title() or "Record"
        return f"Identifier for {entity}"
    if "uuid" in low or "guid" in low:
        return "Universally unique identifier (UUID)"

    # Timestamps
    if any(x in tl for x in ("timestamp", "datetime")):
        if any(x in low for x in ("created", "create")):
            return "Timestamp when record was created"
        if any(x in low for x in ("updated", "modified")):
            return "Timestamp when record was last updated"
        if "deleted" in low:
            return "Soft-delete timestamp"
        return "Date/time value"

    # Names
    if low in ("name", "full_name", "fullname"):
        return "Full name"
    if low in ("first_name", "firstname", "fname"):
        return "First/given name"
    if low in ("last_name", "lastname", "lname"):
        return "Last/family name"
    if "email" in low:
        return "Email address"
    if "phone" in low or "mobile" in low:
        return "Phone number"

    # Status / flags
    if low in ("status", "state"):
        return "Current status of the record"
    if low.startswith("is_") or low.startswith("has_"):
        flag = low.replace("is_", "").replace("has_", "").replace("_", " ")
        return f"Flag indicating {flag}"

    # Amounts
    if "price" in low or "amount" in low or "cost" in low:
        return "Monetary value"
    if "quantity" in low or "qty" in low:
        return "Quantity value"
    if "total" in low:
        return "Calculated total"

    # Text
    if low in ("description", "desc", "notes", "note", "comments"):
        return "Free-text description or notes"

    # Code / type
    if low.endswith("_code") or low == "code":
        return "Classification code"
    if low.endswith("_type") or low == "type":
        return "Type classification"

    # Type-based fallback
    if "int" in tl or "serial" in tl:
        return f"{name.replace('_', ' ').title()} (numeric)"
    if "bool" in tl:
        return "Boolean flag"
    if any(x in tl for x in ("varchar", "text", "char")):
        return f"{name.replace('_', ' ').title()} text"

    return name.replace("_", " ").title()


# ---------------------------------------------------------------------------
# System schemas to skip
# ---------------------------------------------------------------------------

SYSTEM_SCHEMAS = frozenset({
    "information_schema", "pg_catalog", "pg_toast", "pg_temp_1",
    "pg_toast_temp_1", "sys", "INFORMATION_SCHEMA", "mysql",
    "performance_schema", "msdb", "master", "tempdb", "model",
})


# ---------------------------------------------------------------------------
# Schema Extractor
# ---------------------------------------------------------------------------

class SchemaExtractor:
    """Extracts metadata from any supported database – batched & scalable."""

    def __init__(self, connector: DatabaseConnector):
        self.db = connector

    # ── public API ────────────────────────────────────────────────────

    def extract_all(
        self,
        schema: Optional[str] = None,
        include_row_counts: bool = True,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
    ) -> DatabaseMeta:
        """Extract full database metadata with batched processing."""
        all_schemas = self.db.get_schemas()
        user_schemas = [s for s in all_schemas if s not in SYSTEM_SCHEMAS]
        schemas_to_scan = [schema] if schema else user_schemas

        meta = DatabaseMeta(
            database_name=self.db.config.database,
            database_type=self.db.config.db_type,
            extraction_timestamp=datetime.now().isoformat(),
            schemas=user_schemas,
        )

        # Collect table names across schemas
        work_items: List[tuple] = []  # (name, schema, type)
        for s in schemas_to_scan:
            try:
                for t in self.db.get_tables(schema=s):
                    work_items.append((t, s, "TABLE"))
            except Exception as exc:
                logger.warning("Skipping schema tables", extra={"context": {"schema": s, "error": str(exc)}})
            try:
                for v in self.db.get_views(schema=s):
                    work_items.append((v, s, "VIEW"))
            except Exception as exc:
                logger.warning("Skipping schema views", extra={"context": {"schema": s, "error": str(exc)}})

        total = len(work_items)
        logger.info("Extraction started", extra={"context": {"total_objects": total}})

        # Process in batches
        for batch_start in range(0, total, TABLE_BATCH_SIZE):
            batch = work_items[batch_start : batch_start + TABLE_BATCH_SIZE]
            for idx, (name, s, obj_type) in enumerate(batch):
                global_idx = batch_start + idx + 1
                if on_progress:
                    on_progress(global_idx, total, name)
                try:
                    tbl = self._extract_table(name, s, include_row_counts and obj_type == "TABLE")
                    tbl.table_type = obj_type
                    meta.tables.append(tbl)
                except Exception as exc:
                    logger.error("Table extraction failed", extra={
                        "context": {"table": name, "schema": s, "error": str(exc)}
                    })

            logger.info("Batch complete", extra={
                "context": {"processed": min(batch_start + TABLE_BATCH_SIZE, total), "total": total}
            })

        self._build_relationships(meta)
        logger.info("Extraction complete", extra={"context": meta.summary})
        return meta

    def extract_tables_page(
        self,
        schema: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        include_row_counts: bool = True,
    ) -> tuple[List[TableMeta], int]:
        """Extract a single page of tables – used by the paginated API."""
        all_schemas = self.db.get_schemas()
        user_schemas = [s for s in all_schemas if s not in SYSTEM_SCHEMAS]
        schemas_to_scan = [schema] if schema else user_schemas

        work_items: List[tuple] = []
        for s in schemas_to_scan:
            try:
                for t in self.db.get_tables(schema=s):
                    work_items.append((t, s, "TABLE"))
            except Exception:
                pass
            try:
                for v in self.db.get_views(schema=s):
                    work_items.append((v, s, "VIEW"))
            except Exception:
                pass

        total = len(work_items)
        start = (page - 1) * page_size
        page_items = work_items[start : start + page_size]

        tables: List[TableMeta] = []
        for name, s, obj_type in page_items:
            try:
                tbl = self._extract_table(name, s, include_row_counts and obj_type == "TABLE")
                tbl.table_type = obj_type
                tables.append(tbl)
            except Exception as exc:
                logger.error("Page extraction failed", extra={
                    "context": {"table": name, "error": str(exc)}
                })

        return tables, total

    # ── internals ─────────────────────────────────────────────────────

    def _extract_table(self, table: str, schema: Optional[str], row_counts: bool) -> TableMeta:
        """Extract metadata for one table."""
        meta = TableMeta(name=table, schema=schema)

        pk_cols = set(self.db.get_primary_keys(table, schema))

        # FK map
        fk_map: Dict[str, Dict[str, str]] = {}
        for fk in self.db.get_foreign_keys(table, schema):
            for c, rc in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                fk_map[c] = {
                    "name": fk.get("name", ""),
                    "referred_table": fk.get("referred_table", ""),
                    "referred_column": rc,
                    "referred_schema": fk.get("referred_schema"),
                }

        unique_cols: set = set()
        for uc in self.db.get_unique_constraints(table, schema):
            unique_cols.update(uc.get("column_names", []))

        for col in self.db.get_columns(table, schema):
            name = col["name"]
            is_pk = name in pk_cols
            is_fk = name in fk_map
            is_uniq = name in unique_cols

            meta.columns.append(ColumnMeta(
                name=name,
                data_type=str(col["type"]),
                nullable=col.get("nullable", True),
                default=str(col["default"]) if col.get("default") else None,
                primary_key=is_pk,
                foreign_key=fk_map.get(name),
                unique=is_uniq,
                comment=col.get("comment"),
                description=_describe_column(name, str(col["type"]), table, is_pk, is_fk, is_uniq),
            ))

        # Constraints
        if pk_cols:
            meta.constraints.append(ConstraintMeta(name="PRIMARY_KEY", constraint_type="PRIMARY KEY", columns=list(pk_cols)))
        for fk in self.db.get_foreign_keys(table, schema):
            meta.constraints.append(ConstraintMeta(
                name=fk.get("name", "FK"),
                constraint_type="FOREIGN KEY",
                columns=fk.get("constrained_columns", []),
                referenced_table=fk.get("referred_table"),
                referenced_columns=fk.get("referred_columns", []),
            ))
        for uc in self.db.get_unique_constraints(table, schema):
            meta.constraints.append(ConstraintMeta(name=uc.get("name", "UNIQUE"), constraint_type="UNIQUE", columns=uc.get("column_names", [])))

        # Indexes
        for idx in self.db.get_indexes(table, schema):
            meta.indexes.append(IndexMeta(name=idx.get("name", "IDX"), columns=idx.get("column_names", []), unique=idx.get("unique", False)))

        # Row count
        if row_counts:
            meta.row_count = self.db.get_table_row_count(table, schema)

        return meta

    def _build_relationships(self, db: DatabaseMeta):
        """Populate bi-directional relationship lists."""
        table_map = {}
        for t in db.tables:
            table_map[t.name] = t
            if t.schema:
                table_map[f"{t.schema}.{t.name}"] = t

        for tbl in db.tables:
            for c in tbl.constraints:
                if c.constraint_type == "FOREIGN KEY" and c.referenced_table:
                    tbl.relationships.append({
                        "type": "references",
                        "from_table": tbl.display_name,
                        "from_columns": c.columns,
                        "to_table": c.referenced_table,
                        "to_columns": c.referenced_columns,
                    })
                    ref = table_map.get(c.referenced_table)
                    if ref:
                        ref.relationships.append({
                            "type": "referenced_by",
                            "from_table": tbl.display_name,
                            "from_columns": c.columns,
                            "to_table": c.referenced_table,
                            "to_columns": c.referenced_columns,
                        })
