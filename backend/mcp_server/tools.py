"""Validated read-only MCP tool handlers backed by ProfileExplorerService."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
import logging
import math
import threading
from typing import Any, Literal

from mcp.server.mcpserver.exceptions import ToolError

from services.profile_explorer_service import ProfileExplorerService

from .schemas import (
    CompareProfilesResponse,
    ComparisonPoint,
    DatasetSummaryResponse,
    FloatDetailsResponse,
    Observation,
    ProfileComparison,
    ProfileObservationsResponse,
    ProfileSummary,
    SearchProfilesResponse,
)

logger = logging.getLogger(__name__)

SUPPORTED_REGIONS = (
    "Arabian Sea",
    "Bay of Bengal",
    "Equatorial Indian Ocean",
    "Southern Indian Ocean",
    "Indian Ocean",
)
SUPPORTED_PARAMETERS = ("temperature", "salinity", "depth")
MAX_PROFILE_SEARCH_RESULTS = 200
MAX_OBSERVATION_RESULTS = 2000
MAX_COMPARISON_PROFILES = 4
MAX_COMPARISON_LEVELS = 2000
_NOTES = [
    "float_id is a project-level identifier; profile identity is source_file plus profile_number.",
    "The processed DuckDB data does not retain raw NetCDF PLATFORM_NUMBER as a separate field.",
    "QC fields are not present in the processed DuckDB schema.",
]


def _utc_datetime(value: str, *, end_of_date: bool = False) -> datetime:
    """Parse an ISO date/time and interpret date-only values as UTC days."""
    try:
        if not isinstance(value, str) or not value.strip():
            raise ValueError
        text = value.strip()
        if len(text) == 10:
            parsed_date = date.fromisoformat(text)
            parsed = datetime.combine(
                parsed_date,
                time.max if end_of_date else time.min,
                tzinfo=timezone.utc,
            )
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
        return parsed
    except (TypeError, ValueError, OverflowError) as exc:
        raise ToolError("Dates must be valid ISO-8601 dates or timestamps.") from exc


def _validate_date_range(start_date: str | None, end_date: str | None) -> None:
    start = _utc_datetime(start_date) if start_date is not None else None
    end = _utc_datetime(end_date, end_of_date=True) if end_date is not None else None
    if start is not None and end is not None and start > end:
        raise ToolError("start_date must be earlier than or equal to end_date.")


def _validate_coordinate(name: str, value: float | None, minimum: float, maximum: float) -> None:
    if value is None:
        return
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not minimum <= value <= maximum
    ):
        raise ToolError(f"{name} must be between {minimum:g} and {maximum:g}.")


def _profile_identity(profile_id: str) -> tuple[str, int]:
    if not isinstance(profile_id, str) or len(profile_id) > 600:
        raise ToolError("profile_id must be a source file and positive profile number.")
    file_name, separator, profile_text = profile_id.rpartition("#profile=")
    if (
        not separator
        or not file_name
        or "/" in file_name
        or "\\" in file_name
        or len(file_name) > 512
        or not profile_text.isdecimal()
        or int(profile_text) < 1
    ):
        raise ToolError("profile_id must use the form <source_file>#profile=<positive_number>.")
    return file_name, int(profile_text)


def _validate_pressure(pressure_min_dbar: float | None, pressure_max_dbar: float | None) -> None:
    for label, value in (
        ("pressure_min_dbar", pressure_min_dbar),
        ("pressure_max_dbar", pressure_max_dbar),
    ):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ToolError(f"{label} must be a finite non-negative number.")
    if (
        pressure_min_dbar is not None
        and pressure_max_dbar is not None
        and pressure_min_dbar > pressure_max_dbar
    ):
        raise ToolError("pressure_min_dbar must not exceed pressure_max_dbar.")


class OceanIQMCPTools:
    """Run bounded, parameterized read-only operations through a shared service."""

    def __init__(self, service: ProfileExplorerService | None = None) -> None:
        self._service = service or ProfileExplorerService()
        self._lock = threading.RLock()

    def _invoke(self, operation: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            with self._lock:
                return operation(*args, **kwargs)
        except ToolError:
            raise
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            logger.error("OceanIQ MCP operation failed (%s)", type(exc).__name__)
            raise ToolError("OceanIQ data service failed; retry the request later.") from None

    def search_argo_profiles(
        self,
        parameter: str | None = None,
        region: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
        search: str | None = None,
        limit: int = 50,
    ) -> SearchProfilesResponse:
        """Find a bounded page of profiles using supported metadata filters."""
        if parameter is not None and parameter not in SUPPORTED_PARAMETERS:
            raise ToolError(f"parameter must be one of: {', '.join(SUPPORTED_PARAMETERS)}.")
        if region is not None and region not in SUPPORTED_REGIONS:
            raise ToolError(f"region must be one of: {', '.join(SUPPORTED_REGIONS)}.")
        if type(limit) is not int or not 1 <= limit <= MAX_PROFILE_SEARCH_RESULTS:
            raise ToolError(f"limit must be an integer between 1 and {MAX_PROFILE_SEARCH_RESULTS}.")
        if search is not None and (
            not isinstance(search, str) or not search.strip() or len(search) > 512
        ):
            raise ToolError("search must contain between 1 and 512 non-whitespace characters.")
        for name, value, minimum, maximum in (
            ("latitude_min", latitude_min, -90, 90),
            ("latitude_max", latitude_max, -90, 90),
            ("longitude_min", longitude_min, -180, 180),
            ("longitude_max", longitude_max, -180, 180),
        ):
            _validate_coordinate(name, value, minimum, maximum)
        if latitude_min is not None and latitude_max is not None and latitude_min > latitude_max:
            raise ToolError("latitude_min must not exceed latitude_max.")
        if longitude_min is not None and longitude_max is not None and longitude_min > longitude_max:
            raise ToolError("longitude_min must not exceed longitude_max.")
        _validate_date_range(start_date, end_date)

        page = self._invoke(
            self._service.list_profiles,
            limit=limit,
            offset=0,
            parameter=parameter,
            region=region,
            start_datetime=start_date,
            end_datetime=end_date,
            latitude_min=latitude_min,
            latitude_max=latitude_max,
            longitude_min=longitude_min,
            longitude_max=longitude_max,
            search=search,
        )
        profiles = [
            ProfileSummary(
                profile_id=row["profile_key"],
                source_file=row["file_name"],
                float_id=row["float_id"],
                profile_number=row["profile_number"],
                cycle_number=row["cycle_number"],
                datetime_utc=row["datetime"],
                latitude=row["latitude"],
                longitude=row["longitude"],
                observation_count=row["observation_count"],
                available_parameters=row["available_parameters"],
                qc_available=row["qc_available"],
            )
            for row in page["results"]
        ]
        applied = {
            key: value
            for key, value in {
                "parameter": parameter,
                "region": region,
                "start_date": start_date,
                "end_date": end_date,
                "latitude_min": latitude_min,
                "latitude_max": latitude_max,
                "longitude_min": longitude_min,
                "longitude_max": longitude_max,
                "search": search,
            }.items()
            if value is not None
        }
        return SearchProfilesResponse(
            status="success" if profiles else "success_empty",
            filters_applied=applied,
            matched_profile_count=page["total_count"],
            returned_count=len(profiles),
            limit=page["limit"],
            profiles=profiles,
            limitations=_NOTES.copy(),
        )

    def get_float_details(self, float_id: str) -> FloatDetailsResponse:
        """Get aggregates for an exact project-level `float_id`."""
        if not isinstance(float_id, str) or not float_id.strip() or len(float_id) > 512:
            raise ToolError("A valid project float_id is required.")
        details = self._invoke(self._service.get_float_details, float_id)
        if details is None:
            return FloatDetailsResponse(
                status="not_found",
                float_id=float_id,
                identifier_type="project_float_id",
                message="No matching project float_id was found.",
                limitations=_NOTES.copy(),
            )
        return FloatDetailsResponse(
            status="success",
            float_id=details["float_id"],
            identifier_type="project_float_id",
            profile_count=details["profile_count"],
            source_file_count=details["source_file_count"],
            observation_count=details["observation_count"],
            temperature_rows=details["temperature_rows"],
            salinity_rows=details["salinity_rows"],
            depth_rows=details["depth_rows"],
            earliest_datetime_utc=details["earliest_datetime"],
            latest_datetime_utc=details["latest_datetime"],
            latitude_min=details["latitude_min"],
            latitude_max=details["latitude_max"],
            longitude_min=details["longitude_min"],
            longitude_max=details["longitude_max"],
            available_parameters=details["available_parameters"],
            platform_number_available=details["platform_number_available"],
            qc_available=details["qc_available"],
            limitations=details["limitations"],
        )

    def get_profile_observations(
        self,
        profile_id: str,
        parameters: list[str] | None = None,
        pressure_min_dbar: float | None = None,
        pressure_max_dbar: float | None = None,
        limit: int = 500,
    ) -> ProfileObservationsResponse:
        """Return actual measurement levels from one file/profile identity."""
        file_name, profile_number = _profile_identity(profile_id)
        if type(limit) is not int or not 1 <= limit <= MAX_OBSERVATION_RESULTS:
            raise ToolError(f"limit must be an integer between 1 and {MAX_OBSERVATION_RESULTS}.")
        _validate_pressure(pressure_min_dbar, pressure_max_dbar)
        selected = parameters if parameters is not None else list(SUPPORTED_PARAMETERS)
        if not isinstance(selected, list) or not selected or any(
            not isinstance(item, str) or item not in SUPPORTED_PARAMETERS for item in selected
        ):
            raise ToolError(f"parameters must contain values from: {', '.join(SUPPORTED_PARAMETERS)}.")
        if len(set(selected)) != len(selected):
            raise ToolError("parameters must not contain duplicates.")

        detail = self._invoke(self._service.get_profile, file_name, profile_number, limit=10000)
        pressure_filter = {
            "minimum": pressure_min_dbar,
            "maximum": pressure_max_dbar,
        }
        if detail is None:
            return ProfileObservationsResponse(
                status="not_found",
                profile_id=profile_id,
                parameters_requested=selected,
                pressure_filter_dbar=pressure_filter,
                limitations=_NOTES.copy(),
            )

        filtered = [
            row
            for row in detail["measurements"]
            if (pressure_min_dbar is None or (
                row["depth"] is not None and row["depth"] >= pressure_min_dbar
            ))
            and (pressure_max_dbar is None or (
                row["depth"] is not None and row["depth"] <= pressure_max_dbar
            ))
        ]
        returned = filtered[:limit]
        observations = [
            Observation(
                depth=row["depth"],
                temperature=row["temperature"] if "temperature" in selected else None,
                salinity=row["salinity"] if "salinity" in selected else None,
            )
            for row in returned
        ]
        truncated = detail["truncated"] or len(filtered) > limit
        return ProfileObservationsResponse(
            status="success" if observations else "success_empty",
            profile_id=detail["profile_key"],
            source_file=detail["file_name"],
            float_id=detail["float_id"],
            profile_number=detail["profile_number"],
            cycle_number=detail["cycle_number"],
            datetime_utc=detail["datetime"],
            latitude=detail["latitude"],
            longitude=detail["longitude"],
            total_observation_count=detail["observation_count"],
            returned_count=len(observations),
            truncated=truncated,
            parameters_requested=selected,
            pressure_filter_dbar=pressure_filter,
            available_parameters=detail["available_parameters"],
            qc_available=detail["qc_available"],
            measurements=observations,
            limitations=_NOTES.copy() + [
                "The stored `depth` field comes from NetCDF PRES and is treated as pressure in dbar."
            ],
        )

    def compare_profiles(
        self,
        profile_ids: list[str],
        parameter: Literal["temperature", "salinity"],
        pressure_min_dbar: float | None = None,
        pressure_max_dbar: float | None = None,
    ) -> CompareProfilesResponse:
        """Return separate observed series; no interpolation or profile merging occurs."""
        if not isinstance(profile_ids, list) or not 2 <= len(profile_ids) <= MAX_COMPARISON_PROFILES:
            raise ToolError(f"profile_ids must contain between 2 and {MAX_COMPARISON_PROFILES} IDs.")
        if any(not isinstance(profile_id, str) for profile_id in profile_ids):
            raise ToolError("Every profile_id must be a string.")
        if len(set(profile_ids)) != len(profile_ids):
            raise ToolError("profile_ids must be unique.")
        if parameter not in ("temperature", "salinity"):
            raise ToolError("parameter must be either temperature or salinity.")
        _validate_pressure(pressure_min_dbar, pressure_max_dbar)

        profiles: list[ProfileComparison] = []
        missing: list[str] = []
        incomplete: list[str] = []
        for profile_id in profile_ids:
            file_name, profile_number = _profile_identity(profile_id)
            detail = self._invoke(self._service.get_profile, file_name, profile_number, limit=10000)
            if detail is None:
                missing.append(profile_id)
                continue
            selected = [
                row
                for row in detail["measurements"]
                if row["depth"] is not None
                and row[parameter] is not None
                and (pressure_min_dbar is None or row["depth"] >= pressure_min_dbar)
                and (pressure_max_dbar is None or row["depth"] <= pressure_max_dbar)
            ]
            note = None
            if not selected:
                note = f"No {parameter} values are available in the requested pressure range."
                incomplete.append(profile_id)
            elif detail["truncated"]:
                note = "The source profile contains more observations than the retrieval bound."
                incomplete.append(profile_id)
            elif len(selected) > MAX_COMPARISON_LEVELS:
                note = "The returned comparison series is limited to 2,000 observed levels."
                incomplete.append(profile_id)
            profiles.append(
                ProfileComparison(
                    profile_id=detail["profile_key"],
                    source_file=detail["file_name"],
                    float_id=detail["float_id"],
                    profile_number=detail["profile_number"],
                    available_parameters=detail["available_parameters"],
                    points=[
                        ComparisonPoint(pressure_dbar=row["depth"], value=row[parameter])
                        for row in selected[:MAX_COMPARISON_LEVELS]
                    ],
                    note=note,
                )
            )
        units = (
            "degrees_Celsius"
            if parameter == "temperature"
            else "practical_salinity_units"
        )
        if not profiles:
            status: Literal["success", "partial", "not_found"] = "not_found"
        elif missing or incomplete:
            status = "partial"
        else:
            status = "success"
        return CompareProfilesResponse(
            status=status,
            parameter=parameter,
            units=units,
            requested_profile_ids=profile_ids,
            profiles=profiles,
            missing_profile_ids=missing,
            incomplete_profile_ids=incomplete,
            pressure_filter_dbar={
                "minimum": pressure_min_dbar,
                "maximum": pressure_max_dbar,
            },
            limitations=_NOTES.copy() + [
                "Profiles are returned as independent observed series; values are not interpolated or aligned."
            ],
        )

    def get_dataset_summary(self) -> DatasetSummaryResponse:
        """Return the existing dataset summary and its known data limitations."""
        summary = self._invoke(self._service.get_summary)
        return DatasetSummaryResponse(
            status="success",
            observation_rows=summary["observation_rows"],
            profile_count=summary["profile_count"],
            project_float_count=summary["project_float_count"],
            source_file_count=summary["source_file_count"],
            temperature_rows=summary["temperature_rows"],
            salinity_rows=summary["salinity_rows"],
            depth_rows=summary["depth_rows"],
            earliest_datetime_utc=summary["earliest_datetime"],
            latest_datetime_utc=summary["latest_datetime"],
            latitude_min=summary["latitude_min"],
            latitude_max=summary["latitude_max"],
            longitude_min=summary["longitude_min"],
            longitude_max=summary["longitude_max"],
            located_observation_rows=summary["located_observation_rows"],
            regional_profile_counts=summary["regional_profile_counts"],
            available_parameters=summary["available_parameters"],
            platform_number_available=False,
            qc_available=summary["qc_available"],
            limitations=[
                summary["float_identifier_note"],
                summary["qc_note"],
            ],
        )
