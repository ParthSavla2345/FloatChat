#!/usr/bin/env python3
import sys
import json
import signal
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import netCDF4
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from config import (
    ARCHIVE_DIR,
    PARQUET_FILE,
    SUMMARY_FILE,
    FILL_VALUE,
    VAR_CONFIG,
    OUTPUT_COLUMNS,
    setup_logging,
)

logger = setup_logging("extract_profiles")

ARGO_EPOCH = datetime(1950, 1, 1, tzinfo=timezone.utc)
_interrupted = False


def _handle_interrupt(signum, frame):
    global _interrupted
    if not _interrupted:
        logger.warning("KeyboardInterrupt received – finishing current file then stopping")
        _interrupted = True


signal.signal(signal.SIGINT, _handle_interrupt)


def _decode_chars(arr: np.ndarray) -> str:
    flat = np.ma.getdata(arr).flatten()
    chars = []
    for c in flat:
        if isinstance(c, np.ma.MaskedConstant):
            continue
        if isinstance(c, bytes):
            try:
                chars.append(c.decode("ascii"))
            except UnicodeDecodeError:
                chars.append("?")
    return "".join(chars).strip()


def _juld_to_datetime(juld: float) -> datetime:
    try:
        td = pd.Timedelta(days=juld)
        return ARGO_EPOCH + td
    except Exception:
        return pd.NaT


def _safe_select(var_name_adjusted: str, var_name_standard: str, ds: netCDF4.Dataset) -> np.ndarray | None:
    if var_name_adjusted in ds.variables:
        return ds.variables[var_name_adjusted][:]
    if var_name_standard in ds.variables:
        return ds.variables[var_name_standard][:]
    return None


def _replace_fill(data: np.ndarray, fill_value: float = FILL_VALUE) -> np.ndarray:
    if isinstance(data, np.ma.MaskedArray):
        return np.ma.filled(data, np.nan).astype(np.float32)
    arr = data.astype(np.float32)
    arr[arr == fill_value] = np.nan
    return arr


def extract_file(path: Path) -> pd.DataFrame | None:
    try:
        ds = netCDF4.Dataset(str(path), "r")
    except Exception as e:
        logger.error("Cannot open %s: %s", path.name, e)
        return None

    n_prof = ds.dimensions["N_PROF"].size if "N_PROF" in ds.dimensions else 0
    if n_prof == 0:
        logger.warning("No profiles in %s", path.name)
        ds.close()
        return None

    try:
        platform_raw = ds.variables["PLATFORM_NUMBER"][:]
        float_ids = [_decode_chars(platform_raw[i]) for i in range(n_prof)]
    except Exception as e:
        logger.warning("Cannot decode PLATFORM_NUMBER in %s: %s", path.name, e)
        float_ids = [path.stem] * n_prof

    try:
        cycle_numbers = ds.variables["CYCLE_NUMBER"][:]
    except Exception:
        cycle_numbers = np.arange(1, n_prof + 1, dtype=np.int32)

    try:
        juld = ds.variables["JULD"][:]
    except Exception:
        juld = np.full(n_prof, np.nan)

    try:
        latitude = ds.variables["LATITUDE"][:]
    except Exception:
        latitude = np.full(n_prof, np.nan)

    try:
        longitude = ds.variables["LONGITUDE"][:]
    except Exception:
        longitude = np.full(n_prof, np.nan)

    pres_data = _safe_select("PRES_ADJUSTED", "PRES", ds)
    temp_data = _safe_select("TEMP_ADJUSTED", "TEMP", ds)
    psal_data = _safe_select("PSAL_ADJUSTED", "PSAL", ds)

    ds.close()

    rows = []
    file_name = path.name

    for p in range(n_prof):
        if _interrupted:
            break

        pres_p = _replace_fill(pres_data[p]) if pres_data is not None else np.full(0, np.nan)
        temp_p = _replace_fill(temp_data[p]) if temp_data is not None else np.full(0, np.nan)
        psal_p = _replace_fill(psal_data[p]) if psal_data is not None else np.full(0, np.nan)

        n_levels = max(
            len(pres_p) if pres_data is not None else 0,
            len(temp_p) if temp_data is not None else 0,
            len(psal_p) if psal_data is not None else 0,
        )
        if n_levels == 0:
            continue

        dt = _juld_to_datetime(float(juld[p])) if not np.isnan(juld[p]) else pd.NaT
        lat = float(latitude[p]) if not np.isnan(latitude[p]) else None
        lon = float(longitude[p]) if not np.isnan(longitude[p]) else None
        cyc = int(cycle_numbers[p]) if not np.isnan(cycle_numbers[p]) else p + 1

        for k in range(n_levels):
            rows.append(
                {
                    "file_name": file_name,
                    "float_id": float_ids[p],
                    "profile_number": p + 1,
                    "cycle_number": cyc,
                    "datetime": dt,
                    "latitude": lat,
                    "longitude": lon,
                    "depth": float(pres_p[k]) if k < len(pres_p) else None,
                    "temperature": float(temp_p[k]) if k < len(temp_p) else None,
                    "salinity": float(psal_p[k]) if k < len(psal_p) else None,
                }
            )

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    return df


def write_parquet_incremental(df: pd.DataFrame, writer) -> None:
    table = pa.Table.from_pandas(df, preserve_index=False)
    if writer is None:
        writer = pq.ParquetWriter(str(PARQUET_FILE), table.schema)
    writer.write_table(table)
    return writer


def main():
    nc_files = sorted(ARCHIVE_DIR.glob("*.nc"))
    if not nc_files:
        logger.warning("No NetCDF files found in %s", ARCHIVE_DIR)
        return

    logger.info("Starting extraction of %d files", len(nc_files))
    start_time = time.time()
    total_rows = 0
    processed = 0
    failed = 0
    writer = None

    try:
        for idx, f in enumerate(nc_files, 1):
            if _interrupted:
                logger.info("Interrupted – finishing up after file %d/%d", idx - 1, len(nc_files))
                break
            logger.info("[%d/%d] Processing %s", idx, len(nc_files), f.name)
            df = extract_file(f)
            if df is not None and len(df) > 0:
                writer = write_parquet_incremental(df, writer)
                total_rows += len(df)
                processed += 1
                logger.info("  -> %d rows (total %d)", len(df), total_rows)
            else:
                failed += 1
                logger.warning("  -> skipped (no data extracted)")
    except Exception as e:
        logger.error("Unexpected error during extraction: %s", e, exc_info=True)
    finally:
        if writer is not None:
            writer.close()

    elapsed = time.time() - start_time
    summary = {
        "status": "interrupted" if _interrupted else "completed",
        "total_files_found": len(nc_files),
        "files_processed": processed,
        "files_failed": failed,
        "total_rows_written": total_rows,
        "output_file": str(PARQUET_FILE),
        "elapsed_seconds": round(elapsed, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    logger.info("Extraction complete – summary written to %s", SUMMARY_FILE)
    logger.info("Summary: %s", json.dumps(summary, default=str))
    return summary


if __name__ == "__main__":
    main()
