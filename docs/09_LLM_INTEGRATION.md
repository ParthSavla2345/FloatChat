# LLM Integration

## Objective

The optional LLM interpretation layer exists to help users express complex ARGO queries in natural language while retaining the verified retrieval stack as the source of truth. The LLM does not execute SQL, call DuckDB directly, or bypass the rule-based planner and retrieval safeguards.

## Provider abstraction

`backend/services/llm_service.py` introduces a provider-agnostic service with:

- `BaseLLMProvider` for interface standardization,
- `MockLLMProvider` for deterministic automated tests,
- `OpenAICompatibleProvider` for external HTTP-based providers,
- `LLMService` as the validated orchestration wrapper.

Supported configuration knobs are environment variables:

- `FLOATCHAT_LLM_PROVIDER` (`mock` or `openai_compatible`)
- `FLOATCHAT_LLM_MODEL`
- `FLOATCHAT_LLM_BASE_URL`
- `FLOATCHAT_LLM_API_KEY`
- `FLOATCHAT_LLM_TIMEOUT`

The project retains a root-level `.gitignore` entry for `.env` and `.env.*` files so API keys are not committed to source control.

## Structured output contract

The LLM output is interpreted as a `QueryPlan`-compatible payload. The base contract includes:

- `original_query`
- `semantic_query`
- `parameters`
- `region`
- `latitude`
- `longitude`
- `radius_km`
- `bounding_box`
- `start_date`
- `end_date`
- `top_k`
- `interpretation_notes`
- `validation_warnings`

The `LLMPlanResult` model adds provider metadata, validation warnings, status, fallback usage, and error reporting.

## Validation and fallback rules

The LLM output must pass both schema validation and project-domain checks before it is accepted:

- unsupported parameters are rejected or flagged,
- invalid coordinates are rejected,
- invalid date ranges are rejected,
- ambiguous or unsupported regions trigger clarification status,
- invalid JSON or provider errors result in fallback rather than guessing,
- missing required fields trigger fallback when a deterministic planner is available.

The fallback path always reuses the verified rule-based planner, keeping a deterministic baseline available even when the LLM is unavailable or fails.

## Integration with Stage 8B

The orchestration layer calls the rule-based planner first and then optionally invokes the LLM service when `use_llm=True`. The LLM plan is only accepted if it validates cleanly; otherwise, the system returns a structured invalid or clarification status without attempting retrieval.

The operational flow is:

User question -> optional LLM interpretation -> validated structured query -> Stage 8B orchestration -> Stage 7 hybrid retrieval

## Reliability constraints

- no direct SQL execution,
- no unrestricted DB access,
- no hidden provider access in the retrieval services,
- no live API calls in the automated test suite,
- no dependency on a local GPU or server beyond an outbound HTTP-compatible API endpoint.

## Limitations

- This is a rule-validated optional wrapper, not a general autonomous query agent.
- Provider-specific behavior and response schemas differ by vendor and must remain constrained.
- The LLM output is only as good as its validation; unsupported or ambiguous geography is never guessed.
