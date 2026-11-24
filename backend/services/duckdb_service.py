"""
Phase 6 — Safe SQL Engine (DuckDB Service)
Provides a read-only SQL execution engine backed by DuckDB.
Blocks all DDL and DML mutations; only SELECT queries are allowed.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

# ── Blocked SQL keywords (case-insensitive) ────────────────────────────────────
BLOCKED_KEYWORDS = frozenset([
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "MERGE", "EXEC", "EXECUTE",
    "PRAGMA", "ATTACH", "DETACH", "COPY", "EXPORT",
])

# Pattern to strip comments before keyword scanning
SQL_COMMENT_PATTERN = re.compile(r"(--[^\n]*|/\*.*?\*/)", re.DOTALL | re.IGNORECASE)


class SQLSafetyError(Exception):
    """Raised when a blocked SQL operation is attempted."""
    pass


class DuckDBService:
    """
    Read-only DuckDB query service with SQL safety filtering.
    Opens the database in read-only mode to prevent accidental writes.
    """

    def __init__(self):
        self._con: duckdb.DuckDBPyConnection | None = None
        self._ready = False

    def _connect(self) -> None:
        """Open a read-only DuckDB connection."""
        if self._ready:
            return

        from config import settings
        db_path = settings.duckdb_path

        if not db_path.exists():
            raise RuntimeError(
                f"DuckDB file not found: {db_path}. "
                "Please run build_duckdb.py first."
            )

        logger.info(f"Connecting to DuckDB (read-only): {db_path}")
        # read_only=True prevents any writes
        self._con = duckdb.connect(str(db_path), read_only=True)
        self._ready = True
        logger.info("DuckDB connection established")

    def is_ready(self) -> bool:
        return self._ready

    @staticmethod
    def _validate_sql(sql: str) -> None:
        """
        Check SQL for blocked keywords.
        Raises SQLSafetyError if any blocked operation is detected.
        """
        # Strip SQL comments first
        clean_sql = SQL_COMMENT_PATTERN.sub(" ", sql)

        # Tokenise by word boundaries
        tokens = re.findall(r"\b[A-Z]+\b", clean_sql.upper())
        for token in tokens:
            if token in BLOCKED_KEYWORDS:
                raise SQLSafetyError(
                    f"SQL operation '{token}' is not permitted. "
                    "Only SELECT queries are allowed."
                )

        # Ensure query starts with SELECT (after stripping whitespace/comments)
        stripped = clean_sql.strip().upper()
        if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
            raise SQLSafetyError(
                "Only SELECT (or WITH ... SELECT) queries are permitted."
            )

    def execute_query(
        self,
        sql: str,
        limit: int = 1000,
        params: list[Any] | tuple[Any, ...] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a safe SELECT query and return results as a dict.

        Args:
            sql:    SQL SELECT statement.
            limit:  Override row limit (max 5000).
            params: Optional parameter list for parameterized SQL queries.

        Returns:
            Dict with keys: columns, data, row_count, execution_time_ms, sql

        Raises:
            SQLSafetyError:  If query contains blocked operations.
            Exception:       On DuckDB execution errors.
        """
        self._connect()

        # Safety check
        self._validate_sql(sql)

        limit = min(limit, 5000)
        limited_sql = self._apply_limit(sql, limit)

        t0 = time.perf_counter()
        try:
            if params is None:
                df: pd.DataFrame = self._con.execute(limited_sql).df()
            else:
                df = self._con.execute(limited_sql, params).df()
        except Exception as e:
            raise RuntimeError(f"Query execution failed: {e}") from e
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        df = df.fillna(value="")
        for col in df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns:
            df[col] = df[col].astype(str)

        return {
            "sql": limited_sql,
            "columns": list(df.columns),
            "data": df.to_dict(orient="records"),
            "row_count": len(df),
            "execution_time_ms": elapsed_ms,
        }

    @staticmethod
    def _apply_limit(sql: str, limit: int) -> str:
        """Add or replace LIMIT clause in SQL query."""
        sql_stripped = sql.rstrip("; \n\t")
        upper = sql_stripped.upper()

        # If LIMIT already exists, replace it
        limit_match = re.search(r"\bLIMIT\s+\d+\b", upper)
        if limit_match:
            start = limit_match.start()
            return sql_stripped[:start] + f"LIMIT {limit}"

        return f"{sql_stripped} LIMIT {limit}"

    def get_table_info(self) -> dict[str, Any]:
        """Return schema info for argo_profiles table."""
        self._connect()
        try:
            schema_df = self._con.execute("DESCRIBE argo_profiles").df()
            count_row = self._con.execute("SELECT COUNT(*) as n FROM argo_profiles").fetchone()
            return {
                "table": "argo_profiles",
                "row_count": count_row[0] if count_row else 0,
                "schema": schema_df.to_dict(orient="records"),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_summary_stats(self) -> dict[str, Any]:
        """Return dataset summary statistics."""
        self._connect()
        try:
            row = self._con.execute("""
                SELECT
                    COUNT(*) AS total_rows,
                    COUNT(DISTINCT float_id) AS unique_floats,
                    COUNT(DISTINCT file_name) AS files_represented,
                    MIN(time) AS earliest,
                    MAX(time) AS latest,
                    MIN(depth) AS min_depth,
                    MAX(depth) AS max_depth,
                    SUM(CASE WHEN latitude BETWEEN 5 AND 22
                              AND longitude BETWEEN 80 AND 100 THEN 1 ELSE 0 END) AS bay_of_bengal_obs,
                    SUM(CASE WHEN latitude BETWEEN 5 AND 25
                              AND longitude BETWEEN 55 AND 78 THEN 1 ELSE 0 END) AS arabian_sea_obs
                FROM argo_profiles
                WHERE latitude IS NOT NULL
            """).fetchone()

            return {
                "total_rows": row[0],
                "unique_floats": row[1],
                "files_represented": row[2],
                "date_range": {"min": str(row[3])[:10], "max": str(row[4])[:10]},
                "depth_range": {"min_m": round(float(row[5]), 1), "max_m": round(float(row[6]), 1)},
                "regional_obs": {
                    "bay_of_bengal": row[7],
                    "arabian_sea": row[8],
                },
                "regions_covered": ["Bay of Bengal", "Arabian Sea", "Indian Ocean"],
            }
        except Exception as e:
            return {"error": str(e)}

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self._con:
            self._con.close()
            self._ready = False


# Module-level singleton
_service: DuckDBService | None = None


def get_duckdb_service() -> DuckDBService:
    """Get or create the module-level DuckDBService singleton."""
    global _service
    if _service is None:
        _service = DuckDBService()
    return _service


def execute_query(sql: str, limit: int = 1000) -> dict[str, Any]:
    """Module-level convenience wrapper."""
    return get_duckdb_service().execute_query(sql, limit=limit)
