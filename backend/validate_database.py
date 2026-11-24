#!/usr/bin/env python3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb

from config import PARQUET_FILE, DUCKDB_FILE, VALIDATION_REPORT, setup_logging

logger = setup_logging("validate_database")

REPORT_TEMPLATE = """
{sep}
DATABASE VALIDATION REPORT
{sep}

Parquet source: {parquet}
DuckDB database: {duckdb}

Row count:           {row_count:>12,}
Unique floats:       {unique_floats:>12,}
Unique profiles:     {unique_profiles:>12,}

Latitude range:      {lat_min:>8.3f}  to  {lat_max:>8.3f}
Longitude range:     {lon_min:>8.3f}  to  {lon_max:>8.3f}
Temperature range:   {temp_min:>8.3f}  to  {temp_max:>8.3f}  °C
Salinity range:      {psal_min:>8.3f}  to  {psal_max:>8.3f}  PSU
Depth range:         {depth_min:>8.1f}  to  {depth_max:>8.1f}  dbar

Duplicate rows:      {duplicates:>12,}
Float ID anomalies:  {float_anomalies}

Sample records (3):
{sample_records}

{sep}
END OF REPORT
{sep}
"""


def validate() -> dict:
    if not PARQUET_FILE.exists():
        logger.error("Parquet file not found: %s", PARQUET_FILE)
        sys.exit(1)
    if not DUCKDB_FILE.exists():
        logger.error("DuckDB file not found: %s", DUCKDB_FILE)
        sys.exit(1)

    logger.info("Connecting to DuckDB: %s", DUCKDB_FILE)
    con = duckdb.connect(str(DUCKDB_FILE))

    try:
        row_count = con.execute("SELECT COUNT(*) FROM argo_profiles").fetchone()[0]
        unique_floats = con.execute("SELECT COUNT(DISTINCT float_id) FROM argo_profiles").fetchone()[0]
        unique_profiles = con.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT float_id, profile_number FROM argo_profiles)"
        ).fetchone()[0]

        lat_range = con.execute("SELECT MIN(latitude), MAX(latitude) FROM argo_profiles").fetchone()
        lon_range = con.execute("SELECT MIN(longitude), MAX(longitude) FROM argo_profiles").fetchone()
        temp_range = con.execute("SELECT MIN(temperature), MAX(temperature) FROM argo_profiles").fetchone()
        psal_range = con.execute("SELECT MIN(salinity), MAX(salinity) FROM argo_profiles").fetchone()
        depth_range = con.execute("SELECT MIN(depth), MAX(depth) FROM argo_profiles").fetchone()

        duplicates = con.execute(
            """
            SELECT COUNT(*) - COUNT(DISTINCT (float_id, profile_number, cycle_number, depth, datetime, latitude, longitude, temperature, salinity))
            FROM argo_profiles
            """
        ).fetchone()[0]

        float_anomalies = con.execute(
            """
            SELECT float_id, COUNT(*) AS cnt
            FROM argo_profiles
            WHERE float_id IS NULL OR float_id = ''
            GROUP BY float_id
            """
        ).fetchall()
        float_anomalies_count = sum(row[1] for row in float_anomalies) if float_anomalies else 0

        sample = con.execute(
            """
            SELECT float_id, profile_number, cycle_number, datetime,
                   latitude, longitude, depth, temperature, salinity
            FROM argo_profiles
            USING SAMPLE 3
            """
        ).fetchdf()

    finally:
        con.close()

    report = REPORT_TEMPLATE.format(
        sep="=" * 60,
        parquet=PARQUET_FILE,
        duckdb=DUCKDB_FILE,
        row_count=row_count,
        unique_floats=unique_floats,
        unique_profiles=unique_profiles,
        lat_min=lat_range[0],
        lat_max=lat_range[1],
        lon_min=lon_range[0],
        lon_max=lon_range[1],
        temp_min=temp_range[0],
        temp_max=temp_range[1],
        psal_min=psal_range[0],
        psal_max=psal_range[1],
        depth_min=depth_range[0],
        depth_max=depth_range[1],
        duplicates=duplicates,
        float_anomalies=float_anomalies_count,
        sample_records=sample.to_string(index=False),
    )
    return report


def main():
    start = time.time()
    report = validate()
    VALIDATION_REPORT.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_REPORT.write_text(report, encoding="utf-8")
    elapsed = time.time() - start
    logger.info("Validation report written to %s (%.2f seconds)", VALIDATION_REPORT, elapsed)
    print(report)


if __name__ == "__main__":
    main()
