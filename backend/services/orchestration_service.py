from __future__ import annotations

from typing import Any

from models.schemas import OrchestrationResponse, QueryPlan
from services.hybrid_service import get_hybrid_retrieval_service
from services.llm_service import get_llm_service
from services.query_planner import QueryPlanner


class OrchestrationService:
    """Lightweight orchestration layer linking natural-language questions to the planner and hybrid retrieval engine."""

    def __init__(self, planner_cls=None, hybrid_service=None, llm_service=None, use_llm: bool = False):
        self.planner_cls = planner_cls or QueryPlanner
        self.hybrid_service = hybrid_service or get_hybrid_retrieval_service()
        self.llm_service = llm_service or get_llm_service() if use_llm else None
        self.use_llm = use_llm

    @staticmethod
    def _invalid_query_from_warnings(warnings: list[str]) -> bool:
        invalid_markers = (
            "outside the supported range",
            "later than end date",
            "must be non-negative",
            "must be greater than zero",
            "must be between",
        )
        return any(marker in warning.lower() for warning in warnings for marker in invalid_markers)

    @staticmethod
    def _clarification_required_from_warnings(warnings: list[str]) -> bool:
        clarification_markers = (
            "could not be resolved reliably",
            "please specify one of",
            "unsupported scientific parameters were mentioned",
            "ambiguous",
        )
        return any(marker in warning.lower() for warning in warnings for marker in clarification_markers)

    def _plan_question(self, raw_question: str) -> tuple[QueryPlan, dict[str, Any]]:
        fallback_plan = self.planner_cls.plan(raw_question)
        llm_metadata = {"used": False, "provider": None, "model": None, "fallback_used": False}

        if self.use_llm and self.llm_service is not None and self.llm_service.is_enabled():
            llm_result = self.llm_service.interpret(raw_question, fallback_plan=fallback_plan)
            llm_metadata.update({
                "used": True,
                "provider": llm_result.provider,
                "model": llm_result.model,
                "fallback_used": llm_result.fallback_used,
                "status": llm_result.status,
            })
            if llm_result.status in {"success", "fallback"} and llm_result.structured_query:
                try:
                    plan = QueryPlan.model_validate(llm_result.structured_query)
                    llm_metadata["validation_warnings"] = llm_result.validation_warnings
                    llm_metadata["interpretation_notes"] = llm_result.interpretation_notes
                    return plan, llm_metadata
                except Exception:
                    pass
            if llm_result.status in {"invalid", "clarification_required", "provider_error"}:
                llm_metadata["warnings"] = llm_result.validation_warnings
                llm_metadata["error"] = llm_result.error

        return fallback_plan, llm_metadata

    def execute(self, question: str) -> OrchestrationResponse:
        if not isinstance(question, str) or not question.strip():
            return OrchestrationResponse(
                original_query="",
                query_plan={},
                interpretation_notes=[],
                applied_filters={},
                validation_warnings=["Query is empty or not a string."],
                retrieval_status="invalid_query",
                results=[],
                result_count=0,
                ranking_explanation={},
                limitations=["A natural-language question is required to run the planner and retrieval stack."],
            )

        raw_question = " ".join(question.strip().split())
        plan, llm_metadata = self._plan_question(raw_question)
        warnings = list(plan.validation_warnings)

        if warnings and self._invalid_query_from_warnings(warnings):
            return OrchestrationResponse(
                original_query=raw_question,
                query_plan={**plan.model_dump(), "llm_metadata": llm_metadata},
                interpretation_notes=plan.interpretation_notes,
                applied_filters={},
                validation_warnings=warnings,
                retrieval_status="invalid_query",
                results=[],
                result_count=0,
                ranking_explanation={},
                limitations=warnings,
                llm_metadata=llm_metadata,
            )

        if warnings and self._clarification_required_from_warnings(warnings):
            return OrchestrationResponse(
                original_query=raw_question,
                query_plan={**plan.model_dump(), "llm_metadata": llm_metadata},
                interpretation_notes=plan.interpretation_notes,
                applied_filters={},
                validation_warnings=warnings,
                retrieval_status="clarification_required",
                results=[],
                result_count=0,
                ranking_explanation={},
                limitations=warnings,
                llm_metadata=llm_metadata,
            )

        hybrid_payload = plan.to_hybrid_dict()

        try:
            retrieval = self.hybrid_service.retrieve(hybrid_payload)
        except Exception as exc:  # pragma: no cover - defensive branch exercised in tests via mock
            return OrchestrationResponse(
                original_query=raw_question,
                query_plan={**plan.model_dump(), "llm_metadata": llm_metadata},
                interpretation_notes=plan.interpretation_notes,
                applied_filters={},
                validation_warnings=warnings,
                retrieval_status="retrieval_failed",
                results=[],
                result_count=0,
                ranking_explanation={},
                limitations=[f"Retrieval failure: {exc}"],
                llm_metadata=llm_metadata,
            )

        results = retrieval.get("results", []) or []
        result_count = len(results)
        status = "success" if result_count > 0 else "success_zero_results"

        return OrchestrationResponse(
            original_query=raw_question,
            query_plan={**plan.model_dump(), "llm_metadata": llm_metadata},
            interpretation_notes=plan.interpretation_notes,
            applied_filters=retrieval.get("applied_filters", {}),
            validation_warnings=warnings,
            retrieval_status=status,
            results=results,
            result_count=result_count,
            ranking_explanation=retrieval.get("ranking_explanation", {}),
            limitations=retrieval.get("data_limitations", []),
            llm_metadata=llm_metadata,
        )


def get_orchestration_service() -> OrchestrationService:
    """Return the module-level orchestration service singleton."""
    global _service
    if _service is None:
        _service = OrchestrationService()
    return _service


_service: OrchestrationService | None = None
