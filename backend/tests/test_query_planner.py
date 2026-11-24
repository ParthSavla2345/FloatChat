import sys
from pathlib import Path

from services.query_planner import QueryPlanner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_parameter_extraction():
    plan = QueryPlanner.plan("Find temperature and salinity observations in the Bay of Bengal during 2023")
    assert plan.parameters == ["temperature", "salinity"]
    assert plan.region == "Bay of Bengal"
    assert plan.start_date == "2023-01-01"
    assert plan.end_date == "2023-12-31"


def test_date_extraction_for_month_range():
    plan = QueryPlanner.plan("Show observations between January and March 2023")
    assert plan.start_date == "2023-01-01"
    assert plan.end_date == "2023-03-31"


def test_coordinate_and_radius_extraction():
    plan = QueryPlanner.plan("Find floats near latitude 15 and longitude 70 within 200 km")
    assert plan.latitude == 15.0
    assert plan.longitude == 70.0
    assert plan.radius_km == 200.0


def test_bounding_box_extraction():
    plan = QueryPlanner.plan("Find temperature between latitude 5 to 12 and longitude 60 to 80")
    assert plan.bounding_box == {
        "latitude_min": 5.0,
        "latitude_max": 12.0,
        "longitude_min": 60.0,
        "longitude_max": 80.0,
    }


def test_multiple_parameters_and_limit():
    plan = QueryPlanner.plan("Top 10 temperature and salinity profiles in the Arabian Sea")
    assert plan.parameters == ["temperature", "salinity"]
    assert plan.top_k == 10
    assert plan.region == "Arabian Sea"


def test_unsupported_parameter_warning():
    plan = QueryPlanner.plan("Find chlorophyll in the Indian Ocean")
    assert "chlorophyll" in " ".join(plan.validation_warnings).lower()
    assert plan.region == "Indian Ocean"


def test_invalid_dates_and_coordinates_are_warned():
    plan = QueryPlanner.plan("Find temperature near latitude 91 and longitude 181 from 2024-03-01 to 2024-02-01")
    assert plan.validation_warnings
    assert plan.latitude is None
    assert plan.longitude is None


def test_missing_constraints_are_handled_gracefully():
    plan = QueryPlanner.plan("Find information about ARGO float quality")
    assert plan.parameters == []
    assert plan.region is None
    assert "semantic retrieval" in " ".join(plan.interpretation_notes).lower()


def test_integration_with_stage_7_hybrid_query():
    plan = QueryPlanner.plan("Find temperature and salinity in the Bay of Bengal during 2023")
    hybrid = plan.to_hybrid_dict()
    assert hybrid["query"] == plan.original_query
    assert hybrid["semantic_text"]
    assert hybrid["parameters"] == ["temperature", "salinity"]
    assert hybrid["region"] == "Bay of Bengal"
    assert hybrid["max_results"] == plan.top_k


def test_ambiguous_location_requires_warning():
    plan = QueryPlanner.plan("Find temperature near the North Atlantic during 2023")
    assert any("supported project region" in warning.lower() for warning in plan.validation_warnings)
