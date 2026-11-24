#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import netCDF4
import numpy as np
from config import ARCHIVE_DIR, REPORT_FILE, setup_logging

logger = setup_logging("inspect_netcdf")

ADJUSTED_SUFFIXES = ("_ADJUSTED", "_ADJUSTED_QC", "_ADJUSTED_ERROR")


def decode_char_array(arr: np.ndarray) -> str:
    flat = arr.flatten()
    chars = [chr(c) for c in flat if c != 0 and not isinstance(c, np.ma.MaskedConstant)]
    return "".join(chars).strip()


def inspect_file(path: Path) -> dict:
    info = {"file": path.name, "dimensions": {}, "variables": {}, "global_attrs": {}, "adjusted_vars": []}
    try:
        ds = netCDF4.Dataset(str(path), "r")
    except Exception as e:
        logger.error("Cannot open %s: %s", path.name, e)
        info["error"] = str(e)
        return info

    for name, dim in ds.dimensions.items():
        info["dimensions"][name] = len(dim)

    for name, var in ds.variables.items():
        attrs = {}
        for attr_name in var.ncattrs():
            val = getattr(var, attr_name)
            if isinstance(val, np.ndarray):
                val = val.tolist()
            attrs[attr_name] = val
        info["variables"][name] = {
            "dimensions": var.dimensions,
            "dtype": str(var.dtype),
            "attrs": attrs,
        }

    for name in ds.ncattrs():
        val = getattr(ds, name)
        if isinstance(val, np.ndarray):
            val = val.tolist()
        info["global_attrs"][name] = val

    for name in ds.variables:
        if name.endswith("_ADJUSTED") and not name.endswith("_ADJUSTED_QC") and not name.endswith("_ADJUSTED_ERROR"):
            info["adjusted_vars"].append(name)

    info["adjusted_vars"] = sorted(set(info["adjusted_vars"]))
    ds.close()
    return info


def generate_report(files_infos: list[dict]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("ARGO NETCDF INSPECTION REPORT")
    lines.append(f"Total files inspected: {len(files_infos)}")
    lines.append("=" * 80)

    dim_keys: set[str] = set()
    var_keys: set[str] = set()
    for fi in files_infos:
        dim_keys.update(fi.get("dimensions", {}).keys())
        var_keys.update(fi.get("variables", {}).keys())

    lines.append(f"\n\nDistinct dimensions ({len(dim_keys)}):")
    for k in sorted(dim_keys):
        sizes = sorted(set(fi["dimensions"].get(k, -1) for fi in files_infos if "dimensions" in fi))
        lines.append(f"  {k}: {', '.join(str(s) for s in sizes)}")

    lines.append(f"\n\nDistinct variables ({len(var_keys)}):")
    for k in sorted(var_keys):
        has_adjusted = any("ADJUSTED" in k and not any(k.endswith(s) for s in ADJUSTED_SUFFIXES) for _ in [1])
        dims_samples = sorted(
            set(
                tuple(fi["variables"][k]["dimensions"])
                for fi in files_infos
                if "variables" in fi and k in fi["variables"]
            )
        )
        dtype_samples = sorted(
            set(
                fi["variables"][k]["dtype"]
                for fi in files_infos
                if "variables" in fi and k in fi["variables"]
            )
        )
        lines.append(f"  {k}:")
        lines.append(f"    dims: {dims_samples}")
        lines.append(f"    dtype: {dtype_samples}")

    lines.append("\n\nGlobal attributes (first file):")
    if files_infos:
        for k, v in files_infos[0].get("global_attrs", {}).items():
            lines.append(f"  {k}: {v}")

    all_adjusted = set()
    for fi in files_infos:
        all_adjusted.update(fi.get("adjusted_vars", []))
    lines.append(f"\n\nDetected adjusted variables ({len(all_adjusted)}):")
    for v in sorted(all_adjusted):
        present_in = sum(1 for fi in files_infos if v in fi.get("variables", {}))
        lines.append(f"  {v} (in {present_in}/{len(files_infos)} files)")

    error_count = sum(1 for fi in files_infos if "error" in fi)
    if error_count:
        lines.append(f"\n\nFiles with errors ({error_count}):")
        for fi in files_infos:
            if "error" in fi:
                lines.append(f"  {fi['file']}: {fi['error']}")

    lines.append("\n" + "=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    nc_files = sorted(ARCHIVE_DIR.glob("*.nc"))
    if not nc_files:
        logger.warning("No NetCDF files found in %s", ARCHIVE_DIR)
        return

    logger.info("Found %d NetCDF files in %s", len(nc_files), ARCHIVE_DIR)
    files_infos: list[dict] = []
    for f in nc_files:
        logger.info("Inspecting %s", f.name)
        info = inspect_file(f)
        files_infos.append(info)

    report = generate_report(files_infos)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(report, encoding="utf-8")
    logger.info("Report written to %s", REPORT_FILE)
    print(f"\nReport preview (last 30 lines):")
    lines = report.splitlines()
    for line in lines[-30:]:
        print(line)


if __name__ == "__main__":
    main()
