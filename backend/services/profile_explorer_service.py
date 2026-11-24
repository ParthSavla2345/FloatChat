"""Read-only summary and profile-level retrieval for the OceanIQ dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any

from services.duckdb_service import get_duckdb_service
from services.spatial_temporal_service import REGION_BOUNDS

PARAMETER_COLUMNS = {
    "temperature": "temperature",
    "salinity": "salinity",
    "depth": "depth",
}
MAX_PAGE_SIZE = 200
MAX_MAP_RESULTS = 2000
MAX_PROFILE_LEVELS = 10000


def _utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(value: Any) -> Any:
    if isinstance(value, datetime):
        timestamp = _utc_datetime(value)
        return timestamp.isoformat() if timestamp else None
    return value


def _rows(cursor: Any) -> list[dict[str, Any]]:
    names = [item[0] for item in cursor.description]
    return [
        {name: _serialize(value) for name, value in zip(names, row)}
        for row in cursor.fetchall()
    ]


class ProfileExplorerService:
    """Provide bounded read-only profile queries using the shared DuckDB connection."""

    def __init__(self, db_service: Any | None = None) -> None:
        self.db_service = db_service or get_duckdb_service()

    def _connection(self):
        self.db_service._connect()
        connection = self.db_service._con
        if connection is None:
            raise RuntimeError("DuckDB read-only connection is unavailable.")
        connection.execute("SET enable_progress_bar = false")
        return connection

    def get_summary(self) -> dict[str, Any]:
        """Return dataset-wide counts, UTC coverage and coordinate bounds."""
        cursor = self._connection().execute(
            """
            SELECT
                COUNT(*) AS observation_rows,
                COUNT(DISTINCT (file_name, profile_number)) AS profile_count,
                COUNT(DISTINCT float_id) AS project_float_count,
                COUNT(DISTINCT file_name) AS source_file_count,
                COUNT(*) FILTER (WHERE temperature IS NOT NULL) AS temperature_rows,
                COUNT(*) FILTER (WHERE salinity IS NOT NULL) AS salinity_rows,
                COUNT(*) FILTER (WHERE depth IS NOT NULL) AS depth_rows,
                CAST(MIN(datetime) AS VARCHAR) AS earliest_datetime,
                CAST(MAX(datetime) AS VARCHAR) AS latest_datetime,
                MIN(latitude) AS latitude_min,
                MAX(latitude) AS latitude_max,
                MIN(longitude) AS longitude_min,
                MAX(longitude) AS longitude_max,
                COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) AS located_observation_rows,
                COUNT(DISTINCT (file_name, profile_number)) FILTER (
                    WHERE latitude BETWEEN 5 AND 25 AND longitude BETWEEN 55 AND 78
                ) AS arabian_sea_profiles,
                COUNT(DISTINCT (file_name, profile_number)) FILTER (
                    WHERE latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100
                ) AS bay_of_bengal_profiles,
                COUNT(DISTINCT (file_name, profile_number)) FILTER (
                    WHERE latitude BETWEEN -10 AND 10 AND longitude BETWEEN 60 AND 90
                ) AS equatorial_indian_ocean_profiles,
                COUNT(DISTINCT (file_name, profile_number)) FILTER (
                    WHERE latitude BETWEEN -60 AND -10 AND longitude BETWEEN 20 AND 120
                ) AS southern_indian_ocean_profiles,
                COUNT(DISTINCT (file_name, profile_number)) FILTER (
                    WHERE latitude BETWEEN -60 AND 30 AND longitude BETWEEN 20 AND 120
                ) AS indian_ocean_profiles
            FROM argo_profiles
            """
        )
        row = _rows(cursor)[0]
        for key in ("earliest_datetime", "latest_datetime"):
            timestamp = _utc_datetime(row[key])
            row[key] = timestamp.isoformat() if timestamp else None
        row["available_parameters"] = [
            name for name in PARAMETER_COLUMNS
            if row[f"{name}_rows"] > 0
        ]
        row["regional_profile_counts"] = {
            "Arabian Sea": row.pop("arabian_sea_profiles"),
            "Bay of Bengal": row.pop("bay_of_bengal_profiles"),
            "Equatorial Indian Ocean": row.pop("equatorial_indian_ocean_profiles"),
            "Southern Indian Ocean": row.pop("southern_indian_ocean_profiles"),
            "Indian Ocean": row.pop("indian_ocean_profiles"),
        }
        row["qc_available"] = False
        row["qc_note"] = "QC fields are not present in the processed DuckDB schema."
        row["float_identifier_note"] = (
            "float_id is the processed project key; the processed table does not retain a separate "
            "PLATFORM_NUMBER column, so raw WMO identity cannot be asserted independently."
        )
        return row

    def get_float_details(self, float_id: str) -> dict[str, Any] | None:
        """Return aggregate metadata for one exact project-level float_id."""
        if not isinstance(float_id, str) or not float_id.strip() or len(float_id) > 512:
            raise ValueError("A valid project float_id is required.")

        cursor = self._connection().execute(
            """
            SELECT
                float_id,
                COUNT(DISTINCT (file_name, profile_number)) AS profile_count,
                COUNT(DISTINCT file_name) AS source_file_count,
                COUNT(*) AS observation_count,
                COUNT(temperature) AS temperature_rows,
                COUNT(salinity) AS salinity_rows,
                COUNT(depth) AS depth_rows,
                CAST(MIN(datetime) AS VARCHAR) AS earliest_datetime,
                CAST(MAX(datetime) AS VARCHAR) AS latest_datetime,
                MIN(latitude) AS latitude_min,
                MAX(latitude) AS latitude_max,
                MIN(longitude) AS longitude_min,
                MAX(longitude) AS longitude_max
            FROM argo_profiles
            WHERE float_id = ?
            GROUP BY float_id
            """,
            [float_id.strip()],
        )
        rows = _rows(cursor)
        if not rows:
            return None

        row = rows[0]
        for key in ("earliest_datetime", "latest_datetime"):
            timestamp = _utc_datetime(row[key])
            row[key] = timestamp.isoformat() if timestamp else None
        row["available_parameters"] = {
            "temperature": row["temperature_rows"] > 0,
            "salinity": row["salinity_rows"] > 0,
            "depth": row["depth_rows"] > 0,
        }
        row["identifier_type"] = "project_float_id"
        row["platform_number_available"] = False
        row["qc_available"] = False
        row["limitations"] = [
            "The processed table does not retain a separate raw PLATFORM_NUMBER.",
            "QC fields are not present in the processed DuckDB schema.",
        ]
        return row

    @staticmethod
    def _filters(
        *,
        search: str | None = None,
        parameter: str | None = None,
        region: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        require_coordinates: bool = False,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
    ) -> tuple[list[str], list[Any], str | None]:
        clauses: list[str] = []
        params: list[Any] = []
        parameter_column: str | None = None

        if require_coordinates:
            clauses.extend(["latitude IS NOT NULL", "longitude IS NOT NULL"])

        coordinate_ranges = (
            ("latitude_min", latitude_min, -90.0, 90.0, "latitude"),
            ("latitude_max", latitude_max, -90.0, 90.0, "latitude"),
            ("longitude_min", longitude_min, -180.0, 180.0, "longitude"),
            ("longitude_max", longitude_max, -180.0, 180.0, "longitude"),
        )
        for name, value, minimum, maximum, column in coordinate_ranges:
            if value is not None:
                number = float(value)
                if not math.isfinite(number) or number < minimum or number > maximum:
                    raise ValueError(f"{name} must be between {minimum:g} and {maximum:g}.")
                operator = ">=" if name.endswith("_min") else "<="
                clauses.append(f"{column} {operator} ?")
                params.append(number)
        if latitude_min is not None and latitude_max is not None and float(latitude_min) > float(latitude_max):
            raise ValueError("latitude_min must be less than or equal to latitude_max.")
        if longitude_min is not None and longitude_max is not None and float(longitude_min) > float(longitude_max):
            raise ValueError("longitude_min must be less than or equal to longitude_max.")

        if search and search.strip():
            if len(search) > 256:
                raise ValueError("search must be 256 characters or fewer.")
            clauses.append(
                "(file_name ILIKE ? OR float_id ILIKE ? OR CAST(profile_number AS VARCHAR) ILIKE ?)"
            )
            value = f"%{search.strip()}%"
            params.extend([value, value, value])

        if parameter:
            normalized = parameter.strip().lower()
            if normalized not in PARAMETER_COLUMNS:
                raise ValueError(f"Unsupported parameter. Choose one of: {', '.join(PARAMETER_COLUMNS)}.")
            parameter_column = PARAMETER_COLUMNS[normalized]

        if region:
            if region not in REGION_BOUNDS:
                raise ValueError(f"Unsupported region: {region}.")
            bounds = REGION_BOUNDS[region]
            clauses.extend(
                [
                    "latitude BETWEEN ? AND ?",
                    "longitude BETWEEN ? AND ?",
                ]
            )
            params.extend([bounds["lat_min"], bounds["lat_max"], bounds["lon_min"], bounds["lon_max"]])

        start = _utc_datetime(start_datetime) if start_datetime else None
        end = _utc_datetime(end_datetime) if end_datetime else None
        if end and isinstance(end_datetime, str) and len(end_datetime.strip()) == 10:
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        if start and end and start > end:
            raise ValueError("start_datetime must be earlier than or equal to end_datetime.")
        if start:
            clauses.append("datetime >= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(start.isoformat())
        if end:
            clauses.append("datetime <= CAST(? AS TIMESTAMP WITH TIME ZONE)")
            params.append(end.isoformat())
        return clauses, params, parameter_column

    def list_profiles(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
        parameter: str | None = None,
        region: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
    ) -> dict[str, Any]:
        """Return a filtered profile page; profile identity is source file plus profile number."""
        page_size = min(max(int(limit), 1), MAX_PAGE_SIZE)
        page_offset = max(int(offset), 0)
        clauses, params, parameter_column = self._filters(
            search=search,
            parameter=parameter,
            region=region,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            require_coordinates=False,
            latitude_min=latitude_min,
            latitude_max=latitude_max,
            longitude_min=longitude_min,
            longitude_max=longitude_max,
        )
        sql = f"""
            WITH grouped AS (
                SELECT
                    file_name,
                    float_id,
                    profile_number,
                    cycle_number,
                    CAST(datetime AS VARCHAR) AS datetime,
                    latitude,
                    longitude,
                    COUNT(*) AS observation_count,
                    COUNT(temperature) AS temperature_count,
                    COUNT(salinity) AS salinity_count,
                    COUNT(depth) AS depth_count,
                    MIN(depth) AS min_pressure_or_depth,
                    MAX(depth) AS max_pressure_or_depth
                FROM argo_profiles
                {'WHERE ' + ' AND '.join(clauses) if clauses else ''}
                GROUP BY file_name, float_id, profile_number, cycle_number, datetime, latitude, longitude
                {f'HAVING COUNT({parameter_column}) > 0' if parameter_column else ''}
            )
            SELECT
                *,
                COUNT(*) OVER() AS total_count
            FROM grouped
            ORDER BY datetime DESC NULLS LAST, file_name, profile_number
            LIMIT ? OFFSET ?
        """
        rows = _rows(self._connection().execute(sql, [*params, page_size, page_offset]))
        total = rows[0]["total_count"] if rows else 0
        for row in rows:
            timestamp = _utc_datetime(row["datetime"])
            row["datetime"] = timestamp.isoformat() if timestamp else None
            row["profile_key"] = f"{row['file_name']}#profile={row['profile_number']}"
            row["available_parameters"] = {
                name: row[f"{name}_count"] > 0
                for name in PARAMETER_COLUMNS
            }
            row["qc_available"] = False
            row.pop("total_count", None)
        return {
            "results": rows,
            "total_count": total,
            "limit": page_size,
            "offset": page_offset,
        }

    def map_profiles(
        self,
        *,
        limit: int = 1000,
        region: str | None = None,
        search: str | None = None,
        parameter: str | None = None,
        start_datetime: str | None = None,
        end_datetime: str | None = None,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
    ) -> dict[str, Any]:
        """Return a bounded set of actual geolocated profiles for map markers."""
        map_limit = min(max(int(limit), 1), MAX_MAP_RESULTS)
        clauses, params, parameter_column = self._filters(
            search=search,
            parameter=parameter,
            region=region,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            require_coordinates=True,
            latitude_min=latitude_min,
            latitude_max=latitude_max,
            longitude_min=longitude_min,
            longitude_max=longitude_max,
        )
        sql = f"""
            SELECT
                file_name,
                float_id,
                profile_number,
                cycle_number,
                CAST(datetime AS VARCHAR) AS datetime,
                latitude,
                longitude,
                COUNT(*) AS observation_count,
                COUNT(temperature) AS temperature_count,
                COUNT(salinity) AS salinity_count,
                COUNT(depth) AS depth_count
            FROM argo_profiles
            WHERE {' AND '.join(clauses)}
            GROUP BY file_name, float_id, profile_number, cycle_number, datetime, latitude, longitude
            {f'HAVING COUNT({parameter_column}) > 0' if parameter_column else ''}
            ORDER BY datetime DESC NULLS LAST, file_name, profile_number
            LIMIT ?
        """
        rows = _rows(self._connection().execute(sql, [*params, map_limit]))
        for row in rows:
            timestamp = _utc_datetime(row["datetime"])
            row["datetime"] = timestamp.isoformat() if timestamp else None
            row["profile_key"] = f"{row['file_name']}#profile={row['profile_number']}"
            row["available_parameters"] = {
                name: row[f"{name}_count"] > 0
                for name in PARAMETER_COLUMNS
            }
        return {"results": rows, "returned_count": len(rows), "limit": map_limit}

    def get_profile(
        self,
        file_name: str,
        profile_number: int,
        *,
        limit: int = 5000,
    ) -> dict[str, Any] | None:
        """Return one profile's actual measurements, bounded to 10,000 levels."""
        if not file_name or len(file_name) > 512:
            raise ValueError("A valid source file name is required.")
        if int(profile_number) < 1:
            raise ValueError("profile_number must be a positive integer.")
        level_limit = min(max(int(limit), 1), MAX_PROFILE_LEVELS)
        cursor = self._connection().execute(
            """
            SELECT
                file_name,
                float_id,
                profile_number,
                cycle_number,
                CAST(datetime AS VARCHAR) AS datetime,
                latitude,
                longitude,
                depth,
                temperature,
                salinity,
                COUNT(*) OVER() AS total_observation_count
            FROM argo_profiles
            WHERE file_name = ? AND profile_number = ?
            ORDER BY depth ASC NULLS LAST
            LIMIT ?
            """,
            [file_name, int(profile_number), level_limit],
        )
        measurements = _rows(cursor)
        if not measurements:
            return None
        total_observation_count = measurements[0]["total_observation_count"]
        for row in measurements:
            row.pop("total_observation_count", None)
        measurements = measurements[:level_limit]
        for row in measurements:
            timestamp = _utc_datetime(row["datetime"])
            row["datetime"] = timestamp.isoformat() if timestamp else None
        first = measurements[0]
        params = {
            name: any(row.get(name) is not None for row in measurements)
            for name in PARAMETER_COLUMNS
        }
        return {
            "profile_key": f"{file_name}#profile={profile_number}",
            "file_name": first["file_name"],
            "float_id": first["float_id"],
            "profile_number": first["profile_number"],
            "cycle_number": first["cycle_number"],
            "datetime": first["datetime"],
            "latitude": first["latitude"],
            "longitude": first["longitude"],
            "observation_count": total_observation_count,
            "returned_measurement_count": len(measurements),
            "available_parameters": params,
            "qc_available": False,
            "qc_note": "QC fields are not present in the processed DuckDB schema.",
            "measurements": measurements,
            "truncated": total_observation_count > level_limit,
        }


_service: ProfileExplorerService | None = None


def get_profile_explorer_service() -> ProfileExplorerService:
    """Return the module-level profile explorer singleton."""
    global _service
    if _service is None:
        _service = ProfileExplorerService()
    return _service
