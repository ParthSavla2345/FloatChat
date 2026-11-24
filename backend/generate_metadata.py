#!/usr/bin/env python3
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import PARQUET_FILE, METADATA_PARQUET, METADATA_JSON, setup_logging

logger = setup_logging("generate_metadata")

META_COLUMNS = [
    "float_id",
    "total_profiles",
    "observation_start",
    "observation_end",
    "latitude_min",
    "latitude_max",
    "longitude_min",
    "longitude_max",
    "depth_min",
    "depth_max",
    "variables_available",
    "total_observations",
]


def _ocean_region(lat: float, lon: float) -> str:
    if 5 <= lat <= 25 and 60 <= lon <= 100:
        return "the Arabian Sea"
    if -10 <= lat <= 10 and 50 <= lon <= 100:
        return "the equatorial Indian Ocean"
    if -30 <= lat <= -10 and 30 <= lon <= 120:
        return "the southern Indian Ocean"
    if -10 <= lat <= 5 and 80 <= lon <= 100:
        return "the Bay of Bengal"
    if lat > 25 and 60 <= lon <= 100:
        return "the northern Arabian Sea"
    return "the Indian Ocean"


def build_metadata() -> pd.DataFrame:
    logger.info("Connecting to Parquet: %s", PARQUET_FILE)
    con = duckdb.connect()

    query = """
        SELECT
            float_id,
            COUNT(DISTINCT profile_number) AS total_profiles,
            MIN(datetime) AS observation_start,
            MAX(datetime) AS observation_end,
            MIN(latitude) AS latitude_min,
            MAX(latitude) AS latitude_max,
            MIN(longitude) AS longitude_min,
            MAX(longitude) AS longitude_max,
            MIN(depth) AS depth_min,
            MAX(depth) AS depth_max,
            ['temperature', 'salinity', 'pressure'] AS variables_available,
            COUNT(*) AS total_observations
        FROM read_parquet(?)
        GROUP BY float_id
        ORDER BY float_id
    """

    df = con.execute(query, [str(PARQUET_FILE)]).fetchdf()
    con.close()

    df.columns = [c.lower() for c in df.columns]
    for col in META_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[META_COLUMNS]
    logger.info("Generated metadata for %s floats", len(df))
    return df


def generate_summary(row: dict) -> str:
    sid = row["float_id"]
    nprof = row["total_profiles"]
    start = row["observation_start"]
    end = row["observation_end"]
    lat_min = row["latitude_min"]
    lat_max = row["latitude_max"]
    lon_min = row["longitude_min"]
    lon_max = row["longitude_max"]
    d_min = row["depth_min"]
    d_max = row["depth_max"]
    vars_list = row["variables_available"]

    vars_str = ", ".join(str(v) for v in vars_list) if vars_list is not None and len(vars_list) > 0 else "unknown"

    start_str = str(start)[:7] if start else "unknown"
    end_str = str(end)[:7] if end else "unknown"

    mid_lat = (lat_min + lat_max) / 2 if lat_min is not None and lat_max is not None else None
    mid_lon = (lon_min + lon_max) / 2 if lon_min is not None and lon_max is not None else None
    region = _ocean_region(mid_lat, mid_lon) if mid_lat is not None and mid_lon is not None else "the Indian Ocean"
    depth_str = f"{d_min:.0f} to {d_max:.0f} meters" if d_min is not None and d_max is not None else "the full water column"

    return (
        f"Float {sid} collected {nprof} profiles between {start_str} and {end_str} "
        f"in {region} with measurements of {vars_str} from {depth_str}."
    )


def main():
    start = time.time()
    if not PARQUET_FILE.exists():
        logger.error("Parquet file not found: %s", PARQUET_FILE)
        sys.exit(1)

    df = build_metadata()

    logger.info("Writing Parquet: %s", METADATA_PARQUET)
    METADATA_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, str(METADATA_PARQUET))

    records = df.to_dict(orient="records")
    for rec in records:
        rec["natural_language_summary"] = generate_summary(rec)
        for key in ("observation_start", "observation_end"):
            val = rec.get(key)
            if val is not None:
                rec[key] = str(val)

    logger.info("Writing JSON: %s", METADATA_JSON)
    METADATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    METADATA_JSON.write_text(
        json.dumps(records, indent=2, default=str), encoding="utf-8"
    )

    elapsed = time.time() - start
    logger.info(
        "Metadata generation complete in %.2f seconds — %s floats",
        elapsed,
        len(df),
    )


if __name__ == "__main__":
    main()
