"""
Structured JSON logging with TraceID, Timestamp, Severity, Component, Context.
Single responsibility: provide a configured logger for the entire application.
"""

import logging
import json
import uuid
import sys
from datetime import datetime, timezone
from contextvars import ContextVar

# Context variable for per-request trace IDs
_trace_id: ContextVar[str] = ContextVar("trace_id", default="no-trace")


def set_trace_id(trace_id: str | None = None) -> str:
    """Set (or generate) a trace-id for the current async context."""
    tid = trace_id or uuid.uuid4().hex[:16]
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    return _trace_id.get()


class StructuredJsonFormatter(logging.Formatter):
    """Emit every log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": record.levelname,
            "component": record.name,
            "trace_id": get_trace_id(),
            "message": record.getMessage(),
        }
        # Attach extra context if the caller passed it
        if hasattr(record, "context"):
            log_entry["context"] = record.context
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry, default=str)


def get_logger(component: str) -> logging.Logger:
    """Return a module-level structured logger."""
    logger = logging.getLogger(component)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
