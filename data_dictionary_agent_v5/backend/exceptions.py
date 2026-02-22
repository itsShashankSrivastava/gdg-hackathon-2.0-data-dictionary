"""
Custom typed exception hierarchy.

Upstream code can decide:
  - Retry on transient errors (Timeout, ConnectionLost)
  - Fail fast on permanent errors (InvalidConfig, UnsupportedDB)
"""


class DataDictionaryError(Exception):
    """Base exception for the entire application."""
    pass


# ── Connection & Database ──────────────────────────────────────────────────

class DatabaseConnectionError(DataDictionaryError):
    """Could not establish a database connection."""
    pass


class DatabaseTimeoutError(DataDictionaryError):
    """Database operation timed out – safe to retry."""
    pass


class DatabaseReadOnlyViolation(DataDictionaryError):
    """An attempted write was blocked by read-only mode."""
    pass


class UnsupportedDatabaseError(DataDictionaryError):
    """The requested database type is not supported."""
    pass


# ── Schema Extraction ─────────────────────────────────────────────────────

class SchemaExtractionError(DataDictionaryError):
    """Failed to extract schema metadata from the database."""
    pass


class TableExtractionError(SchemaExtractionError):
    """Failed to extract metadata for a specific table."""

    def __init__(self, table_name: str, detail: str = ""):
        self.table_name = table_name
        super().__init__(f"Table '{table_name}': {detail}")


# ── AI / LLM ──────────────────────────────────────────────────────────────

class AIServiceError(DataDictionaryError):
    """Generic AI/LLM service failure."""
    pass


class AIRateLimitError(AIServiceError):
    """Rate limit hit – back off and retry."""
    pass


class AITimeoutError(AIServiceError):
    """LLM call timed out – safe to retry."""
    pass


# ── API / Auth ─────────────────────────────────────────────────────────────

class AuthenticationError(DataDictionaryError):
    """Invalid or missing API key."""
    pass


class InvalidInputError(DataDictionaryError):
    """Client supplied invalid input – fail fast, do not retry."""
    pass


# ── Export ─────────────────────────────────────────────────────────────────

class ExportError(DataDictionaryError):
    """Documentation export failed."""
    pass
