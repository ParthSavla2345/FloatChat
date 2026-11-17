# FloatChat Project Status

## Project audit summary

The project is in a verified, staged recovery state with a clear split between completed and pending work.

### Verified functionality

- Stage 1: NetCDF inspection and extraction — Completed and verified
- Stage 2: Parquet validation and data quality checks — Completed and verified
- Stage 3: DuckDB schema and SQL query validation — Completed and verified
- Stage 4: Float and profile metadata generation — Completed and verified
- Stage 5: Semantic retrieval — Completed and verified
- Stage 6: Spatial and temporal retrieval — Completed and verified
- Stage 7: Hybrid retrieval engine — Completed and verified
- Stage 8A: Natural-language query planning — Completed and verified
- Stage 8B: Query orchestration — Completed and verified
- Stage 9: LLM interpretation layer — Completed and verified
- Stage 10: Interactive Next.js dashboard — Implemented and locally verified against actual ARGO data
- Stage 11: Read-only MCP server — Implemented and verified with controlled-data tool calls and stdio discovery

### Unverified functionality

- External desktop/remote MCP client configuration, deployment, and authentication are not verified
- Automated browser tests are not configured; Stage 10 UI flows were exercised manually in the local browser

### Stage 12 production-hardening status

- Centralized environment configuration is implemented and validated.
- Runtime health checks provide startup-validation warnings without requiring remote LLM access.
- Frontend production build is verified successfully.
- Backend regression suite remains green after the configuration hardening changes.

## Verified evidence

- `backend/logs/extract_profiles.log` shows 706 NetCDF files processed successfully with 68,470,264 rows written to `backend/data/processed/argo_profiles.parquet`.
- `backend/logs/build_duckdb.log` shows the `argo_profiles` table created and imported successfully in ~136 seconds.
- `backend/logs/database_validation.txt` confirms row counts, ranges, and duplicate checks were produced for the built DuckDB database.
- `backend/logs/generate_metadata.log` shows metadata generation completed for 706 floats and the JSON/parquet outputs were written.
- `backend/tests/test_semantic_index.py` passes: 3/3 tests passed.
- `backend/tests/test_spatial_temporal.py` passes: 9/9 tests passed in the focused Stage 6 suite.
- `backend/tests/test_hybrid_retrieval.py` passes: 12/12 tests passed in the Stage 7 hybrid retrieval suite.
- `backend/tests/test_query_planner.py` passes: 10/10 tests passed in the Stage 8A planner suite.
- `backend/tests/test_orchestration.py` passes: 11/11 tests passed in the Stage 8B orchestration suite.
- Full backend regression suite passes: 80/80 tests passed, with 20 non-blocking Pandas 4 deprecation warnings from the existing spatial/temporal service.
- The semantic index was built successfully and the persisted collection count is 706 documents.
- A live semantic query against the Chroma collection returned valid results for the Bay of Bengal temperature-profile prompt.
- Stage 6 runtime checks confirm spatial bounding-box queries, radius queries, nearest-float grouping, temporal date-range queries, and monthly filters all operate on the recovered DuckDB dataset.
- Stage 7 runtime checks confirm semantic + spatial + temporal fusion, deterministic ranking, and duplicate suppression all function correctly.
- `frontend`: `npm run lint` passed and `npm run build` passed for all App Router pages and API routes.
- Live production API checks returned actual dataset metrics: 68,470,264 observation rows, 52,240 distinct `(file_name, profile_number)` profiles, and 706 project float keys.
- Live API checks returned filtered profile pages, actual coordinates, and UTC-normalized measurements for a real profile; its temperature/salinity/pressure charts rendered in the browser.
- Live map API returned actual profile locations under region, parameter, identifier, and coordinate-range filters; the browser rendered interactive Leaflet markers.
- A live two-profile browser comparison displayed actual temperature/salinity overlays and calculated coordinate/time differences; missing salinity data was identified for the profile where unavailable.
- A live POST to `/api/query` returned `retrieval_status=success` and one result for “Find temperature observations in the Arabian Sea.”
- The map returned 1,500 unfiltered locations; filtering Bay of Bengal profiles by temperature availability returned 1,275 real profiles and rendered interactive markers.
- A 390px-wide browser viewport rendered profile details, charts, and responsive navigation.
- A two-profile comparison showed actual values, a 586.7 km coordinate distance, a 0.1 hour time difference, and a missing-salinity notice for a profile without salinity measurements.
- Invalid map-coordinate and profile-date filters surfaced validation errors. The UI was corrected to avoid simultaneously showing an erroneous empty-results message.
- Browser checks exercised overview, query submission, profile listing/detail, map filtering/selection, charts, comparison, and empty/error states.
- `backend/tests/test_mcp_server.py` passes: 16 focused tests cover all five tools, validation/error cases, structured results, controlled in-process MCP calls, and stdio server discovery.
- The official MCP Python SDK client discovered the five tools over stdio; in-process MCP protocol calls exercised each tool against controlled DuckDB fixtures.
- A live stdio MCP smoke test against the recovered DuckDB returned a successful dataset summary (68,470,264 observation rows), two returned temperature profiles, successful float details and profile observations, and a non-error comparison result; an out-of-range latitude was rejected as an MCP tool error.

## Current implementation status

- `backend/config.py` provides the shared `settings` singleton expected by the ingestion and service layer.
- The processed dataset and DuckDB artifacts are present and readable.
- `backend/data/chroma/` contains a verified Chroma collection for the recovered float metadata.
- `backend/services/spatial_temporal_service.py` provides bbox, radius, region, nearest-float, date-range, month, period-comparison, and date-bounds retrieval services.
- `backend/services/hybrid_service.py` merges Chroma semantic results with DuckDB spatial and temporal constraints under a deterministic scoring model.
- `backend/services/query_planner.py` converts natural-language questions into validated structured queries compatible with the Stage 7 hybrid service.
- `backend/services/orchestration_service.py` coordinates the planner and retrieval engine and returns a structured explainability response for the caller.
- `backend/services/llm_service.py` provides an optional provider-agnostic LLM interpretation layer with a mock provider, environment-based provider configuration, validation, and rule-based fallback behavior.
- `backend/services/profile_explorer_service.py` provides parameterized, read-only dataset summaries, bounded profile pagination, map coordinates, and profile measurements.
- `backend/mcp_server/server.py` exposes five read-only MCP tools over stdio; `backend/mcp_server/tools.py` validates bounded inputs and reuses the shared profile explorer service.
- `backend/mcp_server/schemas.py` defines typed MCP result contracts; exact project-level float details are aggregated by `ProfileExplorerService.get_float_details()`.
- `frontend/src/app/page.tsx` is the data-backed dashboard overview; `frontend/src/app/explorer/page.tsx` hosts the conversational query interface.
- `frontend/src/app/api/query/route.ts` bridges the verified Python backend and the Next.js UI without duplicating the retrieval logic.
- `frontend/src/app/api/data/[action]/route.ts` exposes bounded read-only summary, profile-list, map, and individual-profile operations.
- `frontend/src/app/map/page.tsx`, `frontend/src/app/profiles/page.tsx`, `frontend/src/app/profiles/detail/page.tsx`, and `frontend/src/app/compare/page.tsx` implement map, profile browsing, profile details, and comparison.
- The semantic retrieval stack is installed in the project venv and validated by automated tests and direct live queries.
- UTC timestamps are normalized consistently using the source observation time, with the raw NetCDF `PLATFORM_NUMBER` identified as the authoritative ARGO float identifier source when present.

## Known limitation

The processed DuckDB table stores a project-derived `float_id` value generated during extraction, and it is not guaranteed to be the raw NetCDF `PLATFORM_NUMBER` WMO identifier. The actual source variable is `PLATFORM_NUMBER` from the original NetCDF files; if a downstream consumer requires a true WMO identifier, it must be recovered from that source field or backfilled explicitly. Filenames are not treated as float IDs. The MCP server reports the distinction and does not claim that `float_id` is raw WMO identity.

The processed table does not contain QC flags, so dashboard pages and MCP results explicitly mark QC as unavailable. MCP tools are read-only and bounded; no arbitrary SQL, ingestion, LLM, or Chroma operations are exposed. The server was locally exercised against the recovered DuckDB; external MCP client configuration, authentication, and remote deployment remain unverified. Map tiles depend on external OpenStreetMap access. The frontend-to-Python bridge starts a Python subprocess per request and is locally verified, not production deployment infrastructure.

## Immediate next stage

Stage 11 is verified locally. Stage 12 is now implemented as lightweight production hardening: environment-driven configuration, startup validation, and runtime health checks. The project remains compatible with the existing local data pipeline and verified retrieval stack.

## Notable files

- `backend/config.py` – central runtime configuration and shared settings object
- `backend/ingestion/extract_profiles.py` – NetCDF extraction to parquet
- `backend/ingestion/build_duckdb.py` – DuckDB materialization
- `backend/validate_database.py` – database validation report generator
- `backend/generate_metadata.py` – float metadata generation
- `backend/services/duckdb_service.py` – read-only SQL execution layer
- `backend/services/semantic_service.py` – semantic retrieval adapter
- `backend/services/spatial_temporal_service.py` – spatial and temporal retrieval layer
- `backend/services/hybrid_service.py` – hybrid retrieval service combining semantic and structured filtering
- `backend/services/query_planner.py` – Stage 8A natural-language query planner that produces validated Stage 7-compatible query objects
- `backend/services/orchestration_service.py` – Stage 8B orchestration layer connecting the planner to the hybrid retrieval engine
- `backend/services/llm_service.py` – Stage 9 optional LLM interpretation layer with provider abstraction, validation, and fallback behavior
- `backend/services/profile_explorer_service.py` – read-only dashboard summary, profile listing, map marker, and individual profile data service
- `backend/mcp_server/server.py` – independently runnable stdio MCP server and tool registration
- `backend/mcp_server/tools.py` – validated bounded wrappers for profile search, float details, observations, comparison, and dataset summary
- `backend/mcp_server/schemas.py` – typed MCP tool result schemas
- `backend/tests/test_profile_explorer.py` – focused profile explorer query, validation, pagination, and UTC tests
- `backend/tests/test_mcp_server.py` – MCP tool, input validation, error handling, protocol, and stdio tests
- `backend/requirements.txt` – includes the official MCP Python SDK dependency
- `frontend/src/components/` – shared navigation, chat, Leaflet map, profile, and scientific chart components
- `frontend/src/lib/` – typed frontend API client, response types, and UTC/number formatting
- `frontend/src/app/api/data/[action]/route.ts` – bounded Next.js API bridge to profile explorer operations
- `docs/10_NEXTJS_FRONTEND.md` – Stage 10 dashboard structure, data contracts, validation, and limitations
- `docs/11_MCP_SERVER_INTEGRATION.md` – Stage 11 server architecture, tool contracts, execution, verification, and limits
- `backend/ingestion/build_chroma_index.py` – index build script for semantic retrieval
- `backend/tests/test_spatial_temporal.py` – Stage 6 verification suite
- `backend/tests/test_hybrid_retrieval.py` – Stage 7 hybrid retrieval verification suite
- `backend/tests/test_query_planner.py` – Stage 8A query-planning verification suite
- `backend/tests/test_orchestration.py` – Stage 8B orchestration verification suite

## Last verified completed stage

Stage 11: the read-only MCP server is verified with all five tools called through the official in-process MCP client against controlled DuckDB data, stdio transport discovery, and a live local stdio smoke test against the recovered database. External MCP client deployment remains unverified.
