#!/usr/bin/env python3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb

from config import PARQUET_FILE, DUCKDB_FILE, setup_logging

logger = setup_logging("build_duckdb")


def drop_existing_table(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP TABLE IF EXISTS argo_profiles")
    logger.info("Dropped existing argo_profiles table")


def create_table_from_parquet(con: duckdb.DuckDBPyConnection) -> int:
    logger.info("Creating argo_profiles table from %s", PARQUET_FILE)
    con.execute(
        f"""
        CREATE TABLE argo_profiles AS
        SELECT * FROM read_parquet('{PARQUET_FILE}')
        """
    )
    result = con.execute("SELECT COUNT(*) FROM argo_profiles").fetchone()
    row_count = result[0]
    logger.info("Imported %s rows into argo_profiles", f"{row_count:,}")
    return row_count


def verify_schema(con: duckdb.DuckDBPyConnection) -> None:
    logger.info("Verifying schema...")
    rows = con.execute("DESCRIBE argo_profiles").fetchall()
    for row in rows:
        logger.info("  %s %s", row[0], row[1])


def main():
    start = time.time()
    if not PARQUET_FILE.exists():
        logger.error("Parquet file not found: %s", PARQUET_FILE)
        sys.exit(1)

    db_path = str(DUCKDB_FILE)
    logger.info("Connecting to DuckDB: %s", db_path)
    con = duckdb.connect(db_path)

    try:
        drop_existing_table(con)
        row_count = create_table_from_parquet(con)
        verify_schema(con)
        elapsed = time.time() - start
        logger.info("DuckDB build complete in %.2f seconds — %s rows", elapsed, f"{row_count:,}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
