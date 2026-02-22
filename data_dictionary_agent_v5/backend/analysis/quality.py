"""
Data quality analyser.
Reuses the connector and schema metadata – no repeated logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ..database.connector import DatabaseConnector
from ..database.extractor import TableMeta, ColumnMeta
from ..logger import get_logger

logger = get_logger("analysis.quality")


# ---------------------------------------------------------------------------
# Quality metric dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ColumnQuality:
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
    most_common_values: List[Dict[str, Any]] = field(default_factory=list)
    has_nulls: bool = False
    is_unique: bool = False
    is_potential_key: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TableQuality:
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
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    columns: List[ColumnQuality] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # columns already handled by asdict
        return d


# ---------------------------------------------------------------------------
# Analyser
# ---------------------------------------------------------------------------

class QualityAnalyzer:
    """Analyses data quality for tables. Stateless – pass connector at init."""

    def __init__(self, connector: DatabaseConnector):
        self.db = connector

    def analyze_table(self, table: TableMeta, sample_size: int = 10_000) -> TableQuality:
        metrics = TableQuality(
            table_name=table.name,
            schema_name=table.schema,
            row_count=table.row_count,
            column_count=len(table.columns),
        )

        sample = self.db.get_sample_data(table.name, table.schema, limit=sample_size)
        if sample.empty:
            metrics.issues.append("Could not retrieve sample data")
            return metrics

        pk_cols = [c.name for c in table.columns if c.primary_key]
        completeness_scores: List[float] = []

        for col_meta in table.columns:
            if col_meta.name not in sample.columns:
                continue
            cq = self._analyze_column(sample, col_meta, table.name)
            metrics.columns.append(cq)
            completeness_scores.append(cq.completeness)

        if completeness_scores:
            metrics.overall_completeness = float(np.mean(completeness_scores))

        metrics.primary_key_health = self._pk_health(sample, pk_cols) if pk_cols else 1.0
        metrics.duplicate_row_estimate = self._dup_estimate(sample)
        self._detect_freshness(sample, table, metrics)
        metrics.quality_score = self._score(metrics)
        self._generate_insights(metrics, table)

        logger.info("Table quality analysed", extra={"context": {
            "table": table.display_name, "score": metrics.quality_score
        }})
        return metrics

    def analyze_all(self, tables: List[TableMeta], sample_size: int = 10_000) -> Dict[str, TableQuality]:
        return {
            t.display_name: self.analyze_table(t, sample_size)
            for t in tables if t.table_type == "TABLE"
        }

    # ── column analysis ───────────────────────────────────────────────

    def _analyze_column(self, df: pd.DataFrame, col: ColumnMeta, table_name: str) -> ColumnQuality:
        data = df[col.name]
        cq = ColumnQuality(
            column_name=col.name,
            data_type=col.data_type,
            description=col.description or "",
            total_count=len(data),
        )
        cq.null_count = int(data.isna().sum())
        cq.distinct_count = int(data.nunique())
        cq.completeness = (cq.total_count - cq.null_count) / cq.total_count if cq.total_count else 0
        cq.uniqueness = cq.distinct_count / cq.total_count if cq.total_count else 0
        cq.has_nulls = cq.null_count > 0
        cq.is_unique = cq.distinct_count == cq.total_count - cq.null_count
        cq.is_potential_key = cq.is_unique and not cq.has_nulls

        non_null = data.dropna()
        if len(non_null) == 0:
            return cq

        if self._is_temporal(col, non_null):
            self._temporal_stats(cq, non_null)
        elif pd.api.types.is_numeric_dtype(non_null):
            self._numeric_stats(cq, non_null)

        # top values
        vc = data.value_counts().head(5)
        cq.most_common_values = [
            {"value": str(v), "count": int(c), "pct": round(c / cq.total_count * 100, 2)}
            for v, c in vc.items()
        ]
        return cq

    # ── helpers (DRY: each does exactly one thing) ────────────────────

    @staticmethod
    def _is_temporal(col: ColumnMeta, data: pd.Series) -> bool:
        t = col.data_type.lower()
        if any(x in t for x in ("timestamp", "datetime", "date")):
            return True
        if any(x in col.name.lower() for x in ("created", "updated", "date", "time", "_at")):
            try:
                pd.to_datetime(data.head(10), errors="raise")
                return True
            except Exception:
                pass
        return False

    @staticmethod
    def _temporal_stats(cq: ColumnQuality, data: pd.Series):
        try:
            dt = pd.to_datetime(data, errors="coerce").dropna()
            if dt.empty:
                return
            cq.earliest_value = dt.min().strftime("%Y-%m-%d %H:%M:%S")
            cq.latest_value = dt.max().strftime("%Y-%m-%d %H:%M:%S")
            cq.freshness = QualityAnalyzer._relative_time(dt.max())
        except Exception:
            pass

    @staticmethod
    def _numeric_stats(cq: ColumnQuality, data: pd.Series):
        try:
            n = pd.to_numeric(data, errors="coerce").dropna()
            if n.empty:
                return
            cq.min_value = float(n.min())
            cq.max_value = float(n.max())
            cq.mean_value = float(n.mean())
            cq.median_value = float(n.median())
            cq.std_dev = float(n.std()) if len(n) > 1 else None
        except Exception:
            pass

    @staticmethod
    def _relative_time(ts) -> str:
        try:
            now = datetime.now()
            if hasattr(ts, "tzinfo") and ts.tzinfo:
                ts = ts.replace(tzinfo=None)
            if hasattr(ts, "to_pydatetime"):
                ts = ts.to_pydatetime()
            delta = now - ts
            if delta.total_seconds() < 0:
                return "Future"
            d = delta.days
            if d == 0:
                h = delta.seconds // 3600
                return f"{h} hr ago" if h else f"{delta.seconds // 60} min ago"
            if d < 7:
                return f"{d} day{'s' if d > 1 else ''} ago"
            if d < 30:
                return f"{d // 7} week{'s' if d // 7 > 1 else ''} ago"
            if d < 365:
                return f"{d // 30} month{'s' if d // 30 > 1 else ''} ago"
            return f"{d // 365} year{'s' if d // 365 > 1 else ''} ago"
        except Exception:
            return "Unknown"

    @staticmethod
    def _pk_health(df: pd.DataFrame, pk_cols: List[str]) -> float:
        try:
            if not all(c in df.columns for c in pk_cols):
                return 0.0
            pk = df[pk_cols]
            bad = int(pk.isna().any(axis=1).sum()) + int(pk.duplicated().sum())
            return (len(df) - bad) / len(df) if len(df) else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _dup_estimate(df: pd.DataFrame) -> float:
        try:
            return int(df.duplicated().sum()) / len(df) if len(df) else 0.0
        except Exception:
            return 0.0

    def _detect_freshness(self, df: pd.DataFrame, table: TableMeta, metrics: TableQuality):
        ts_kw = ("created", "updated", "modified", "timestamp", "date", "time", "_at")
        latest = None
        src_col = None
        for col in table.columns:
            t = col.data_type.lower()
            n = col.name.lower()
            if any(x in t for x in ("timestamp", "datetime", "date")) or any(x in n for x in ts_kw):
                if col.name not in df.columns:
                    continue
                try:
                    mx = pd.to_datetime(df[col.name], errors="coerce").max()
                    if pd.notna(mx) and (latest is None or mx > latest):
                        latest = mx
                        src_col = col.name
                except Exception:
                    continue
        if latest and src_col:
            try:
                metrics.latest_timestamp = latest.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                metrics.latest_timestamp = str(latest)
            metrics.freshness_column = src_col
            metrics.data_freshness = self._relative_time(latest)

    @staticmethod
    def _score(m: TableQuality) -> float:
        s = m.overall_completeness * 40
        s += m.primary_key_health * 30
        s += (1.0 - m.duplicate_row_estimate) * 20
        if m.columns:
            s += (sum(1 for c in m.columns if c.is_unique) / len(m.columns)) * 10
        return round(s, 2)

    @staticmethod
    def _generate_insights(m: TableQuality, table: TableMeta):
        for c in m.columns:
            if c.completeness < 0.5:
                m.issues.append(f"Column '{c.column_name}' has very low completeness ({c.completeness:.0%})")
                m.recommendations.append(f"Review data entry for '{c.column_name}'")
            elif c.completeness < 0.9:
                m.issues.append(f"Column '{c.column_name}' has {c.null_count} nulls")
        if m.duplicate_row_estimate > 0.05:
            m.issues.append(f"~{m.duplicate_row_estimate:.0%} duplicate rows detected")
            m.recommendations.append("Deduplicate data")
        if m.quality_score < 50:
            m.issues.append("Overall quality is poor")
        elif m.quality_score < 75:
            m.issues.append("Quality needs improvement")
