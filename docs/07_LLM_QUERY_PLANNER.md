# Query Planning Layer

## Purpose

The query-planning layer sits between a natural-language question and the existing Stage 7 hybrid retrieval engine. It does not perform retrieval or ranking itself; instead, it converts a user question into a validated structured query contract that can be passed to `backend/services/hybrid_service.py`.

## Scope

This stage keeps the system rule-based and deterministic. No LLM, no MCP, and no new embedding index are introduced. The planner is intentionally limited to supported project regions, supported scientific parameters, and the existing hybrid retrieval contract.

## Supported query types

The planner accepts:

- parameter extraction for temperature, salinity, and depth,
- region extraction for Arabian Sea, Bay of Bengal, Equatorial Indian Ocean, Southern Indian Ocean, and Indian Ocean,
- coordinate extraction for point-based searches,
- radius extraction in kilometres,
- bounding-box extraction using latitude/longitude ranges,
- date-range extraction for full dates, month ranges, and single-year queries,
- top-K result limit extraction.

## Output contract

The planner emits a `QueryPlan` model containing:

- `original_query`
- `semantic_query`
- `parameters`
- `region`
- `latitude`
- `longitude`
- `radius_km`
- `bounding_box`
- `start_date`
- `end_date`
- `top_k`
- `interpretation_notes`
- `validation_warnings`

The `to_hybrid_dict()` method converts the plan into the equivalent Stage 7 `HybridRetrievalQuery` dictionary format.

## Validation rules

- Coordinates must remain within valid latitude and longitude ranges.
- Radius values must be non-negative.
- Date ranges must be valid; start dates cannot exceed end dates.
- Geographic names outside the supported project region list trigger a clarification warning instead of a guessed coordinate.
- Unsupported parameters trigger warnings and are not passed to the retrieval engine as if they were supported.

## Integration details

The planner feeds the Stage 7 service through:

- `QueryPlanner.plan(query)`
- `plan.to_hybrid_dict()`
- `HybridRetrievalQuery.from_dict(plan.to_hybrid_dict())`

This keeps all retrieval logic in the existing service layer while preserving a clean separation between user-question interpretation and actual retrieval execution.

### Stage 8B orchestration behavior

The orchestration service (`backend/services/orchestration_service.py`) sits on top of the planner:

- it executes the planner,
- inspects validation warnings,
- returns `invalid_query` or `clarification_required` before retrieval when needed,
- invokes the hybrid service only for valid questions,
- packages the final result with planning metadata, filters, and ranking explanation.

## Stage 9 LLM layer

The project now includes an optional provider-agnostic LLM layer in `backend/services/llm_service.py`. This layer is intentionally constrained to produce a `QueryPlan`-compatible payload and never executes SQL or direct retrieval. It should be treated as an interpretation aid, not an execution authority.

The deterministic planner remains the fallback and validation baseline. When the provider is unavailable, times out, returns invalid JSON, or emits unsupported/ambiguous output, the system falls back to the rule-based planner instead of guessing.

## Query-planner file

- `backend/services/query_planner.py`
- `backend/services/llm_service.py`

## Testing

- `backend/tests/test_query_planner.py`

## Known limitations

- Rule-based parsing is intentionally conservative; it prefers explicit validation and warnings over silent guesses.
- The supported scientific parameter list is limited to the project’s actual metadata and Stage 7 retrieval contract.
- Unsupported or ambiguous locations are reported rather than converted into coordinates.
