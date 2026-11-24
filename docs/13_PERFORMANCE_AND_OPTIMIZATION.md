# Performance and Optimization

## Core design principle

The retrieval stack remains CPU-efficient and read-only:

- Chroma stores the semantic metadata index,
- DuckDB stores the large observation table,
- only structured, parameterized queries are executed,
- the LLM layer is optional and intentionally lightweight.

## Efficiency characteristics

- Query planning is deterministic and rule-based; it does not require model inference by default.
- The hybrid retrieval engine limits result counts through `max_results` and uses the Stage 7 ranking path only after structured filters are applied.
- DuckDB queries remain parameterized and intentionally focused on the necessary subset of observation rows.
- The LLM layer is not allowed to run unrestricted database queries or load the observation dataset into memory.

## Cost and latency

- The mock provider is zero-cost and deterministic for automated tests.
- External provider calls may incur API cost and network latency depending on the selected model and provider.
- The project keeps latency bounded by using a small timeout budget and a strict validation-and-fallback contract.

## Monitoring and warnings

- provider failures are explicitly surfaced as errors and do not silently pass through,
- invalid or unsupported LLM outputs are rejected before retrieval begins,
- retrieval still uses the verified rule-based planner baseline when provider execution fails.

## Known performance limitations

- The LLM layer introduces network latency if enabled with an external provider.
- Large Chroma and DuckDB collections still depend on the underlying dataset size rather than an in-memory cache.
- The retrieval engine remains float-level rather than profile-level for the supported dataset design.
