# Setup and Execution Guide

## Project environment

Activate the project virtual environment before running the tests or application code:

`D:\FloatChat\.venv\Scripts\Activate.ps1`

-or-

`D:\FloatChat\.venv\Scripts\python.exe`

## Optional LLM and runtime configuration

Create a local `.env` file in the project root based on `.env.example` if you want to use an external provider or tune local runtime settings. Example:

```env
FLOATCHAT_LLM_PROVIDER=openai_compatible
FLOATCHAT_LLM_MODEL=gpt-4o-mini
FLOATCHAT_LLM_BASE_URL=https://api.openai.com/v1
FLOATCHAT_LLM_API_KEY=your_api_key_here
FLOATCHAT_LLM_TIMEOUT=30
```

Do not commit this file. The project root-level `.gitignore` excludes `.env` files.

A runtime health check is available from the backend root with:

`D:\FloatChat\.venv\Scripts\python.exe -c "from health import get_runtime_health; print(get_runtime_health())"`

## Validation suite

Run the project regression suite with:

`D:\FloatChat\.venv\Scripts\python.exe -m pytest backend/tests -q`

## Run the Stage 10 dashboard

The Next.js app is in `D:\FloatChat\frontend`. Install the dependencies from that directory, then start the dev server:

```powershell
Set-Location D:\FloatChat\frontend
npm install
npm run dev
```

The Next.js API routes expect the project Python environment at `D:\FloatChat\.venv\Scripts\python.exe`, installed backend dependencies, and the processed DuckDB database. `/api/query` also requires the existing Chroma index for semantic retrieval. The data-exploration endpoints are read-only and use fixed operations; they do not accept SQL from the browser.

Verify the production frontend compilation from `D:\FloatChat\frontend`:

```powershell
npm run lint
npm run build
npm start
```

The dashboard uses:

- `/` for the dataset overview,
- `/explorer` for natural-language retrieval,
- `/map` for bounded map exploration,
- `/profiles` and `/profiles/detail` for profile listing and individual measurements,
- `/compare` for plotting selected profiles, and
- `/about` for data notes.

The local API bridge launches a Python subprocess per request; it is intended for local integration rather than production deployment. OpenStreetMap tile loading requires network access.

## Run the Stage 11 MCP server

Install backend dependencies in the project virtual environment, including `mcp>=2.3.0,<3.0`. From PowerShell:

```powershell
Set-Location D:\FloatChat\backend
..\.venv\Scripts\python.exe -m mcp_server.server
```

The server speaks MCP over stdio and should be launched by an MCP client/host, not opened as a browser endpoint. It uses the processed DuckDB database configured for the backend. Its five read-only tools and limits are documented in `docs/11_MCP_SERVER_INTEGRATION.md`. No API key, LLM, Chroma collection, or arbitrary SQL is needed for these tools.

## Minimal execution flow for the verified stack

1. Ensure the archive and processed data exist.
2. Run the query planner or orchestration service.
3. Validate any LLM output against the existing stage schemas.
4. Invoke the hybrid retrieval engine only for valid plans.
5. Review the returned status and ranking metadata.

## Result interpretation

- `success` — retrieval returned results,
- `success_zero_results` — retrieval ran but no candidates matched,
- `invalid_query` — malformed or invalid values were provided,
- `clarification_required` — the location or parameter requires human clarification,
- `retrieval_failed` — execution itself failed and no result should be trusted.
