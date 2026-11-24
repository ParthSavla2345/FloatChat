from __future__ import annotations

from pathlib import Path
import sys

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
            """
            INSERT INTO argo_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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


def test_summary_distinguishes_profiles_observations_and_float_ids(profile_service):
    summary = profile_service.get_summary()

    assert summary["observation_rows"] == 3
    assert summary["profile_count"] == 2
    assert summary["project_float_count"] == 2
    assert summary["available_parameters"] == ["temperature", "salinity", "depth"]
    assert summary["regional_profile_counts"]["Arabian Sea"] == 1
    assert summary["regional_profile_counts"]["Bay of Bengal"] == 0
    assert summary["qc_available"] is False
    assert summary["earliest_datetime"] == "2023-01-02T00:00:00+00:00"

def test_float_details_use_exact_project_identifier_and_return_actual_aggregates(profile_service):
    details = profile_service.get_float_details("project-float-1")

    assert details is not None
    assert details["identifier_type"] == "project_float_id"
    assert details["profile_count"] == 1
    assert details["observation_count"] == 2
    assert details["available_parameters"] == {
        "temperature": True,
        "salinity": True,
        "depth": True,
    }
    assert details["platform_number_available"] is False
    assert profile_service.get_float_details("missing-float") is None


def test_profile_list_groups_measurement_levels_and_paginates(profile_service):
    page = profile_service.list_profiles(limit=1, offset=0, region="Arabian Sea")

    assert page["total_count"] == 1
    assert page["results"][0]["file_name"] == "argo_a.nc"
    assert page["results"][0]["observation_count"] == 2
    assert page["results"][0]["available_parameters"]["temperature"] is True


def test_profile_filter_searches_parameters_and_regions(profile_service):
    page = profile_service.list_profiles(search="project-float-2", parameter="salinity")

    assert page["total_count"] == 1
    assert page["results"][0]["profile_number"] == 1
    assert page["results"][0]["available_parameters"]["temperature"] is False


def test_profile_detail_returns_actual_measurements_and_not_found(profile_service):
    detail = profile_service.get_profile("argo_a.nc", 1)

    assert detail is not None
    assert detail["observation_count"] == 2
    assert detail["measurements"][0]["temperature"] == pytest.approx(28.1)
    assert detail["measurements"][1]["depth"] == pytest.approx(20.0)
    assert detail["qc_available"] is False
    assert profile_service.get_profile("missing.nc", 1) is None


def test_map_data_uses_actual_coordinates_and_limits(profile_service):
    result = profile_service.map_profiles(region="Arabian Sea", limit=1)
    coordinate_result = profile_service.map_profiles(
        latitude_min=9,
        latitude_max=11,
        longitude_min=69,
        longitude_max=71,
        search="project-float-1",
    )

    assert result["returned_count"] == 1
    assert result["results"][0]["latitude"] == pytest.approx(10.0)
    assert coordinate_result["returned_count"] == 1
    assert coordinate_result["results"][0]["longitude"] == pytest.approx(70.0)


def test_date_filters_include_the_full_end_date_in_utc(profile_service):
    page = profile_service.list_profiles(
        start_datetime="2023-01-02",
        end_datetime="2023-01-02",
    )

    assert page["total_count"] == 1
    assert page["results"][0]["datetime"] == "2023-01-02T00:00:00+00:00"


def test_profile_list_keeps_profiles_without_coordinates_but_map_excludes_them(profile_service):
    profile_service.db_service._con.execute(
        """
        INSERT INTO argo_profiles VALUES
        ('argo_no_location.nc', 'project-float-3', 1, 1, '2023-03-01T00:00:00Z', NULL, NULL, 5, 20, 35)
        """
    )

    page = profile_service.list_profiles(search="project-float-3")
    map_results = profile_service.map_profiles(search="project-float-3")

    assert page["total_count"] == 1
    assert page["results"][0]["latitude"] is None
    assert map_results["results"] == []


def test_invalid_profile_filters_are_rejected(profile_service):
    with pytest.raises(ValueError, match="Unsupported parameter"):
        profile_service.list_profiles(parameter="oxygen")
    with pytest.raises(ValueError, match="Unsupported region"):
        profile_service.map_profiles(region="North Atlantic")
    with pytest.raises(ValueError, match="earlier than"):
        profile_service.list_profiles(
            start_datetime="2023-02-01T00:00:00Z",
            end_datetime="2023-01-01T00:00:00Z",
        )
    with pytest.raises(ValueError, match="latitude_min"):
        profile_service.map_profiles(latitude_min=20, latitude_max=10)
    with pytest.raises(ValueError, match="positive"):
        profile_service.get_profile("argo_a.nc", 0)
