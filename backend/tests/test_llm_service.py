import sys
from pathlib import Path

from services.llm_service import LLMService, MockLLMProvider
from services.orchestration_service import OrchestrationService
from services.query_planner import QueryPlanner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_valid_structured_output():
    service = LLMService(provider_instance=MockLLMProvider())
    result = service.interpret("Find temperature in the Bay of Bengal")
    assert result.status == "success"
    assert result.structured_query["parameters"] == ["temperature"]
    assert result.structured_query["region"] == "Bay of Bengal"
    assert result.provider == "mock"


def test_invalid_json_triggers_fallback():
    service = LLMService(provider_instance=MockLLMProvider(invalid_json=True))
    question = "Find temperature in the Bay of Bengal"
    fallback = QueryPlanner.plan(question)
    result = service.interpret(question, fallback_plan=fallback)
    assert result.status == "fallback"
    assert result.fallback_used is True
    assert result.structured_query["original_query"] == question


def test_missing_fields_are_rejected():
    service = LLMService(provider_instance=MockLLMProvider(missing_fields=True))
    question = "Find temperature in the Bay of Bengal"
    fallback = QueryPlanner.plan(question)
    result = service.interpret(question, fallback_plan=fallback)
    assert result.status == "fallback"


def test_provider_timeout_triggers_fallback():
    service = LLMService(provider_instance=MockLLMProvider(timeout=True))
    question = "Find salinity in the Arabian Sea"
    fallback = QueryPlanner.plan(question)
    result = service.interpret(question, fallback_plan=fallback)
    assert result.status == "fallback"
    assert result.fallback_used is True


def test_unsupported_parameters_are_flagged():
    service = LLMService(provider_instance=MockLLMProvider(unsupported_parameter=True))
    result = service.interpret("Find chlorophyll in the Bay of Bengal")
    assert result.status == "clarification_required"
    assert any("unsupported" in warning.lower() for warning in result.validation_warnings)


def test_invalid_coordinates_are_rejected():
    service = LLMService(provider_instance=MockLLMProvider(invalid_coordinates=True))
    result = service.interpret("Find temperature at latitude 91 and longitude 181")
    assert result.status == "invalid"
    assert any("latitude" in warning.lower() or "longitude" in warning.lower() for warning in result.validation_warnings)


def test_orchestration_can_use_llm_when_enabled():
    llm_service = LLMService(provider_instance=MockLLMProvider())
    service = OrchestrationService(llm_service=llm_service, use_llm=True)
    response = service.execute("Find temperature in the Bay of Bengal")
    assert response.retrieval_status == "success"
    assert response.llm_metadata["used"] is True
    assert response.query_plan["region"] == "Bay of Bengal"


def test_fallback_to_rule_based_planner_when_llm_fails():
    llm_service = LLMService(provider_instance=MockLLMProvider(timeout=True))
    service = OrchestrationService(llm_service=llm_service, use_llm=True)
    response = service.execute("Find salinity in the Arabian Sea")
    assert response.llm_metadata["fallback_used"] is True
    assert response.query_plan["original_query"] == "Find salinity in the Arabian Sea"


def test_llm_output_is_validated_against_existing_schema():
    service = LLMService(provider_instance=MockLLMProvider())
    result = service.interpret("Top 8 temperature and salinity profiles in the Indian Ocean")
    assert result.status == "success"
    assert result.structured_query["parameters"] == ["temperature"]
    assert result.structured_query["top_k"] == 5


def test_no_direct_sql_execution_in_llm_layer():
    service = LLMService(provider_instance=MockLLMProvider())
    result = service.interpret("Find temperature in the Bay of Bengal")
    assert "select" not in str(result.structured_query).lower()
