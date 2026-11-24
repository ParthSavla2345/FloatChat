# Testing and Validation

## Regression suite

The relevant backend regression suite is executed with:

`D:\FloatChat\.venv\Scripts\python.exe -m pytest backend/tests -q`

## Current execution result

The verified backend regression suite after Stage 12 is:

- `83 passed, 20 warnings` in the complete project regression suite.
- The warnings are existing `Pandas4Warning` messages about `DataFrame.drop(inplace=...)` in `spatial_temporal_service.py`; they do not originate from Stage 12.
- `backend/tests/test_mcp_server.py`: `16 passed` in the focused Stage 11 suite.
- `backend/tests/test_runtime_health.py`: `3 passed` in the startup-validation suite.
- `frontend`: `npm run build` passed successfully with the production build.

## Coverage

The suite includes:

- semantic retrieval tests,
- spatial/temporal retrieval tests,
- hybrid retrieval tests,
- query planner tests,
- orchestration tests,
- profile explorer and controlled DuckDB tests,
- MCP tool, protocol, and stdio tests.

## Validation goals

- confirm planner-to-retrieval integration,
- confirm invalid and ambiguous queries do not execute retrieval,
- confirm valid queries still reach the hybrid engine,
- confirm final response schemas are consistent with the actual service outputs.
- exercise all five MCP tools against controlled DuckDB fixtures through the official in-process MCP client.
- confirm the standalone stdio server starts and advertises the same tools.
- confirm invalid MCP input and service failures are errors rather than successful empty results.
- confirm configuration validation and startup health checks fail fast on missing required resources without changing the existing retrieval behavior.

## Stage 11 verification boundary

The tests verify handler behavior and MCP protocol calls on controlled data, plus stdio process startup and tool discovery. A separate local stdio smoke test invoked the tools against the recovered DuckDB. External MCP host configuration, remote deployment, and authentication are not verified. Existing Stage 10 live dashboard/API checks remain prior verified evidence and were not repeated as part of Stage 11.
