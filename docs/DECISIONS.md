# Design Decisions

## Why retain Chroma and DuckDB

The system keeps Chroma for semantic retrieval and DuckDB for analytical filtering because they serve different retrieval responsibilities:

- Chroma is optimized for semantic similarity search over metadata summaries.
- DuckDB is optimized for fast, parameterized SQL over the large observation table.
- This separation preserves the project’s staged pipeline and avoids unnecessary re-indexing or migration work.

## Why enforce filters before ranking

The hybrid engine only ranks candidates that satisfy the requested spatial and temporal constraints. This keeps retrieval explainable and prevents the system from returning results that merely "look relevant" but are outside the requested region or time window.

## Why use `float_id` for merge keys

The semantic collection stores float-level metadata keyed by `float_id`, and DuckDB structured queries are naturally grouped by float. Using `float_id` is the stable join key across both retrieval systems, while `file_name` remains a provenance label and `PLATFORM_NUMBER` remains the raw source identifier when needed.

## Why keep the pipeline independent of the LLM

The retrieval engine is intentionally non-LLM. It accepts structured query inputs and yields explainable results without requiring an LLM planner. This creates a stable service layer usable by later orchestrators without introducing hidden model behavior into retrieval decisions.

## Why use a rule-based query planner before LLM orchestration

The Stage 8A planner is intentionally deterministic and conservative. It validates supported regions, parameters, dates, and coordinates before the retrieval layer runs. This keeps the system reliable, explainable, and compatible with the existing hybrid engine while avoiding fabricated geographic or temporal assumptions.

## Why keep orchestration separate from retrieval logic

The Stage 8B service is deliberately thin: it coordinates the planner and the hybrid engine but does not duplicate filtering, ranking, or retrieval behavior. This preserves the project’s architectural boundary, reduces the chance of inconsistent logic, and keeps the retrieval stack testable as a standalone component.

## Why make LLM interpretation optional and validated

The Stage 9 LLM layer exists only to help interpret natural-language questions. It is not a trusted execution layer and never bypasses the existing validation, planner, or retrieval stack. By making the provider optional and always validating the model output, the project keeps a deterministic baseline while still allowing an LLM to propose structured plans when available.

## Why keep the dashboard as a thin presentation layer

The Stage 10 Next.js app calls the existing Python orchestration service for natural-language retrieval and a separate read-only `ProfileExplorerService` for summary/profile/map/detail data. Ranking, retrieval, and SQL stay in the backend. The browser only consumes fixed API contracts and cannot submit SQL.

The profile explorer groups observations by `(file_name, profile_number)` for individual profile access, preserving `float_id` as a different project-level key. Queries are parameterized and bounded to avoid sending the full observation table to the browser. The API bridge uses a Python subprocess per request to fit the current local project structure without introducing a second persistent server.

## Why show scientific data limitations in the UI

The processed table has no QC columns and does not retain a separate `PLATFORM_NUMBER`. The interface therefore labels QC as unavailable, labels `float_id` as a project key, and preserves source filename/profile number as the profile identity. The stored `depth` field comes from NetCDF `PRES`, so charts use pressure units and do not claim a geometric-depth conversion. Actual-value plots do not interpolate missing observations.

## Why the MCP server is a separate read-only adapter

Stage 11 uses the official MCP Python SDK over stdio and delegates all data work to `ProfileExplorerService`. This reuses the validated parameterized DuckDB operations without exposing arbitrary SQL, the LLM, ingestion, or unrestricted retrieval internals. Typed response models and explicit result caps keep the agent-facing boundary predictable.

Float detail aggregation keys only on the exact processed project `float_id`; profile retrieval and comparison key on `(file_name, profile_number)`. The tool responses preserve source filenames as provenance and state that a separate raw `PLATFORM_NUMBER` is not available in the processed schema. Comparison returns independent actual measurements, not interpolated or aligned scientific values.

MCP verification is deliberately scoped: all tools are exercised by the official in-process client using controlled DuckDB fixtures, and the standalone stdio server is started to verify tool discovery. External MCP host configuration, authentication, deployment, and live MCP tool queries over the full dataset remain unverified.

## Why keep the runtime configuration environment-driven but lightweight

The project now reads deployment settings from environment variables instead of hardcoded local paths. This makes the same verified retrieval stack easier to run on a different workstation or a controlled deployment without changing the core scientific logic. The configuration remains intentionally simple: no extra service container, no database migration layer, and no secret material in the repository.

## Why prefer a validated local-process bridge over a larger service abstraction

The existing Next.js API routes are local-process call wrappers around the validated Python retrieval stack. This keeps the architecture narrow and predictable for a laptop-sized deployment while preserving the exact retrieval logic already tested in the backend. A persistent worker or full backend service would add operational complexity without improving the verified behavior for the current project scope.

## Known limitations

- Raw WMO identifiers require reading `PLATFORM_NUMBER` from the original NetCDF source.
- The semantic store represents floats, not individual observation rows.
- Parameter coverage is limited to the variables present in the flattened observation table.
- Ranking remains deterministic but is intentionally transparent rather than a complex learned model.
- Dashboard APIs are local-process bridges, not a production deployment architecture; each request can incur Python startup latency.
- Map basemap tiles require network access to OpenStreetMap; the data coordinates are served from DuckDB.
- External deployment targets and remote MCP client hosting remain outside the verified local configuration.

## Operational notes

- All retrieval services remain CPU-efficient by reusing the persisted Chroma collection and the existing DuckDB table.
- Parameterized queries are kept in place to reduce injection risk and preserve the read-only database model.
- The hybrid service is designed to be a stable foundation for future orchestration layers.
