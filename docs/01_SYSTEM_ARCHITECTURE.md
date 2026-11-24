# System Architecture

## Overview

FloatChat recovers an ARGO-derived NetCDF archive, flattens the profile observations into parquet, materializes the data into DuckDB, generates float-level metadata, indexes semantic summaries in Chroma, and exposes read-only retrieval services for later application and agent layers.

## Layered architecture

1. Source layer
   - `archive/*.nc` contains raw NetCDF files from the ARGO project.
   - The authoritative float identifier in the source data is `PLATFORM_NUMBER`.
   - Filenames and project-derived `float_id` values are not treated as canonical WMO identifiers.

2. Extraction layer
   - `backend/ingestion/extract_profiles.py` reads each NetCDF file and expands profile-level observations into a standard row-per-observation table.
   - Each row includes `file_name`, `float_id`, `profile_number`, `cycle_number`, `datetime`, `latitude`, `longitude`, `depth`, `temperature`, and `salinity`.
   - UTC timestamps are preserved using `datetime` values normalized to timezone-aware UTC.

3. Storage layer
   - `backend/ingestion/build_duckdb.py` creates the persistent `argo_profiles` table in `backend/data/processed/floatchat.duckdb`.
   - `backend/services/duckdb_service.py` provides a read-only SQL layer that rejects writes and only permits `SELECT`/`WITH ... SELECT` queries.

4. Metadata layer
   - `backend/generate_metadata.py` aggregates float-level summaries from the observation table.
   - Metadata includes observation windows, bounding coordinate ranges, and variable availability.

5. Semantic layer
   - `backend/ingestion/build_chroma_index.py` creates text summaries from metadata and stores them in Chroma.
   - `backend/services/semantic_service.py` exposes semantic retrieval over the vector store.

6. Retrieval layer
   - `backend/services/spatial_temporal_service.py` exposes spatial and temporal queries.
   - `backend/services/hybrid_service.py` merges semantic results with structured filters and produces explainable ranking.
   - `backend/services/query_planner.py` translates natural-language scientific questions into validated structured retrieval payloads before the hybrid service is invoked.
   - This layer is intentionally decoupled from the LLM and should be reused by later orchestration or MCP services.
7. Profile exploration layer
   - `backend/services/profile_explorer_service.py` provides bounded read-only dataset summaries, profile-level pages, map locations, and individual measurement levels over DuckDB.
   - Profile identity is `(file_name, profile_number)`; the project-level `float_id` and raw NetCDF `PLATFORM_NUMBER` are distinct concepts.
   - SQL values are bound parameters; the browser cannot pass SQL or access unrestricted database operations.
8. Agent integration layer
   - `backend/mcp_server/server.py` exposes a separate read-only MCP server over stdio.
   - `backend/mcp_server/tools.py` validates bounded requests and calls `ProfileExplorerService`; it does not expose SQL, ingestion, Chroma, or LLM operations.
   - MCP profile identity is `(source_file, profile_number)`; project `float_id` and raw NetCDF `PLATFORM_NUMBER` remain distinct.
9. Presentation layer
   - `frontend/` is a Next.js App Router application with overview, query explorer, map, profile list/detail, comparison, and data notes.
   - `/api/query` calls the existing Python orchestration layer; `/api/data/[action]` exposes only allowlisted profile-explorer methods.
   - Both route families invoke local Python processes; Stage 10 does not introduce a persistent Python HTTP service.

## Architectural notes

- `float_id` is a processed-project identifier used inside the recovered pipeline.
- The actual raw NetCDF variable `PLATFORM_NUMBER` remains the authoritative source when a true ARGO float identifier is required.
- All project service code shares `backend/config.py` via the `settings` singleton.

## Stage 6 responsibilities

Stage 6 adds:

- bounding-box spatial filtering,
- radius-based coordinate search,
- nearest-float grouping,
- date-range and month-based filtering,
- last-N-day and last-N-month windows,
- period comparison, and
- earliest/latest timestamp bounds.

## Stage 7 responsibilities

Stage 7 adds:

- semantic + structured retrieval fusion,
- deterministic hybrid ranking,
- duplicate suppression by `float_id`,
- parameter-aware filtering,
- explainable retrieval metadata, and
- validation of end-to-end engine behavior without an LLM.

## Stage 8A responsibilities

Stage 8A adds:

- natural-language parsing of scientific queries,
- extraction of parameters, regions, coordinates, radii, and dates,
- validation of constraints before execution,
- conversion into a Stage 7-compatible hybrid query,
- preservation of the user’s original question while keeping the planner independent of the LLM.

## Stage 8B responsibilities

Stage 8B adds:

- orchestration between the planner and the hybrid retrieval engine,
- status handling for valid, zero-result, invalid, clarification-required, and failed retrieval flows,
- explainable structured response packaging,
- no LLM or MCP dependency and no duplicate retrieval logic.

## Stage 9 responsibilities

Stage 9 adds an optional LLM interpretation layer that:

- converts a user’s natural-language question into a Stage 8A-compatible structured plan,
- validates the generated output against the existing query schema and project rules,
- keeps a provider abstraction isolated from the retrieval stack,
- falls back to the deterministic planner when the provider is unavailable, times out, or responds with invalid JSON,
- never executes SQL or bypasses the retrieval and validation layers.

## Stage 10 responsibilities

Stage 10 adds an interactive scientific-data dashboard and local Next.js API bridge that:

- exposes verified summary, spatial, profile, measurement, and query data in responsive browser pages,
- calls `OrchestrationService` for conversational retrieval and `ProfileExplorerService` for bounded, read-only exploration,
- renders planner interpretation, enforced filters, ranking information, actual profile coordinates, and measurement values,
- distinguishes the project float key from profile identity and does not claim QC or raw WMO identity when these are absent,
- keeps the web layer separate from the retrieval engine and does not make the browser submit SQL.

The profile explorer caps profile pages at 200 rows, map payloads at 2,000 profiles, and individual measurement responses at 10,000 levels. The UI applies smaller limits for responsiveness. Each API request starts a Python subprocess; production serving, authentication, and persistent backend connections are not Stage 10 deliverables.

## Stage 11 responsibilities

Stage 11 adds an independently runnable, read-only MCP server with five tools: profile search, exact project-float aggregates, individual profile observations, comparisons, and dataset summary. It shares the profile explorer service and its DuckDB connection. Search returns at most 200 profiles, observation responses at most 2,000 levels, and comparisons accept 2–4 profiles with at most 2,000 returned levels per profile. Comparison returns separate measured series and does not interpolate.

The server is launched using the official MCP Python SDK over stdio. Automated verification covers each tool against controlled DuckDB fixtures and discovers all tools through the stdio transport. A local stdio smoke test also invoked the tools against the recovered database. Deployment with an external MCP host and authentication have not been verified. See `docs/11_MCP_SERVER_INTEGRATION.md`.

## Execution instructions

1. Activate the project virtual environment.
2. Ensure the source archive and processed outputs exist.
3. Run the validation/test suite with:
   - `.venv\Scripts\python.exe -m pytest backend/tests -q`

## Diagram

```mermaid
flowchart LR
    A[NetCDF archive] --> B[extract_profiles]
    B --> C[argo_profiles parquet]
    C --> D[DuckDB argo_profiles]
    D --> E[metadata generation]
    E --> F[semantic summaries]
    F --> G[Chroma collection]
    D --> H[spatial_temporal_service]
    G --> I[semantic_service]
    H --> J[hybrid_service]
    I --> J
    K[natural_language_query] --> L[query_planner]
    K --> O[optional LLM service]
    O --> L
    L --> M[orchestration_service]
    M --> J[hybrid_service]
    J --> N[structured response]
    UI[Next.js dashboard] --> Q[/api/query]
    Q --> M
    UI --> R[/api/data allowlist]
    R --> X[ProfileExplorerService]
    X --> D
    O -. fallback .-> L
    MCPC[MCP host] <-->|stdio| MCP[read-only MCPServer]
    MCP --> T[validated MCP tools]
    T --> X
```
