"""Spatial and temporal retrieval for ARGO profile observations.

The project stores the recovery-era `float_id` values directly from the processed
DuckDB table. These values are not guaranteed to be the raw NetCDF
`PLATFORM_NUMBER` WMO identifiers; the raw variable name is documented in the
project docs and stage-6 validation notes.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from services.duckdb_service import get_duckdb_service

REGION_BOUNDS: dict[str, dict[str, float]] = {
    "Arabian Sea": {"lat_min": 5.0, "lat_max": 25.0, "lon_min": 55.0, "lon_max": 78.0},
    "Bay of Bengal": {"lat_min": 5.0, "lat_max": 22.0, "lon_min": 80.0, "lon_max": 100.0},
    "Equatorial Indian Ocean": {"lat_min": -10.0, "lat_max": 10.0, "lon_min": 60.0, "lon_max": 90.0},
    "Southern Indian Ocean": {"lat_min": -60.0, "lat_max": -10.0, "lon_min": 20.0, "lon_max": 120.0},
    "Indian Ocean": {"lat_min": -60.0, "lat_max": 30.0, "lon_min": 20.0, "lon_max": 120.0},
}


def _as_utc_timestamp(value: Any) -> str | None:
    """Normalize a datetime-like input to an ISO UTC timestamp string."""
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.isoformat()


def _validate_latitude(latitude: float) -> float:
    value = float(latitude)
    if value < -90 or value > 90:
        raise ValueError("Latitude must be between -90 and 90 degrees.")
    return value


def _validate_longitude(longitude: float) -> float:
    value = float(longitude)
    if value < -180 or value > 180:
        raise ValueError("Longitude must be between -180 and 180 degrees.")
    return value


def _validate_date_range(start: Any, end: Any) -> tuple[str | None, str | None]:
    start_ts = _as_utc_timestamp(start)
    end_ts = _as_utc_timestamp(end)
    if start_ts and end_ts and start_ts > end_ts:
        raise ValueError("Start date must be earlier than or equal to end date.")
    return start_ts, end_ts


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


class SpatialTemporalService:
    """Service layer for safe spatial and temporal retrieval over DuckDB."""

    def __init__(self, db_service=None):
        self.db_service = db_service or get_duckdb_service()

    def _fetch_dataframe(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> pd.DataFrame:
        self.db_service._connect()
        if params is None:
            df = self.db_service._con.execute(sql).df()
        else:
            df = self.db_service._con.execute(sql, params).df()
        if df.empty:
            return df
        for col in [
            "datetime",
            "observation_start",
            "observation_end",
            "earliest_observation",
            "latest_observation",
        ]:
            if col in df.columns:
                df[col] = df[col].map(
                    lambda value: _as_utc_timestamp(value) if value is not None and value != "" else None
                )
        return df

    def search_bbox(
        self,
        latitude_min: float,
        latitude_max: float,
        longitude_min: float,
        longitude_max: float,
        start_datetime: Any | None = None,
        end_datetime: Any | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return profile rows within a latitude/longitude bounding box."""
        lat_min = _validate_latitude(latitude_min)
        lat_max = _validate_latitude(latitude_max)
        lon_min = _validate_longitude(longitude_min)
        lon_max = _validate_longitude(longitude_max)
        start_ts, end_ts = _validate_date_range(start_datetime, end_datetime)

        clauses = [
            "latitude IS NOT NULL",
            "longitude IS NOT NULL",
            "latitude BETWEEN ? AND ?",
            "longitude BETWEEN ? AND ?",
        ]
        params: list[Any] = [lat_min, lat_max, lon_min, lon_max]

        if start_ts is not None:
            clauses.append("datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(start_ts)
        if end_ts is not None:
            clauses.append("datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(end_ts)

        sql = f"""
            SELECT
                file_name,
                float_id,
                profile_number,
                cycle_number,
                datetime,
                latitude,
                longitude,
                depth,
                temperature,
                salinity
            FROM argo_profiles
            WHERE {' AND '.join(clauses)}
            ORDER BY datetime DESC
            LIMIT ?
        """
        params.append(min(int(limit), 5000))
        df = self._fetch_dataframe(sql, params)
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    def search_radius(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
        start_datetime: Any | None = None,
        end_datetime: Any | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return profiles within a radius of a coordinate pair in kilometres."""
        lat = _validate_latitude(latitude)
        lon = _validate_longitude(longitude)
        radius = float(radius_km)
        if radius < 0:
            raise ValueError("Radius must be non-negative.")
        start_ts, end_ts = _validate_date_range(start_datetime, end_datetime)

        distance_sql = (
            "6371.0 * ACOS(COS(RADIANS(?)) * COS(RADIANS(latitude)) * "
            "COS(RADIANS(longitude) - RADIANS(?)) + SIN(RADIANS(?)) * SIN(RADIANS(latitude)))"
        )
        clauses = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
        params: list[Any] = [lat, lon, lat]

        if start_ts is not None:
            clauses.append("datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(start_ts)
        if end_ts is not None:
            clauses.append("datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(end_ts)

        sql = f"""
            SELECT
                file_name,
                float_id,
                profile_number,
                cycle_number,
                datetime,
                latitude,
                longitude,
                depth,
                temperature,
                salinity,
                {distance_sql} AS distance_km
            FROM argo_profiles
            WHERE {' AND '.join(clauses)}
              AND {distance_sql} <= ?
            ORDER BY distance_km ASC
            LIMIT ?
        """
        params.extend([lat, lon, lat, radius, min(int(limit), 5000)])
        df = self._fetch_dataframe(sql, params)
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    def search_by_region(
        self,
        region_name: str,
        start_datetime: Any | None = None,
        end_datetime: Any | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return profiles that fall within a predefined region."""
        key = region_name.strip()
        if key not in REGION_BOUNDS:
            valid = ", ".join(sorted(REGION_BOUNDS))
            raise ValueError(f"Unknown region '{region_name}'. Valid values: {valid}")

        bounds = REGION_BOUNDS[key]
        return self.search_bbox(
            latitude_min=bounds["lat_min"],
            latitude_max=bounds["lat_max"],
            longitude_min=bounds["lon_min"],
            longitude_max=bounds["lon_max"],
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            limit=limit,
        )

    def nearest_floats(
        self,
        latitude: float,
        longitude: float,
        top_k: int = 5,
        max_radius_km: float | None = None,
        start_datetime: Any | None = None,
        end_datetime: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Return the nearest unique float identifiers, grouped by float_id."""
        lat = _validate_latitude(latitude)
        lon = _validate_longitude(longitude)
        start_ts, end_ts = _validate_date_range(start_datetime, end_datetime)
        top_k = max(1, int(top_k))

        distance_sql = (
            "6371.0 * ACOS(COS(RADIANS(?)) * COS(RADIANS(latitude)) * "
            "COS(RADIANS(longitude) - RADIANS(?)) + SIN(RADIANS(?)) * SIN(RADIANS(latitude)))"
        )

        where_clauses = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
        params: list[Any] = [lat, lon, lat]

        if start_ts is not None:
            where_clauses.append("datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(start_ts)
        if end_ts is not None:
            where_clauses.append("datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(end_ts)

        radius_clause = ""
        if max_radius_km is not None:
            radius = float(max_radius_km)
            if radius <= 0:
                raise ValueError("max_radius_km must be > 0 when supplied.")
            radius_clause = f" AND {distance_sql} <= ?"
            params.extend([lat, lon, lat, radius])

        sql = f"""
            WITH distances AS (
                SELECT
                    float_id,
                    MIN(file_name) AS representative_file,
                    MIN(datetime) AS earliest_observation,
                    MAX(datetime) AS latest_observation,
                    COUNT(*) AS profile_count,
                    MIN({distance_sql}) AS nearest_distance_km
                FROM argo_profiles
                WHERE {' AND '.join(where_clauses)}{radius_clause}
                GROUP BY float_id
            )
            SELECT *
            FROM distances
            WHERE nearest_distance_km IS NOT NULL
            ORDER BY nearest_distance_km ASC, float_id ASC
            LIMIT ?
        """
        params.append(top_k)
        df = self._fetch_dataframe(sql, params)
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    def search_date_range(
        self,
        start_datetime: Any,
        end_datetime: Any,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return profiles whose timestamps fall within a date range."""
        start_ts, end_ts = _validate_date_range(start_datetime, end_datetime)
        if start_ts is None or end_ts is None:
            raise ValueError("Both start_datetime and end_datetime must be provided.")

        sql = """
            SELECT
                file_name,
                float_id,
                profile_number,
                cycle_number,
                datetime,
                latitude,
                longitude,
                depth,
                temperature,
                salinity
            FROM argo_profiles
            WHERE datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)
              AND datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)
            ORDER BY datetime ASC
            LIMIT ?
        """
        params = [start_ts, end_ts, min(int(limit), 5000)]
        df = self._fetch_dataframe(sql, params)
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    def search_by_month(self, year: int, month: int, limit: int = 1000) -> list[dict[str, Any]]:
        """Return all profiles for a specific month and year."""
        if not 1 <= int(month) <= 12:
            raise ValueError("Month must be between 1 and 12.")
        sql = """
            SELECT
                file_name,
                float_id,
                profile_number,
                cycle_number,
                datetime,
                latitude,
                longitude,
                depth,
                temperature,
                salinity
            FROM argo_profiles
            WHERE EXTRACT(YEAR FROM datetime) = CAST(? AS INTEGER)
              AND EXTRACT(MONTH FROM datetime) = CAST(? AS INTEGER)
            ORDER BY datetime ASC
            LIMIT ?
        """
        params = [int(year), int(month), min(int(limit), 5000)]
        df = self._fetch_dataframe(sql, params)
        return df.where(pd.notnull(df), None).to_dict(orient="records")

    def search_last_days(self, days: int, limit: int = 1000) -> list[dict[str, Any]]:
        """Return profiles from the previous N days relative to the current UTC time."""
        window_days = int(days)
        if window_days < 0:
            raise ValueError("days must be >= 0.")
        now_utc = pd.Timestamp.utcnow().tz_localize("UTC")
        start_ts = (now_utc - pd.Timedelta(days=window_days)).isoformat()
        return self.search_date_range(start_ts, now_utc.isoformat(), limit=limit)

    def search_last_months(self, months: int, limit: int = 1000) -> list[dict[str, Any]]:
        """Return profiles from the previous N months relative to the current UTC time."""
        window_months = int(months)
        if window_months < 0:
            raise ValueError("months must be >= 0.")
        now_utc = pd.Timestamp.utcnow().tz_localize("UTC")
        start_ts = (now_utc - pd.DateOffset(months=window_months)).isoformat()
        return self.search_date_range(start_ts, now_utc.isoformat(), limit=limit)

    def compare_periods(
        self,
        first_start: Any,
        first_end: Any,
        second_start: Any,
        second_end: Any,
    ) -> dict[str, Any]:
        """Compare counts across two time periods."""
        first_start_ts, first_end_ts = _validate_date_range(first_start, first_end)
        second_start_ts, second_end_ts = _validate_date_range(second_start, second_end)

        if None in (first_start_ts, first_end_ts, second_start_ts, second_end_ts):
            raise ValueError("All comparison period boundaries must be supplied.")

        sql = """
            WITH first AS (
                SELECT COUNT(*) AS profile_count
                FROM argo_profiles
                WHERE datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)
                  AND datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)
            ),
            second AS (
                SELECT COUNT(*) AS profile_count
                FROM argo_profiles
                WHERE datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)
                  AND datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)
            )
            SELECT first.profile_count AS first_period_count,
                   second.profile_count AS second_period_count,
                   second.profile_count - first.profile_count AS delta_count
            FROM first, second
        """
        params = [first_start_ts, first_end_ts, second_start_ts, second_end_ts]
        df = self._fetch_dataframe(sql, params)
        if df.empty:
            return {"first_period_count": 0, "second_period_count": 0, "delta_count": 0}
        return df.where(pd.notnull(df), None).to_dict(orient="records")[0]

    def get_date_bounds(self) -> dict[str, str | None]:
        """Return the earliest and latest observation timestamps in UTC."""
        sql = """
            SELECT
                MIN(datetime) AS earliest_datetime,
                MAX(datetime) AS latest_datetime
            FROM argo_profiles
        """
        df = self._fetch_dataframe(sql)
        if df.empty:
            return {"earliest_datetime": None, "latest_datetime": None}
        row = df.iloc[0].to_dict()
        return {
            "earliest_datetime": _as_utc_timestamp(row.get("earliest_datetime")),
            "latest_datetime": _as_utc_timestamp(row.get("latest_datetime")),
        }


def get_spatial_temporal_service() -> SpatialTemporalService:
    """Return the module-level singleton for spatial and temporal retrieval."""
    global _service
    if _service is None:
        _service = SpatialTemporalService()
    return _service


_service: SpatialTemporalService | None = None
