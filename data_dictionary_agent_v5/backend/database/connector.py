"""
Database connector with:
  - Connection pooling (SQLAlchemy QueuePool)
  - Read-only enforcement
  - Structured logging
  - Typed exceptions
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool

from ..config import (
    DatabaseConfig,
    MAX_OVERFLOW,
    POOL_RECYCLE,
    POOL_SIZE,
    POOL_TIMEOUT,
)
from ..exceptions import (
    DatabaseConnectionError,
    DatabaseReadOnlyViolation,
    DatabaseTimeoutError,
    UnsupportedDatabaseError,
)
from ..logger import get_logger

logger = get_logger("database.connector")


# ---------------------------------------------------------------------------
# Read-only SQL guard – lightweight, KISS
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = {"INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "REPLACE", "MERGE"}


def _is_write_query(sql: str) -> bool:
    """Return True if *sql* looks like a data-modifying statement."""
    first_token = sql.strip().split()[0].upper() if sql.strip() else ""
    return first_token in _WRITE_KEYWORDS


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class DatabaseConnector:
    """Thread-safe, read-only database connector with connection pooling."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Optional[Engine] = None
        self.inspector = None

    # ── lifecycle ──────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Create a pooled engine and verify connectivity."""
        try:
            conn_str = self.config.get_connection_string()

            # SQLite doesn't support pooling the same way
            if self.config.db_type == "sqlite":
                self.engine = create_engine(conn_str, connect_args={"check_same_thread": False})
            else:
                self.engine = create_engine(
                    conn_str,
                    poolclass=QueuePool,
                    pool_size=POOL_SIZE,
                    max_overflow=MAX_OVERFLOW,
                    pool_timeout=POOL_TIMEOUT,
                    pool_recycle=POOL_RECYCLE,
                    pool_pre_ping=True,  # verify connection health
                )

            # Register read-only guard on every SQL execution
            @event.listens_for(self.engine, "before_cursor_execute")
            def _enforce_read_only(conn, cursor, statement, parameters, context, executemany):
                if _is_write_query(statement):
                    raise DatabaseReadOnlyViolation(
                        f"Write operations are blocked. Statement starts with: {statement[:60]}"
                    )

            # Smoke test
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self.inspector = inspect(self.engine)
            logger.info("Database connected", extra={
                "context": {"db_type": self.config.db_type, "database": self.config.database}
            })
            return True

        except DatabaseReadOnlyViolation:
            raise
        except SQLAlchemyError as exc:
            logger.error("Connection failed", exc_info=exc, extra={
                "context": {"db_type": self.config.db_type}
            })
            raise DatabaseConnectionError(f"Failed to connect: {exc}") from exc

    def disconnect(self):
        """Dispose the engine and return all pooled connections."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.inspector = None
            logger.info("Database disconnected")

    # ── introspection helpers (read-only) ─────────────────────────────

    def _require_inspector(self):
        if not self.inspector:
            raise DatabaseConnectionError("Not connected to any database")

    def get_schemas(self) -> List[str]:
        self._require_inspector()
        try:
            return self.inspector.get_schema_names()
        except Exception:
            return ["default"]

    def get_tables(self, schema: Optional[str] = None) -> List[str]:
        self._require_inspector()
        return self.inspector.get_table_names(schema=schema)

    def get_views(self, schema: Optional[str] = None) -> List[str]:
        self._require_inspector()
        try:
            return self.inspector.get_view_names(schema=schema)
        except Exception:
            return []

    def get_columns(self, table: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_inspector()
        return self.inspector.get_columns(table, schema=schema)

    def get_primary_keys(self, table: str, schema: Optional[str] = None) -> List[str]:
        self._require_inspector()
        pk = self.inspector.get_pk_constraint(table, schema=schema)
        return pk.get("constrained_columns", []) if pk else []

    def get_foreign_keys(self, table: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_inspector()
        return self.inspector.get_foreign_keys(table, schema=schema)

    def get_indexes(self, table: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_inspector()
        return self.inspector.get_indexes(table, schema=schema)

    def get_unique_constraints(self, table: str, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        self._require_inspector()
        try:
            return self.inspector.get_unique_constraints(table, schema=schema)
        except Exception:
            return []

    # ── query helpers (all SELECT-only thanks to the guard) ───────────

    def execute_query(self, query: str) -> pd.DataFrame:
        if not self.engine:
            raise DatabaseConnectionError("Not connected to any database")
        try:
            return pd.read_sql(text(query), self.engine)
        except DatabaseReadOnlyViolation:
            raise
        except Exception as exc:
            logger.error("Query execution failed", exc_info=exc, extra={"context": {"query": query[:200]}})
            raise

    def get_table_row_count(self, table: str, schema: Optional[str] = None) -> int:
        fqn = f"{schema}.{table}" if schema else table
        try:
            df = self.execute_query(f"SELECT COUNT(*) AS cnt FROM {fqn}")
            return int(df["cnt"].iloc[0])
        except Exception:
            return -1

    def get_sample_data(self, table: str, schema: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        fqn = f"{schema}.{table}" if schema else table
        try:
            return self.execute_query(f"SELECT * FROM {fqn} LIMIT {limit}")
        except Exception:
            try:
                return self.execute_query(f"SELECT TOP {limit} * FROM {fqn}")
            except Exception:
                return pd.DataFrame()

    def get_column_stats(self, table: str, column: str, schema: Optional[str] = None) -> Dict[str, Any]:
        fqn = f"{schema}.{table}" if schema else table
        stats: Dict[str, Any] = {}
        try:
            q = (
                f"SELECT COUNT(*) AS total, "
                f"SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS nulls, "
                f"COUNT(DISTINCT {column}) AS distincts "
                f"FROM {fqn}"
            )
            df = self.execute_query(q)
            total = int(df["total"].iloc[0])
            nulls = int(df["nulls"].iloc[0])
            stats["total_count"] = total
            stats["null_count"] = nulls
            stats["distinct_count"] = int(df["distincts"].iloc[0])
            stats["completeness"] = (total - nulls) / total if total else 0
        except Exception as exc:
            stats["error"] = str(exc)
        return stats

    # ── context manager ───────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.disconnect()
