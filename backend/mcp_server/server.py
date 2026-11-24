"""Independently runnable read-only OceanIQ MCP server using stdio transport."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from mcp_server.tools import (  # noqa: E402
    MAX_COMPARISON_PROFILES,
    MAX_OBSERVATION_RESULTS,
    MAX_PROFILE_SEARCH_RESULTS,
    OceanIQMCPTools,
)
from mcp_server.schemas import (  # noqa: E402
    CompareProfilesResponse,
    DatasetSummaryResponse,
    FloatDetailsResponse,
    ProfileObservationsResponse,
    SearchProfilesResponse,
)
from services.profile_explorer_service import (  # noqa: E402
    ProfileExplorerService,
    get_profile_explorer_service,
)


def create_server(
    tools: OceanIQMCPTools | None = None,
    service: ProfileExplorerService | None = None,
) -> MCPServer:
    """Create the MCP server with one shared read-only profile service instance."""
    handlers = tools or OceanIQMCPTools(service or get_profile_explorer_service())
    server = MCPServer(
        name="OceanIQ",
        version="1.0.0",
        description="Read-only access to processed OceanIQ ARGO profile data.",
    )
    annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.tool(
        description="Search a bounded page of profiles by supported parameter, region, date, and coordinate filters.",
        annotations=annotations,
    )
    def search_argo_profiles(
        parameter: Literal["temperature", "salinity", "depth"] | None = None,
        region: Literal[
            "Arabian Sea",
            "Bay of Bengal",
            "Equatorial Indian Ocean",
            "Southern Indian Ocean",
            "Indian Ocean",
        ] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        latitude_min: float | None = None,
        latitude_max: float | None = None,
        longitude_min: float | None = None,
        longitude_max: float | None = None,
        search: str | None = None,
        limit: int = Field(default=50, ge=1, le=MAX_PROFILE_SEARCH_RESULTS),
    ) -> SearchProfilesResponse:
        return handlers.search_argo_profiles(
            parameter=parameter,
            region=region,
            start_date=start_date,
            end_date=end_date,
            latitude_min=latitude_min,
            latitude_max=latitude_max,
            longitude_min=longitude_min,
            longitude_max=longitude_max,
            search=search,
            limit=limit,
        )

    @server.tool(
        description="Get aggregate profile, date, location, and parameter details for an exact project float_id.",
        annotations=annotations,
    )
    def get_float_details(float_id: str) -> FloatDetailsResponse:
        return handlers.get_float_details(float_id)

    @server.tool(
        description="Get actual stored observations for a source-file/profile-number ID, optionally filtered by pressure.",
        annotations=annotations,
    )
    def get_profile_observations(
        profile_id: str,
        parameters: list[Literal["temperature", "salinity", "depth"]] | None = None,
        pressure_min_dbar: float | None = None,
        pressure_max_dbar: float | None = None,
        limit: int = Field(default=500, ge=1, le=MAX_OBSERVATION_RESULTS),
    ) -> ProfileObservationsResponse:
        return handlers.get_profile_observations(
            profile_id=profile_id,
            parameters=parameters,
            pressure_min_dbar=pressure_min_dbar,
            pressure_max_dbar=pressure_max_dbar,
            limit=limit,
        )

    @server.tool(
        description="Compare actual temperature or salinity series from 2–4 profiles; no interpolation is performed.",
        annotations=annotations,
    )
    def compare_profiles(
        profile_ids: list[str] = Field(min_length=2, max_length=MAX_COMPARISON_PROFILES),
        parameter: Literal["temperature", "salinity"] = "temperature",
        pressure_min_dbar: float | None = None,
        pressure_max_dbar: float | None = None,
    ) -> CompareProfilesResponse:
        return handlers.compare_profiles(
            profile_ids=profile_ids,
            parameter=parameter,
            pressure_min_dbar=pressure_min_dbar,
            pressure_max_dbar=pressure_max_dbar,
        )

    @server.tool(
        description="Return dataset coverage, profile/float/file counts, available parameters, and known limitations.",
        annotations=annotations,
    )
    def get_dataset_summary() -> DatasetSummaryResponse:
        return handlers.get_dataset_summary()

    return server


def main() -> None:
    """Run the MCP server over stdio for desktop MCP clients."""
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
