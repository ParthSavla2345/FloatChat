# API and Tool Reference

## Query planner

### `QueryPlanner.plan(query: str) -> QueryPlan`

- Input: a natural-language scientific query.
- Output: a validated `QueryPlan` object with extracted parameters, region, coordinates, dates, and warnings.
- Current implementation lives in `backend/services/query_planner.py`.

## Hybrid retrieval

### `HybridRetrievalService.retrieve(query: HybridRetrievalQuery | dict) -> dict`

- Input: a Stage 7-compatible structured query payload.
- Output: ranked hybrid retrieval results with filters, counts, and explainability metadata.
- Current implementation lives in `backend/services/hybrid_service.py`.

## Orchestration service

### `OrchestrationService.execute(question: str) -> OrchestrationResponse`

- Input: one natural-language question.
- Output: a structured orchestration response with status, planner output, retrieval results, and explainability metadata.
- Current implementation lives in `backend/services/orchestration_service.py`.

## Response schema

`backend/models/schemas.py` defines:

- `OrchestrationRequest`
- `OrchestrationResponse`
- `QueryPlan`
- `HybridRetrievalRequest`
- `HybridRetrievalResponse`

The orchestration response includes:

- `original_query`
- `query_plan`
- `interpretation_notes`
- `applied_filters`
- `validation_warnings`
- `retrieval_status`
- `results`
- `result_count`
- `ranking_explanation`
- `limitations`

## Read-only MCP server (Stage 11)

The MCP entry point is `backend/mcp_server/server.py`; run from the backend directory with `python -m mcp_server.server`. It uses the official MCP Python SDK stdio transport and shares the existing `ProfileExplorerService`. The MCP server does not call the LLM, Chroma, or hybrid retriever and does not accept SQL.

| Tool | Inputs and bounds | Output |
|---|---|---|
| `search_argo_profiles` | Optional `parameter` (`temperature`, `salinity`, `depth`), supported `region`, ISO date range, latitude/longitude bounds, substring search; `limit` 1–200 | Typed `SearchProfilesResponse`, actual matching profile IDs and applied filters |
| `get_float_details` | Exact project-level `float_id` | Typed aggregates for that ID or `not_found`; raw WMO availability is explicitly false |
| `get_profile_observations` | `profile_id` in `<source_file>#profile=<positive_number>` form; optional parameters and pressure range; `limit` 1–2,000 | Typed actual measurements, with `depth` sourced from NetCDF `PRES` |
| `compare_profiles` | 2–4 unique `profile_id` values; parameter is temperature or salinity; optional pressure bounds | Separate observed series with no interpolation; missing/incomplete identities are marked |
| `get_dataset_summary` | No arguments | Existing dataset counts, coverage, region counts, and service limitations |

`backend/mcp_server/schemas.py` defines response types. All handlers in `backend/mcp_server/tools.py` use `ProfileExplorerService` methods; SQL remains parameterized within that service. Errors are surfaced as MCP tool errors with sanitized service-failure messages. The complete contract, launch details, and verified scope are in `docs/11_MCP_SERVER_INTEGRATION.md`.
