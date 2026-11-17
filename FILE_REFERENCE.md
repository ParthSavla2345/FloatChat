# File Reference

## Verified functionality

- `backend/config.py` – central settings and path definitions; exposes the `settings` singleton used by the ingestion and service modules and now reads environment-specific values with startup validation.
- `backend/health.py` – lightweight runtime health checks that validate dataset availability, backend configuration and optional LLM settings without executing database writes.
- `.env.example` – example environment variables for backend data, LLM, and runtime settings; do not commit real secrets.
- `frontend/.env.example` – example Next.js environment variables for the local Python bridge and frontend API base URL.
- `backend/ingestion/build_chroma_index.py` – verified semantic index builder; populates a persistent Chroma collection and includes the Windows-safe console output fix required for successful execution on cp1252 terminals.
- `backend/services/semantic_service.py` – verified semantic search layer over the persisted Chroma collection.
- `backend/services/spatial_temporal_service.py` – verified spatial and temporal retrieval layer for bounding-box, radius, nearest-float, and date-range queries.
- `backend/services/hybrid_service.py` – verified hybrid retrieval layer that merges Chroma semantic results with DuckDB spatial and temporal filtering.
- `backend/services/query_planner.py` – verified rule-based planner that converts natural-language questions into validated Stage 7-compatible structured queries.
- `backend/services/orchestration_service.py` – verified orchestration layer that coordinates the planner and hybrid service and returns structured explainability metadata.
- `backend/services/llm_service.py` – verified optional LLM integration layer with provider abstraction, environment-based configuration, validation, fallback logic, and a mock provider for tests.
- `backend/services/profile_explorer_service.py` – read-only DuckDB service for dataset summary, region counts, profile-level pages, map locations, and bounded individual-profile measurements.
- `backend/mcp_server/server.py` – independently runnable stdio MCP server registering the five read-only OceanIQ tools.
- `backend/mcp_server/tools.py` – validates bounded search, project float, profile observation, comparison, and summary requests before reusing `ProfileExplorerService`.
- `backend/mcp_server/schemas.py` – Pydantic response contracts for MCP tools, preserving the distinction between project float IDs, profile identities, and source files.
- `backend/tests/test_mcp_server.py` – controlled-data tests for MCP handlers, validation, safe errors, structured protocol calls, and stdio discovery.
- `backend/requirements.txt` – backend dependencies, including the official `mcp>=2.3.0,<3.0` SDK.
- `backend/tests/test_profile_explorer.py` – controlled in-memory DuckDB tests for metrics, grouping, filters, date handling, pagination, locations, and profile detail.
- `frontend/src/app/page.tsx` – data-backed overview with actual observation/profile/float counts, available fields, regional profile coverage, browser query history, and navigation links.
- `frontend/src/app/layout.tsx` – root metadata and shared `AppShell` wrapper for every route.
- `frontend/src/app/globals.css` – Tailwind import and shared OceanIQ dashboard, navigation, map, chart, table, and responsive styles.
- `frontend/src/app/about/page.tsx` – user-facing notes on data coverage, identity, pressure, and QC limitations.
- `frontend/src/app/explorer/page.tsx` plus `frontend/src/components/chat/query-explorer.tsx` – conversational query submission through the existing `/api/query` route, explainability, result display, and recent query history.
- `frontend/src/app/map/page.tsx` plus `frontend/src/components/map/argo-map.tsx` – interactive React-Leaflet map using actual profile coordinates and bounded spatial/temporal/parameter/identifier filters.
- `frontend/src/app/profiles/page.tsx` – filtered and paginated profile list, current-page sorting, and selection for comparisons.
- `frontend/src/app/profiles/detail/page.tsx` plus `frontend/src/components/profiles/profile-detail-view.tsx` – actual individual profile metadata, measurement table, pressure/temperature/salinity charts, and QC-unavailable messaging.
- `frontend/src/app/compare/page.tsx` – comparison of two to four profiles with measured-data overlays and coordinate/time differences.
- `frontend/src/app/api/query/route.ts` – existing local Next.js bridge to the Python orchestration service.
- `frontend/src/app/api/data/[action]/route.ts` – bounded read-only API bridge for summary, profiles, map, and individual profile data.
- `frontend/src/lib/api.ts` and `frontend/src/lib/types.ts` – typed frontend API client and backend response shapes.
- `frontend/src/components/charts/profile-charts.tsx` – Recharts scatter plots that use observed values and pressure coordinates without interpolation.
- `frontend/package.json` and `frontend/package-lock.json` – Next.js scripts and pinned frontend dependencies, including chart/map/icon libraries.
- `backend/data/chroma/` – verified persistent Chroma output; the `argo_profiles` collection was successfully created and counted at 706 documents.
- `backend/tests/test_semantic_index.py` – focused automated verification for metadata normalization, summary generation, and semantic retrieval.
- `backend/tests/test_spatial_temporal.py` – focused automated verification for Stage 6 spatial and temporal retrieval.
- `backend/tests/test_hybrid_retrieval.py` – focused automated verification for Stage 7 hybrid retrieval.
- `backend/tests/test_query_planner.py` – focused automated verification for Stage 8A natural-language planning and validation.
- `backend/tests/test_orchestration.py` – focused automated verification for Stage 8B orchestration and validation behavior.
- `backend/tests/test_mcp_server.py` – focused Stage 11 tests, including all five MCP tool operations on controlled data and protocol transport checks.
- `backend/tests/test_runtime_health.py` – verifies environment-driven configuration and runtime health-check behavior for startup validation.

## Unverified functionality

- External MCP client setup/deployment and authentication are not verified. Controlled-data MCP calls, stdio tool discovery, and a local stdio tool smoke test against the recovered database are verified.
- The LLM layer is optional and tested only with mock or provider-retry patterns; it does not replace the validated rule-based planner or underlying retrieval engine.
- The true raw WMO float ID is not persisted in the processed DuckDB table; any downstream system requiring the actual ARGO platform number must explicitly read `PLATFORM_NUMBER` from the original NetCDF or backfill it.
- QC flags are unavailable in the processed DuckDB schema. The dashboard labels them unavailable; this does not assert that observations pass QC.
- OpenStreetMap tiles loaded during the local browser check; future tile availability still depends on external network access. Marker coordinates come from DuckDB.

## Ingestion and processing scripts

- `backend/ingestion/extract_profiles.py` – reads NetCDF profile files from `archive/` and writes `argo_profiles.parquet`; sets `float_id` from `PLATFORM_NUMBER` when available and falls back to the source filename if decoding fails.
- `backend/ingestion/inspect_netcdf.py` – inventories NetCDF dimensions and variables.
- `backend/generate_metadata.py` – creates summary metadata for each float.
- `backend/ingestion/build_chroma_index.py` – generates semantic summaries and populates the Chroma collection.
- `backend/ingestion/build_duckdb.py` – creates the persistent DuckDB database from parquet.
- `backend/validate_database.py` – checks counts, ranges, duplication, and sample quality.

## Data artifacts

- `archive/` – original NetCDF ARGO files.
- `backend/data/processed/argo_profiles.parquet` – flattened observation table.
- `backend/data/processed/float_metadata.parquet` – float-level metadata table.
- `backend/data/processed/float_metadata.json` – metadata export used by semantic indexing and verification.
- `backend/data/processed/floatchat.duckdb` – queryable DuckDB database.
- `backend/data/chroma/` – persistent Chroma index output.

## Application services

- `backend/services/duckdb_service.py` – read-only SQL engine with safety checks.
- `backend/services/semantic_service.py` – semantic search over Chroma embeddings.
- `backend/services/spatial_temporal_service.py` – spatial retrieval (bbox, radius, nearest-float, regional) and temporal retrieval (date-range, month, last N, comparisons, date-bounds) built on DuckDB.
- `backend/services/hybrid_service.py` – hybrid retrieval engine combining semantic relevance and enforced structured filters.
- `backend/services/query_planner.py` – natural-language query planner that converts free-form scientific questions into structured hybrid-retrieval input while validating supported constraints.
- `backend/services/orchestration_service.py` – orchestration service connecting the planner to the hybrid retrieval engine and packaging the response for callers.
- `backend/services/llm_service.py` – optional LLM interpretation layer used only to generate a Stage 8A-compatible query plan; it never executes SQL or calls DuckDB or Chroma directly.
- `backend/services/profile_explorer_service.py` – parameterized read-only operations for dashboard summary, profile listing, map data, profile measurements, and exact project-level float aggregates. It preserves profile identity as `(file_name, profile_number)` and normalizes timestamps to UTC.
- `backend/mcp_server/server.py` – MCP server factory and stdio entry point (`python -m mcp_server.server` from `backend/`).
- `backend/mcp_server/tools.py` – five MCP handlers (`search_argo_profiles`, `get_float_details`, `get_profile_observations`, `compare_profiles`, and `get_dataset_summary`); all results are bounded and use the existing read-only service.
- `backend/mcp_server/schemas.py` – strict typed response models for profile search, float details, observations, comparisons, and dataset summary.
- `frontend/src/app/api/query/route.ts` – Next.js API endpoint that executes the verified Python orchestration service and returns the structured response payload to the browser UI.
- `frontend/src/app/api/data/[action]/route.ts` – Next.js GET route with allowlisted operations, numeric/input validation, result limits, and parameterized calls into `ProfileExplorerService`.
- `frontend/src/app/page.tsx` – data-backed dashboard overview.
- `frontend/src/app/explorer/page.tsx` – query explorer page that reuses the established orchestration endpoint.
- `frontend/src/app/map/page.tsx` – filtered profile map page.
- `frontend/src/app/profiles/page.tsx` – paginated profile explorer page.
- `frontend/src/app/profiles/detail/page.tsx` – individual profile detail route.
- `frontend/src/app/compare/page.tsx` – profile comparison page.
- `frontend/src/components/layout/app-shell.tsx` – responsive application navigation shell.
- `frontend/src/components/chat/query-explorer.tsx` – question submission, response explanation, result cards, and local history.
- `frontend/src/components/map/argo-map.tsx` – client-rendered Leaflet map with actual profile marker metadata.
- `frontend/src/components/charts/profile-charts.tsx` – actual-measurement charts; y-axis is pressure in dbar from the stored `depth` field.
- `frontend/src/components/profiles/profile-detail-view.tsx` – individual profile values, charts, and paginated measurement table.
- `frontend/src/lib/api.ts` – typed same-origin frontend fetch helpers; no SQL or provider keys are exposed to the browser.
- `frontend/src/lib/types.ts` – types for summary, profile page/detail, map, orchestration, and history payloads.
- `frontend/src/lib/format.ts` – number and UTC date formatting helpers.

## Data contracts and schemas

- `backend/models/schemas.py` – request/response model definitions for API-facing validation, including hybrid retrieval, query-planning, and orchestration schemas.
- `backend/data/processed/float_metadata.json` – the metadata schema used by semantic retrieval; includes `float_id`, coordinate ranges, and observation windows.
- `argo_profiles` in DuckDB: `file_name`, `float_id`, `profile_number`, `cycle_number`, `datetime`, `latitude`, `longitude`, `depth`, `temperature`, `salinity`.

## Reports and logs

- `backend/logs/inspection_report.txt` – ARGO NetCDF inspection summary.
- `backend/logs/database_validation.txt` – validation summary for the DuckDB database.
- `backend/logs/*.log` – script execution logs.

## Architecture and design docs

- `docs/01_SYSTEM_ARCHITECTURE.md` – project architecture and service boundaries.
- `docs/02_DATA_FLOW.md` – end-to-end ingestion and retrieval flow.
- `docs/04_DATABASE_SCHEMA.md` – schema details and identifier rules.
- `docs/06_HYBRID_RETRIEVAL.md` – hybrid retrieval service design, merge logic, and ranking policy.
- `docs/07_LLM_QUERY_PLANNER.md` – Stage 8A query-planning layer, validation rules, and integration boundaries.
- `docs/08_ORCHESTRATION.md` – Stage 8B orchestration architecture and status model.
- `docs/10_NEXTJS_FRONTEND.md` – Stage 10 dashboard architecture, route contracts, limits, startup, validation, and known limitations.
- `docs/11_API_AND_TOOL_REFERENCE.md` – API and service reference for planner, retrieval, and orchestration layers.
- `docs/11_MCP_SERVER_INTEGRATION.md` – Stage 11 MCP architecture, tools, contracts, execution, testing evidence, and limitations.
- `docs/12_TESTING_AND_VALIDATION.md` – validation notes and test suite execution summary.
- `docs/15_INTERVIEW_PREPARATION.md` – interview-ready summary and implementation notes.
- `docs/16_DEPLOYMENT_AND_PRODUCTION_HARDENING.md` – deployment and production-hardening steps, environment config, startup validation, and verified local-production checks.
- `docs/DECISIONS.md` – design decisions, trade-offs, and known limitations.
