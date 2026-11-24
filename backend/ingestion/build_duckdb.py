"""
Phase 3 — DuckDB Database Build
Loads argo_profiles.parquet into a persistent DuckDB database,
creates the argo_profiles table, and prints summary statistics.

Output: data/processed/floatchat.duckdb
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from config import settings


def build_duckdb() -> None:
    parquet_path = settings.argo_profiles_parquet
    db_path = settings.duckdb_path

    if not parquet_path.exists():
        print(f"[ERROR] Parquet file not found: {parquet_path}")
        print("[ERROR] Please run extract_profiles.py first.")
        sys.exit(1)

    settings.ensure_dirs()

    print(f"\n[INFO] Loading: {parquet_path}")
    print(f"[INFO] DuckDB target: {db_path}\n")

    # Remove existing database to start fresh
    if db_path.exists():
        print(f"[INFO] Removing existing database: {db_path}")
        db_path.unlink()

    con = duckdb.connect(str(db_path))

    try:
        # Create table from parquet
        print("[INFO] Creating argo_profiles table...")
        con.execute(f"""
            CREATE TABLE argo_profiles AS
            SELECT
                file_name,
                profile_index,
                float_id,
                CAST(time AS TIMESTAMP) AS time,
                CAST(latitude AS DOUBLE) AS latitude,
                CAST(longitude AS DOUBLE) AS longitude,
                CAST(depth AS DOUBLE) AS depth,
                CAST(temperature AS DOUBLE) AS temperature,
                CAST(salinity AS DOUBLE) AS salinity,
                CAST(year AS INTEGER) AS year,
                CAST(month AS INTEGER) AS month
            FROM read_parquet('{parquet_path.as_posix()}')
        """)

        # Create useful indexes
        print("[INFO] Creating indexes...")
        con.execute("CREATE INDEX idx_float_id ON argo_profiles(float_id)")
        con.execute("CREATE INDEX idx_year ON argo_profiles(year)")
        con.execute("CREATE INDEX idx_latlon ON argo_profiles(latitude, longitude)")

        # ── Statistics ────────────────────────────────────────────────────
        print("\n[INFO] Computing statistics...\n")

        stats = con.execute("""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT float_id) AS unique_floats,
                COUNT(DISTINCT file_name) AS files_represented,
                MIN(time) AS earliest,
                MAX(time) AS latest,
                MIN(depth) AS min_depth,
                MAX(depth) AS max_depth,
                MIN(temperature) AS min_temp,
                MAX(temperature) AS max_temp,
                MIN(salinity) AS min_sal,
                MAX(salinity) AS max_sal,
                AVG(temperature) AS avg_temp,
                AVG(salinity) AS avg_sal
            FROM argo_profiles
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """).fetchone()

        (total_rows, unique_floats, files_rep,
         earliest, latest,
         min_depth, max_depth,
         min_temp, max_temp,
         min_sal, max_sal,
         avg_temp, avg_sal) = stats

        # Sample regional counts
        regional = con.execute("""
            SELECT
                SUM(CASE WHEN latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100 THEN 1 ELSE 0 END) AS bay_of_bengal,
                SUM(CASE WHEN latitude BETWEEN 5 AND 25 AND longitude BETWEEN 55 AND 78 THEN 1 ELSE 0 END) AS arabian_sea,
                SUM(CASE WHEN latitude BETWEEN -60 AND 30 AND longitude BETWEEN 20 AND 120 THEN 1 ELSE 0 END) AS indian_ocean
            FROM argo_profiles
        """).fetchone()

        print(f"""
╔══════════════════════════════════════════════════════════╗
  DUCKDB BUILD COMPLETE
╠══════════════════════════════════════════════════════════╣
  Database path     : {db_path}
╠══════════════════════════════════════════════════════════╣
  Total rows        : {total_rows:>12,}
  Unique floats     : {unique_floats:>12,}
  Files represented : {files_rep:>12,}
╠══════════════════════════════════════════════════════════╣
  Date range        : {earliest} → {latest}
  Depth range       : {min_depth:.1f} → {max_depth:.1f} dbar
  Temp range        : {min_temp:.2f} → {max_temp:.2f} °C  (avg: {avg_temp:.2f})
  Salinity range    : {min_sal:.2f} → {max_sal:.2f} PSU  (avg: {avg_sal:.2f})
╠══════════════════════════════════════════════════════════╣
  Bay of Bengal obs : {regional[0]:>12,}
  Arabian Sea obs   : {regional[1]:>12,}
  Indian Ocean obs  : {regional[2]:>12,}
╚══════════════════════════════════════════════════════════╝
""")

        # Verify table schema
        schema = con.execute("DESCRIBE argo_profiles").fetchdf()
        print("[INFO] Table schema:")
        print(schema.to_string(index=False))
        print()

    finally:
        con.close()


if __name__ == "__main__":
    build_duckdb()
