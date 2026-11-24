"""Structured, bounded response models for OceanIQ MCP tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MCPResponse(BaseModel):
    """Base class that rejects accidental response fields."""

    model_config = ConfigDict(extra="forbid")


class ProfileSummary(MCPResponse):
    """Profile metadata; profile identity is source file plus profile number."""

    profile_id: str
    source_file: str
    float_id: str
    profile_number: int
    cycle_number: int | None
    datetime_utc: str | None
    latitude: float | None
    longitude: float | None
    observation_count: int
    available_parameters: dict[str, bool]
    qc_available: bool


class SearchProfilesResponse(MCPResponse):
    """A bounded page of profiles matching the actual filters applied."""

    status: Literal["success", "success_empty"]
    filters_applied: dict[str, Any]
    matched_profile_count: int
    returned_count: int
    limit: int
    profiles: list[ProfileSummary]
    limitations: list[str] = Field(default_factory=list)


class FloatDetailsResponse(MCPResponse):
    """Aggregates for an exact project-level float identifier."""

    status: Literal["success", "not_found"]
    float_id: str
    identifier_type: Literal["project_float_id"]
    profile_count: int | None = None
    source_file_count: int | None = None
    observation_count: int | None = None
    temperature_rows: int | None = None
    salinity_rows: int | None = None
    depth_rows: int | None = None
    earliest_datetime_utc: str | None = None
    latest_datetime_utc: str | None = None
    latitude_min: float | None = None
    latitude_max: float | None = None
    longitude_min: float | None = None
    longitude_max: float | None = None
    available_parameters: dict[str, bool] = Field(default_factory=dict)
    platform_number_available: bool = False
    qc_available: bool = False
    message: str | None = None
    limitations: list[str] = Field(default_factory=list)


class Observation(MCPResponse):
    """One stored measurement level; `depth` is sourced from NetCDF PRES."""

    depth: float | None
    temperature: float | None
    salinity: float | None


class ProfileObservationsResponse(MCPResponse):
    """Observed levels from a single source-file/profile-number identity."""

    status: Literal["success", "success_empty", "not_found"]
    profile_id: str
    source_file: str | None = None
    float_id: str | None = None
    profile_number: int | None = None
    cycle_number: int | None = None
    datetime_utc: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    total_observation_count: int = 0
    returned_count: int = 0
    truncated: bool = False
    parameters_requested: list[str]
    pressure_filter_dbar: dict[str, float | None]
    available_parameters: dict[str, bool] = Field(default_factory=dict)
    qc_available: bool = False
    measurements: list[Observation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ComparisonPoint(MCPResponse):
    """One actual pressure/value pair, without interpolation."""

    pressure_dbar: float
    value: float


class ProfileComparison(MCPResponse):
    """Actual observed values for one profile and one selected parameter."""

    profile_id: str
    source_file: str
    float_id: str | None
    profile_number: int
    available_parameters: dict[str, bool]
    points: list[ComparisonPoint]
    note: str | None = None


class CompareProfilesResponse(MCPResponse):
    """Independent observed series for a bounded set of profile identifiers."""

    status: Literal["success", "partial", "not_found"]
    parameter: Literal["temperature", "salinity"]
    units: Literal["degrees_Celsius", "practical_salinity_units"]
    requested_profile_ids: list[str]
    profiles: list[ProfileComparison]
    missing_profile_ids: list[str] = Field(default_factory=list)
    incomplete_profile_ids: list[str] = Field(default_factory=list)
    interpolation: Literal["none"] = "none"
    pressure_filter_dbar: dict[str, float | None]
    limitations: list[str] = Field(default_factory=list)


class DatasetSummaryResponse(MCPResponse):
    """Dataset-level profile, observation, coverage and limitation summary."""

    status: Literal["success"]
    observation_rows: int
    profile_count: int
    project_float_count: int
    source_file_count: int
    temperature_rows: int
    salinity_rows: int
    depth_rows: int
    earliest_datetime_utc: str | None
    latest_datetime_utc: str | None
    latitude_min: float | None
    latitude_max: float | None
    longitude_min: float | None
    longitude_max: float | None
    located_observation_rows: int
    regional_profile_counts: dict[str, int]
    available_parameters: list[str]
    platform_number_available: bool
    qc_available: bool
    limitations: list[str]
