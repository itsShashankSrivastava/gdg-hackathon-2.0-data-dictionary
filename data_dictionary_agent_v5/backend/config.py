"""
Configuration module using environment variables.
Follows 12-factor app methodology - all config from environment.
"""

import os
from typing import Optional
from dataclasses import dataclass, field
from urllib.parse import quote_plus


# ---------------------------------------------------------------------------
# Application Settings (read once at import time from env / .env)
# ---------------------------------------------------------------------------

BEDROCK_MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0:48k")
BEDROCK_REGION: str = os.getenv("BEDROCK_REGION", "ap-south-1")

API_KEY: str = os.getenv("DD_API_KEY", "change-me-in-production")
API_KEY_HEADER: str = "X-API-Key"

# Connection pool settings
POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))

# Extraction batch size (for 10 000+ table databases)
TABLE_BATCH_SIZE: int = int(os.getenv("TABLE_BATCH_SIZE", "200"))
SAMPLE_ROW_LIMIT: int = int(os.getenv("SAMPLE_ROW_LIMIT", "10000"))

# Supported database types
SUPPORTED_DATABASES = [
    "postgresql", "mysql", "sqlite",
    "snowflake", "sqlserver", "oracle",
]


# ---------------------------------------------------------------------------
# Database Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class DatabaseConfig:
    """Immutable database connection descriptor."""

    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: str = ""
    username: Optional[str] = None
    password: Optional[str] = None
    # Snowflake
    account: Optional[str] = None
    warehouse: Optional[str] = None
    schema: Optional[str] = None
    # SQLite
    filepath: Optional[str] = None

    def get_connection_string(self) -> str:
        """Build a SQLAlchemy connection URL."""
        user = quote_plus(self.username) if self.username else ""
        pwd = quote_plus(self.password) if self.password else ""

        builders = {
            "postgresql": lambda: f"postgresql://{user}:{pwd}@{self.host}:{self.port or 5432}/{self.database}",
            "mysql": lambda: f"mysql+pymysql://{user}:{pwd}@{self.host}:{self.port or 3306}/{self.database}",
            "sqlite": lambda: f"sqlite:///{self.filepath or self.database}",
            "sqlserver": lambda: (
                f"mssql+pyodbc://{user}:{pwd}@{self.host}:{self.port or 1433}"
                f"/{self.database}?driver=ODBC+Driver+17+for+SQL+Server"
            ),
            "snowflake": lambda: (
                f"snowflake://{user}:{pwd}@{self.account}"
                f"/{self.database}/{self.schema}?warehouse={self.warehouse}"
            ),
            "oracle": lambda: f"oracle+cx_oracle://{user}:{pwd}@{self.host}:{self.port or 1521}/{self.database}",
        }

        builder = builders.get(self.db_type)
        if builder is None:
            raise ValueError(f"Unsupported database type: {self.db_type}")
        return builder()
