# Orchestration Layer

## Purpose

The orchestration layer provides the narrow integration point between the user-facing natural-language question and the validated retrieval stack. It does not add new retrieval logic; it simply coordinates the existing Stage 8A planner and Stage 7 hybrid engine.

## Responsibilities

- accept a single natural-language question,
- call `QueryPlanner.plan()` to interpret constraints,
- evaluate planner validation warnings,
- stop safely on invalid or ambiguous input,
- convert a valid plan to the hybrid service payload,
- invoke the hybrid retrieval engine,
- return a structured response with explainability and status metadata.

## Service contract

- `backend/services/orchestration_service.py`
- `OrchestrationService.execute(question: str) -> OrchestrationResponse`

## Status values

The orchestration response uses a fixed set of statuses:

- `success` — retrieval succeeded with one or more results.
- `success_zero_results` — retrieval succeeded but no results matched.
- `invalid_query` — the question was malformed or violated a range/date rule.
- `clarification_required` — a location or unsupported parameter requires a human clarification.
- `retrieval_failed` — the planner succeeded but retrieval execution raised an exception.

## Validation behavior

The orchestrator exits early for invalid or ambiguous queries instead of running the retrieval stack. It preserves the planner warnings and includes them in the returned payload.

## Integration detail

`question -> QueryPlanner.plan() -> plan.to_hybrid_dict() -> HybridRetrievalQuery.from_dict() -> HybridRetrievalService.retrieve()`

This keeps planning and retrieval responsibilities distinct and avoids duplicating any database or ranking logic.

## Explainability output

The orchestrator returns:

- the original question,
- the generated planner output,
- interpretation notes,
- applied filters from the retrieval service,
- validation warnings,
- retrieval status,
- result list,
- result count,
- ranking explanation,
- data limitations.

## Stage 9 integration

When `use_llm=True`, the orchestration service can optionally invoke `LLMService.interpret()` before falling back to the rule-based planner. The LLM response is accepted only if it validates against the project schema and rules. Otherwise the request returns an explicit invalid or clarification status with the planner output preserved for explainability.

## Limitations

- The underlying hybrid service is float-level, not profile-row-level.
- Raw `PLATFORM_NUMBER` remains the source-of-truth identifier when true ARGO platform IDs are required.
- The planner remains rule-based and intentionally conservative rather than guessing missing geographic context.
- The LLM layer is optional and cannot replace validated retrieval logic.
