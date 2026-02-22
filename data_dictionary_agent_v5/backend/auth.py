"""
Simple API-key authentication dependency for FastAPI.
"""

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from .config import API_KEY, API_KEY_HEADER
from .exceptions import AuthenticationError
from .logger import get_logger

logger = get_logger("auth")

_api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


async def require_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """FastAPI dependency – reject requests without a valid key."""
    if not api_key or api_key != API_KEY:
        logger.warning("Authentication failed", extra={"context": {"provided_key_prefix": (api_key or "")[:4]}})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return api_key
