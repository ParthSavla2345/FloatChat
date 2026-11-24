import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.schemas import OrchestrationResponse
from services.orchestration_service import OrchestrationService


def test_valid_query_with_results():
    service = OrchestrationService()
    response = service.execute("Bay of Bengal temperature profiles")
    assert response.retrieval_status == "success"
    assert response.result_count > 0
    assert response.results
    assert response.query_plan["original_query"] == "Bay of Bengal temperature profiles"


def test_valid_query_with_zero_results():
    service = OrchestrationService()
    response = service.execute("Find temperature near 0 0 within 0.1 km after 2099-01-01")
    assert response.retrieval_status == "success_zero_results"
    assert response.result_count == 0
    assert response.results == []


def test_invalid_query_stops_before_retrieval():
    planner = MagicMock()
    planner.plan.return_value = MagicMock(
        validation_warnings=["Latitude is outside the supported range [-90, 90]."],
        interpretation_notes=["Attempted coordinate parse"],
        model_dump=lambda: {"original_query": "bad query"},
    )
    hybrid = MagicMock()
    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)

    response = service.execute("Find temperature at latitude 91")
    assert response.retrieval_status == "invalid_query"
    assert response.result_count == 0
    hybrid.retrieve.assert_not_called()


def test_query_requiring_clarification_stops_before_retrieval():
    planner = MagicMock()
    planner.plan.return_value = MagicMock(
        validation_warnings=["A geographic location was mentioned but could not be resolved reliably to a supported project region. Please specify one of: Arabian Sea, Bay of Bengal, Equatorial Indian Ocean, Southern Indian Ocean, Indian Ocean."],
        interpretation_notes=["Regional ambiguity detected"],
        model_dump=lambda: {"original_query": "Find chlorophyll in the North Atlantic"},
    )
    hybrid = MagicMock()
    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)

    response = service.execute("Find chlorophyll in the North Atlantic")
    assert response.retrieval_status == "clarification_required"
    assert response.result_count == 0
    hybrid.retrieve.assert_not_called()


def test_planner_warnings_are_returned():
    planner = MagicMock()
    planner.plan.return_value = MagicMock(
        validation_warnings=["Unsupported scientific parameters were mentioned: chlorophyll. Only temperature, salinity, and depth are validated in the current retrieval layer."],
        interpretation_notes=["Detected unsupported parameter"],
        model_dump=lambda: {"original_query": "Find chlorophyll in the Indian Ocean"},
    )
    hybrid = MagicMock()
    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)

    response = service.execute("Find chlorophyll in the Indian Ocean")
    assert response.validation_warnings
    assert response.retrieval_status == "clarification_required"


def test_hybrid_service_invocation_uses_expected_payload():
    planner = MagicMock()
    plan = MagicMock()
    plan.validation_warnings = []
    plan.interpretation_notes = ["Detected supported parameters: temperature."]
    plan.to_hybrid_dict.return_value = {
        "query": "Bay of Bengal temperature profiles",
        "semantic_text": "Bay of Bengal temperature profiles",
        "parameters": ["temperature"],
        "region": "Bay of Bengal",
        "max_results": 5,
    }
    plan.model_dump.return_value = {"original_query": "Bay of Bengal temperature profiles"}
    planner.plan.return_value = plan

    hybrid = MagicMock()
    hybrid.retrieve.return_value = {
        "applied_filters": {"region": "Bay of Bengal"},
        "results": [{"float_id": "F1", "hybrid_score": 0.88}],
        "ranking_explanation": {"method": "test"},
        "data_limitations": ["project float_id limitation"],
    }

    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)
    response = service.execute("Bay of Bengal temperature profiles")

    hybrid.retrieve.assert_called_once_with(plan.to_hybrid_dict.return_value)
    assert response.retrieval_status == "success"
    assert response.result_count == 1
    assert response.applied_filters == {"region": "Bay of Bengal"}


def test_hybrid_retrieval_exception_sets_failed_status():
    planner = MagicMock()
    plan = MagicMock()
    plan.validation_warnings = []
    plan.interpretation_notes = ["Valid query"]
    plan.to_hybrid_dict.return_value = {"query": "valid query", "max_results": 3}
    plan.model_dump.return_value = {"original_query": "valid query"}
    planner.plan.return_value = plan

    hybrid = MagicMock()
    hybrid.retrieve.side_effect = RuntimeError("DuckDB unavailable")

    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)
    response = service.execute("valid query")

    assert response.retrieval_status == "retrieval_failed"
    assert response.result_count == 0
    assert "DuckDB unavailable" in response.limitations[0]


def test_result_count_matches_response_length():
    planner = MagicMock()
    plan = MagicMock()
    plan.validation_warnings = []
    plan.interpretation_notes = ["Valid query"]
    plan.to_hybrid_dict.return_value = {"query": "test", "max_results": 2}
    plan.model_dump.return_value = {"original_query": "test"}
    planner.plan.return_value = plan

    hybrid = MagicMock()
    hybrid.retrieve.return_value = {
        "applied_filters": {"region": "Bay of Bengal"},
        "results": [
            {"float_id": "F1", "hybrid_score": 0.91},
            {"float_id": "F2", "hybrid_score": 0.82},
        ],
        "ranking_explanation": {"method": "test"},
        "data_limitations": [],
    }

    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)
    response = service.execute("test")
    assert response.result_count == len(response.results)
    assert response.result_count == 2


def test_ranking_and_identity_metadata_are_preserved():
    service = OrchestrationService()
    response = service.execute("Bay of Bengal temperature profiles")
    assert response.results
    first = response.results[0]
    assert first.get("float_id") or first.get("matched_float_ids")
    assert "hybrid_score" in first or response.ranking_explanation


def test_no_duplicate_execution_of_planner_or_retrieval_service():
    planner = MagicMock()
    plan = MagicMock()
    plan.validation_warnings = []
    plan.interpretation_notes = ["Valid query"]
    plan.to_hybrid_dict.return_value = {"query": "test", "max_results": 2}
    plan.model_dump.return_value = {"original_query": "test"}
    planner.plan.return_value = plan

    hybrid = MagicMock()
    hybrid.retrieve.return_value = {"applied_filters": {}, "results": [{"float_id": "F1", "hybrid_score": 0.5}], "ranking_explanation": {"method": "test"}, "data_limitations": []}

    service = OrchestrationService(planner_cls=planner, hybrid_service=hybrid)
    service.execute("test")
    assert planner.plan.call_count == 1
    assert hybrid.retrieve.call_count == 1


def test_orchestration_response_model_is_compatible_with_schema():
    response = OrchestrationResponse(
        original_query="Find salinity in the Indian Ocean",
        query_plan={"parameters": ["salinity"], "region": "Indian Ocean"},
        interpretation_notes=["Detected supported parameters: salinity."],
        applied_filters={"region": "Indian Ocean"},
        validation_warnings=[],
        retrieval_status="success",
        results=[{"float_id": "F1", "hybrid_score": 0.77}],
        result_count=1,
        ranking_explanation={"method": "test"},
        limitations=[]
    )
    assert response.retrieval_status == "success"
    assert response.result_count == 1
