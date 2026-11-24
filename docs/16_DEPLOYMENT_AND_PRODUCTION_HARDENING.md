# Deployment and Production Hardening

## Scope

This document covers the Stage 12 hardening work applied to the verified OceanIQ stack without altering the completed retrieval, semantic, hybrid, planner, orchestration, dashboard, or MCP logic. The project remains compatible with the existing local development flow and the recovered DuckDB + Chroma artifacts.

## Audit summary

The repository already includes:

- a read-only DuckDB database and a Parquet observation table,
- a persisted Chroma semantic index,
- a Next.js dashboard with API routes that spawn the local Python environment,
- a read-only stdio MCP server,
- a staged Python service layer without a dedicated server process or external deployment runtime.

The main operational gap was configuration and startup validation rather than retrieval logic. The backend depended on hardcoded local paths and the frontend API bridge assumed a single local Python install. There was no explicit runtime health check or a clear `.env.example` representing the supported environment variables.

## Production configuration

The system now centralizes runtime settings in `backend/config.py`:

- `FLOATCHAT_ENV`
- `FLOATCHAT_ARCHIVE_DIR`
- `FLOATCHAT_DATA_DIR`
- `FLOATCHAT_PROCESSED_DIR`
- `FLOATCHAT_LOGS_DIR`
- `FLOATCHAT_CHROMA_DIR`
- `FLOATCHAT_DUCKDB_PATH`
- `FLOATCHAT_PARQUET_PATH`
- `FLOATCHAT_METADATA_PARQUET`
- `FLOATCHAT_METADATA_JSON`
- `FLOATCHAT_VALIDATION_REPORT`
- `FLOATCHAT_BACKEND_HOST`
- `FLOATCHAT_BACKEND_PORT`
- `FLOATCHAT_REQUEST_TIMEOUT`
- `FLOATCHAT_LLM_PROVIDER`
- `FLOATCHAT_LLM_MODEL`
- `FLOATCHAT_LLM_BASE_URL`
- `FLOATCHAT_LLM_API_KEY`
- `FLOATCHAT_LLM_TIMEOUT`
- `NEXT_PUBLIC_API_BASE_URL`
- `OCEANIQ_PYTHON_PATH`

The project includes `.env.example` and `frontend/.env.example` to make these settings explicit while still ignoring real secrets via `.gitignore`.

## Runtime health checks

`backend/health.py` adds a safe read-only health-report API:

```python
from health import get_runtime_health
print(get_runtime_health())
```

The health report checks:

- required dataset paths,
- the DuckDB database file,
- the processed parquet file,
- the runtime environment,
- optional LLM provider configuration.

This does not attempt to rebuild the dataset or run write operations.

## Python subprocess decision

The existing architecture uses a per-request Python subprocess from the Next.js API routes. This is not a production deployment architecture, but it remains the simplest reliable option for this project because:

- the Python retrieval stack is already implemented and validated,
- the backend does not currently expose a dedicated HTTP server,
- the project is designed to run locally and on a personal machine with limited resources,
- a larger persistent worker would add operational complexity without direct user requirement.

The code now supports overriding the Python interpreter via environment variables as a practical production-hardening measure, without changing the underlying retrieval logic.

## MCP and security notes

The read-only MCP server remains unchanged in behavior and continues to rely on the vetted `ProfileExplorerService`. It still does not expose arbitrary SQL or unrestricted database access. Logging and configuration remain local-only and avoid storing secrets.

## Frontend verification

The Next.js app was verified with a production build:

```powershell
Set-Location D:\FloatChat\frontend
npm run build
```

Result: successful production build, valid static/dynamic route generation, and no TypeScript errors.

## Backend verification

The backend regression suite was run with:

```powershell
Set-Location D:\FloatChat
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

Result: `83 passed, 20 warnings`.

The warnings remain the existing Pandas 4 deprecations in `backend/services/spatial_temporal_service.py` and are not caused by the Stage 12 configuration changes.

## Known limitations

- No dedicated external backend server or public deployment was configured in this stage.
- The Next.js API routes still use local Python subprocess execution rather than a persistent service worker.
- External MCP host configuration and remote client deployment remain unverified.
- LLM support remains optional, and the rule-based planner remains the deterministic fallback.
- A production deployment target was not selected, so no cloud-provider-specific configuration was added.

## Verification status

- Locally verified: yes
- Production build verified: yes
- Deployment configured: no external deployment target selected
- External MCP-host verified: no
- Authentication verified: no
