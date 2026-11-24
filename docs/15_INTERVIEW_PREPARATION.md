# Interview Preparation Notes

## What was recovered and verified

- Stage 1: NetCDF extraction completed and validated.
- Stage 2: parquet validation and data quality checks completed.
- Stage 3: DuckDB materialization and schema validation completed.
- Stage 4: float metadata generation completed.
- Stage 5: semantic retrieval over Chroma completed.
- Stage 6: spatial and temporal retrieval completed and verified.
- Stage 7: hybrid retrieval engine completed and verified.
- Stage 8A: natural-language query planning completed and verified.
- Stage 8B: query orchestration completed and verified.
- Stage 9: optional LLM-based interpretation, with validation and deterministic fallback, completed and verified.
- Stage 10: interactive Next.js scientific-data dashboard locally verified against actual DuckDB and retrieval results.
- Stage 11: independent read-only MCP server verified through controlled-data tool calls and stdio discovery.

## Verified implementation highlights

- Shared config via `backend/config.py` and `settings` singleton.
- Read-only SQL execution in `backend/services/duckdb_service.py`.
- Spatial retrieval in `backend/services/spatial_temporal_service.py`.
- Hybrid retrieval in `backend/services/hybrid_service.py`.
- Query planning in `backend/services/query_planner.py`.
- Semantic search in `backend/services/semantic_service.py`.
- Automated verification in `backend/tests/test_semantic_index.py`, `backend/tests/test_spatial_temporal.py`, `backend/tests/test_hybrid_retrieval.py`, and `backend/tests/test_query_planner.py`.
- Read-only dashboard data operations in `backend/services/profile_explorer_service.py`; the service returns actual dataset summaries, bounded profile pages, map locations, and individual measurement levels.
- Browser pages for overview, natural-language query, map, paginated profiles, profile details/charts, and up-to-four-profile comparison.
- Local Next.js API routes call existing Python services and do not accept arbitrary SQL.
- MCP tools reuse the same `ProfileExplorerService` for profile search, exact project-float aggregates, bounded observations, non-interpolated comparison, and summary.

## Important technical caveat

The processed `float_id` is not guaranteed to be the raw ARGO WMO-like identifier. The real source field is `PLATFORM_NUMBER` inside the NetCDF files. Filenames are not float IDs and should not be used as IDs in production workflows.

## Stage 10 dashboard answer

"The browser app is a presentation layer over the existing Python services. The query explorer posts a natural-language question to the orchestration service; the other pages use a bounded, read-only DuckDB profile explorer for summary metrics, map markers, profile pages, and measurement detail. Profile identity is the source-file/profile-number pair, separate from the project float key. All plotted values are observations, with no interpolation. The processed table has no QC columns, so the UI reports QC as unavailable. The Next.js routes spawn a local Python process per request, so this is verified as a local integration, not as a production deployment."

The current recovered local data contains 68,470,264 observation rows, 52,240 source-file/profile-number pairs, and 706 project float keys/source files. Dataset coverage is 2022-01-01 through 2024-12-20 UTC. These values come from the actual database at the time of verification.

## Stage 11 MCP answer

"The MCP server is a separate stdio adapter over the existing read-only profile explorer service. It exposes five typed, bounded tools and does not accept SQL or bypass the service layer. Tool calls preserve source-file/profile-number identity separately from the project float key, and raw `PLATFORM_NUMBER` and QC remain explicitly unavailable in the processed DuckDB schema. Controlled-data protocol calls and a local stdio smoke test against the recovered database are verified; external-host deployment is not."

The Stage 11 backend regression result is `80 passed` with 20 existing Pandas deprecation warnings. Sixteen focused MCP tests exercise all tool handlers, validation, error paths, structured client calls, and stdio tool discovery.

## Stage 10 validation evidence

- Frontend `npm run lint` passed.
- Frontend `npm run build` passed and included the dashboard pages and API routes.
- Backend regression suite: 63 passed, with 20 non-blocking Pandas deprecation warnings.
- Local browser/API verification covered overview metrics, query orchestration, map locations, paginated profiles, profile detail and charts, and profile comparison.

## UTC and geospatial correctness

- Temporal outputs are normalized to UTC.
- Spatial queries use coordinate validation and a Haversine-based distance calculation.
- Nearest-float results must be grouped by true `float_id` to avoid counting every profile as its own float.

## Stage 6 service examples

- bbox search: `search_bbox(latitude_min, latitude_max, longitude_min, longitude_max)`
- radius search: `search_radius(latitude, longitude, radius_km)`
- nearest floats: `nearest_floats(latitude, longitude, top_k=5)`
- date range: `search_date_range(start_datetime, end_datetime)`
- monthly: `search_by_month(year, month)`

## Stage 7 hybrid service example

- hybrid retrieval: `HybridRetrievalQuery(query='Bay of Bengal salinity', region='Bay of Bengal', start_datetime='2022-01-01', end_datetime='2022-12-31', parameters=['temperature', 'salinity'])`
- result: explainable ranked hybrid matches with semantic scores and enforced structured filters

## Stage 8A planner example

- natural-language input: `Find temperature and salinity in the Bay of Bengal during 2023`
- structured plan: `QueryPlan(original_query='Find temperature and salinity in the Bay of Bengal during 2023', parameters=['temperature', 'salinity'], region='Bay of Bengal', start_date='2023-01-01', end_date='2023-12-31', top_k=5)`
- integration: `plan.to_hybrid_dict()` produces the Stage 7-compatible payload consumed by `HybridRetrievalQuery.from_dict()`

## Stage 8B orchestration example

- natural-language input: `Bay of Bengal temperature profiles`
- orchestration flow: `QueryPlanner.plan() -> plan.to_hybrid_dict() -> HybridRetrievalService.retrieve() -> OrchestrationResponse`
- status: `success` when results are returned, `success_zero_results` when the planner and retrieval succeed but no records match, and `clarification_required` or `invalid_query` when the user input must be corrected.

## Good architecture answer

"The project is a staged data pipeline: NetCDF ingestion to parquet, conversion to DuckDB, float-level metadata generation, semantic retrieval, and then a service layer for spatial and temporal retrieval. The design intentionally keeps the LLM and retrieval planner separate from the data services, and the database remains read-only to preserve the integrity of the recovered pipeline."
