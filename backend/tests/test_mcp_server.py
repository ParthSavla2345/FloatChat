from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys

import duckdb
from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from mcp_server.server import create_server
from mcp_server.tools import OceanIQMCPTools
from services.profile_explorer_service import ProfileExplorerService


class InMemoryDatabase:
    def __init__(self) -> None:
        self._con = duckdb.connect(":memory:")
        self._con.execute(
            """
            CREATE TABLE argo_profiles (
                file_name VARCHAR,
                float_id VARCHAR,
                profile_number INTEGER,
                cycle_number INTEGER,
                datetime TIMESTAMPTZ,
                latitude DOUBLE,
                longitude DOUBLE,
                depth DOUBLE,
                temperature DOUBLE,
                salinity DOUBLE
            )
            """
        )
        self._con.executemany(
            "INSERT INTO argo_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("argo_a.nc", "project-float-1", 1, 10, "2023-01-02T00:00:00Z", 10.0, 70.0, 5.0, 28.1, 35.0),
                ("argo_a.nc", "project-float-1", 1, 10, "2023-01-02T00:00:00Z", 10.0, 70.0, 20.0, 27.0, 35.1),
                ("argo_b.nc", "project-float-2", 1, 2, "2023-02-03T00:00:00Z", -15.0, 90.0, 10.0, None, 34.8),
            ],
        )

    def _connect(self) -> None:
        return None


@pytest.fixture
def profile_service():
    database = InMemoryDatabase()
    yield ProfileExplorerService(database)
    database._con.close()


def test_search_tool_applies_supported_filters_and_preserves_identity(profile_service):
    result = OceanIQMCPTools(profile_service).search_argo_profiles(
        parameter="temperature",
        region="Arabian Sea",
        limit=10,
    )

    assert result.status == "success"
    assert result.matched_profile_count == 1
    profile = result.profiles[0]
    assert profile.profile_id == "argo_a.nc#profile=1"
    assert profile.source_file == "argo_a.nc"
    assert profile.float_id == "project-float-1"
    assert profile.available_parameters["temperature"] is True


def test_search_tool_reports_empty_results_without_fabrication(profile_service):
    result = OceanIQMCPTools(profile_service).search_argo_profiles(
        parameter="temperature",
        region="Bay of Bengal",
    )

    assert result.status == "success_empty"
    assert result.matched_profile_count == 0
    assert result.profiles == []


def test_float_details_are_exact_project_float_aggregates(profile_service):
    tools = OceanIQMCPTools(profile_service)

    result = tools.get_float_details("project-float-1")
    missing = tools.get_float_details("argo_a.nc")

    assert result.status == "success"
    assert result.identifier_type == "project_float_id"
    assert result.profile_count == 1
    assert result.observation_count == 2
    assert result.platform_number_available is False
    assert missing.status == "not_found"


def test_profile_observations_are_bounded_and_pressure_filtered(profile_service):
    result = OceanIQMCPTools(profile_service).get_profile_observations(
        "argo_a.nc#profile=1",
        parameters=["temperature"],
        pressure_min_dbar=10,
        pressure_max_dbar=20,
    )

    assert result.status == "success"
    assert result.returned_count == 1
    assert result.measurements[0].depth == 20.0
    assert result.measurements[0].temperature == 27.0
    assert result.measurements[0].salinity is None


def test_profile_comparison_returns_separate_observed_series(profile_service):
    result = OceanIQMCPTools(profile_service).compare_profiles(
        ["argo_a.nc#profile=1", "argo_b.nc#profile=1"],
        parameter="temperature",
    )

    assert result.status == "partial"
    assert result.interpolation == "none"
    assert result.profiles[0].points[0].pressure_dbar == 5.0
    assert result.profiles[0].points[0].value == pytest.approx(28.1)
    assert result.incomplete_profile_ids == ["argo_b.nc#profile=1"]


def test_summary_tool_uses_existing_dataset_summary(profile_service):
    result = OceanIQMCPTools(profile_service).get_dataset_summary()

    assert result.status == "success"
    assert result.profile_count == 2
    assert result.project_float_count == 2
    assert result.platform_number_available is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"latitude_min": -91}, "latitude_min"),
        ({"start_date": "2023-02-01", "end_date": "2023-01-01"}, "start_date"),
        ({"start_date": "not-a-date"}, "ISO-8601"),
        ({"parameter": "oxygen"}, "parameter"),
        ({"region": "Unknown Sea"}, "region"),
        ({"limit": 201}, "limit"),
    ],
)
def test_search_rejects_invalid_constraints(profile_service, kwargs, message):
    with pytest.raises(ToolError, match=message):
        OceanIQMCPTools(profile_service).search_argo_profiles(**kwargs)


def test_observation_and_comparison_reject_invalid_profile_or_pressure(profile_service):
    tools = OceanIQMCPTools(profile_service)

    with pytest.raises(ToolError, match="profile_id"):
        tools.get_profile_observations("argo_a.nc")
    with pytest.raises(ToolError, match="must not exceed"):
        tools.get_profile_observations(
            "argo_a.nc#profile=1",
            pressure_min_dbar=20,
            pressure_max_dbar=10,
        )
    with pytest.raises(ToolError, match="must contain between"):
        tools.compare_profiles(["argo_a.nc#profile=1"], parameter="temperature")
    with pytest.raises(ToolError, match="integer"):
        tools.search_argo_profiles(limit=1.5)
    with pytest.raises(ToolError, match="finite"):
        tools.get_profile_observations("argo_a.nc#profile=1", pressure_min_dbar="bad")


def test_service_failures_are_reported_without_internal_details(profile_service):
    class BrokenService(ProfileExplorerService):
        def list_profiles(self, **kwargs):
            raise RuntimeError("database path and credentials must not be exposed")

    tools = OceanIQMCPTools(BrokenService(profile_service.db_service))

    with pytest.raises(ToolError, match="data service failed") as error:
        tools.search_argo_profiles()
    assert "credentials" not in str(error.value)


def test_all_tools_are_discoverable_and_callable_over_in_process_mcp_protocol(profile_service):
    server = create_server(service=profile_service)

    async def exercise_protocol():
        async with Client(server) as client:
            tool_names = {item.name for item in (await client.list_tools()).tools}
            assert tool_names == {
                "search_argo_profiles",
                "get_float_details",
                "get_profile_observations",
                "compare_profiles",
                "get_dataset_summary",
            }
            calls = [
                ("search_argo_profiles", {"region": "Arabian Sea", "limit": 10}),
                ("get_float_details", {"float_id": "project-float-1"}),
                ("get_profile_observations", {"profile_id": "argo_a.nc#profile=1"}),
                (
                    "compare_profiles",
                    {
                        "profile_ids": ["argo_a.nc#profile=1", "argo_b.nc#profile=1"],
                        "parameter": "temperature",
                    },
                ),
                ("get_dataset_summary", {}),
            ]
            for name, arguments in calls:
                result = await client.call_tool(name, arguments)
                assert result.is_error is False
                assert result.structured_content is not None
                assert result.structured_content["status"] in (
                    "success",
                    "success_empty",
                    "partial",
                )
            search_result = await client.call_tool(
                "search_argo_profiles",
                {"region": "Arabian Sea", "limit": 1},
            )
            assert (
                search_result.structured_content["profiles"][0]["profile_id"]
                == "argo_a.nc#profile=1"
            )
            rejected = await client.call_tool(
                "search_argo_profiles",
                {"parameter": "oxygen"},
            )
            assert rejected.is_error is True
            malformed_profile = await client.call_tool(
                "get_profile_observations",
                {"profile_id": "argo_a.nc"},
            )
            assert malformed_profile.is_error is True

    asyncio.run(exercise_protocol())


def test_stdio_server_starts_and_lists_tools():
    environment = os.environ.copy()
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(BACKEND_ROOT),
        env=environment,
    )

    async def exercise_stdio():
        async with Client(parameters) as client:
            names = {item.name for item in (await client.list_tools()).tools}
            assert len(names) == 5
            assert "get_dataset_summary" in names

    asyncio.run(exercise_stdio())
