"""Optional LLM interpretation layer for OceanIQ.

This service intentionally does not execute database queries or issue
unrestricted SQL. It translates a user question into the same structured
query contract used by the rule-based planner and the Stage 7 hybrid layer.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error, request

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

from models.schemas import LLMPlanResult, QueryPlan
from services.query_planner import QueryPlanner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class LLMProviderError(RuntimeError):
    """Raised when the configured LLM provider fails."""


class LLMTimeoutError(LLMProviderError):
    """Raised when the provider exceeds its timeout budget."""


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider exceeds a rate limit."""


class BaseLLMProvider:
    """Abstract provider interface."""

    def __init__(self, model: str | None = None):
        self.model = model or "generic-model"

    @property
    def provider_name(self) -> str:
        return self.__class__.__name__.replace("LLMProvider", "").lower()

    def generate(self, question: str) -> str:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    """Deterministic test provider that avoids real API access."""

    def __init__(
        self,
        model: str | None = None,
        *,
        invalid_json: bool = False,
        missing_fields: bool = False,
        invalid_coordinates: bool = False,
        unsupported_parameter: bool = False,
        timeout: bool = False,
        rate_limited: bool = False,
        response_payload: str | dict[str, Any] | None = None,
    ) -> None:
        super().__init__(model or "mock-model")
        self.invalid_json = invalid_json
        self.missing_fields = missing_fields
        self.invalid_coordinates = invalid_coordinates
        self.unsupported_parameter = unsupported_parameter
        self.timeout = timeout
        self.rate_limited = rate_limited
        self.response_payload = response_payload

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(self, question: str) -> str:
        if self.timeout:
            raise LLMTimeoutError("Mock provider simulated timeout")
        if self.rate_limited:
            raise LLMRateLimitError("Mock provider simulated rate limit")

        if self.response_payload is not None:
            if isinstance(self.response_payload, str):
                return self.response_payload
            return json.dumps(self.response_payload)

        lower = question.lower()
        if "chlorophyll" in lower:
            payload = {"original_query": question, "parameters": ["chlorophyll"], "top_k": 5}
            if self.invalid_json:
                return "{not valid json"
            return json.dumps(payload)

        if "latitude 91" in lower or "181" in lower:
            payload = {
                "original_query": question,
                "parameters": ["temperature"],
                "latitude": 91.0,
                "longitude": 181.0,
                "top_k": 5,
            }
            if self.invalid_json:
                return "{not valid json"
            return json.dumps(payload)

        if "north atlantic" in lower:
            payload = {
                "original_query": question,
                "parameters": ["temperature"],
                "region": "North Atlantic",
                "top_k": 5,
            }
            if self.invalid_json:
                return "{not valid json"
            return json.dumps(payload)

        if self.invalid_json:
            return "{not valid json"

        payload = {
            "original_query": question,
            "semantic_query": "Bay of Bengal temperature profiles",
            "parameters": ["temperature"],
            "region": "Bay of Bengal",
            "top_k": 5,
        }
        if self.unsupported_parameter:
            payload["parameters"] = ["chlorophyll"]
        if self.invalid_coordinates:
            payload["latitude"] = 91.0
            payload["longitude"] = 181.0
        if self.missing_fields:
            payload.pop("parameters", None)
        return json.dumps(payload)


class OpenAICompatibleProvider(BaseLLMProvider):
    """Minimal OpenAI-compatible HTTP client for optional external providers."""

    def __init__(self, model: str | None = None, *, base_url: str | None = None, api_key: str | None = None, timeout: float = 30.0):
        super().__init__(model)
        self.base_url = (base_url or os.getenv("FLOATCHAT_LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.getenv("FLOATCHAT_LLM_API_KEY")
        self.timeout = float(timeout or os.getenv("FLOATCHAT_LLM_TIMEOUT", "30"))

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    def _build_request(self, question: str) -> tuple[str, dict[str, str], bytes]:
        endpoint = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You convert scientific ARGO queries into a strict JSON object with keys "
                        "original_query, semantic_query, parameters, region, latitude, longitude, radius_km, "
                        "bounding_box, start_date, end_date, top_k, interpretation_notes, validation_warnings. "
                        "Only use supported parameters: temperature, salinity, depth. "
                        "Do not invent coordinates or dates."
                    ),
                },
                {"role": "user", "content": question},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        return endpoint, headers, json.dumps(payload).encode("utf-8")

    def generate(self, question: str) -> str:
        if not self.api_key:
            raise LLMProviderError("FLOATCHAT_LLM_API_KEY is not configured for the OpenAI-compatible provider.")
        endpoint, headers, body = self._build_request(question)
        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                raise LLMRateLimitError(f"Rate limited by provider: {detail}") from exc
            raise LLMProviderError(f"Provider HTTP error {exc.code}: {detail}") from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(f"Provider request timed out after {self.timeout}s") from exc
        except Exception as exc:  # pragma: no cover - provider network exceptions
            raise LLMProviderError(f"Provider request failed: {exc}") from exc

        data = json.loads(payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"Provider response was missing the expected chat-completions content: {payload}") from exc


def _coerce_dict_payload(raw: Any, question: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("LLM provider produced a non-dictionary result.")

    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("LLM provider returned an empty response.")
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {cleaned[:200]}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object.")
    parsed.setdefault("original_query", question)
    return parsed


class LLMService:
    """Thin service wrapper that translates user questions into QueryPlan-compatible output."""

    def __init__(
        self,
        provider_name: str | None = None,
        *,
        provider_instance: BaseLLMProvider | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        if provider_instance is not None:
            self.provider = provider_instance
            self.provider_name = provider_instance.provider_name
            self.model = provider_instance.model
            return

        provider_name = (provider_name or os.getenv("FLOATCHAT_LLM_PROVIDER") or "mock").strip().lower()
        self.provider_name = provider_name
        self.model = model or os.getenv("FLOATCHAT_LLM_MODEL") or ("gpt-4o-mini" if provider_name == "openai_compatible" else "mock-model")
        if provider_name == "mock":
            self.provider = MockLLMProvider(self.model)
        elif provider_name in {"openai", "openai_compatible", "compatible"}:
            self.provider = OpenAICompatibleProvider(self.model, base_url=base_url or os.getenv("FLOATCHAT_LLM_BASE_URL"), api_key=api_key or os.getenv("FLOATCHAT_LLM_API_KEY"), timeout=timeout or float(os.getenv("FLOATCHAT_LLM_TIMEOUT", "30")))
        else:
            raise ValueError(f"Unsupported LLM provider '{provider_name}'. Supported values: mock, openai_compatible.")

    def is_enabled(self) -> bool:
        return self.provider_name != "disabled"

    def _normalise_plan_payload(self, payload: dict[str, Any], q: str) -> dict[str, Any]:
        payload = dict(payload)
        payload.setdefault("original_query", q)
        payload.setdefault("semantic_query", q)
        payload.setdefault("parameters", [])
        payload.setdefault("top_k", 5)
        payload.setdefault("interpretation_notes", [])
        payload.setdefault("validation_warnings", [])
        if isinstance(payload.get("parameters"), str):
            payload["parameters"] = [payload["parameters"]]
        if "region" in payload and payload["region"] is None:
            payload.pop("region")
        if "latitude" in payload and payload["latitude"] is not None:
            payload["latitude"] = float(payload["latitude"])
        if "longitude" in payload and payload["longitude"] is not None:
            payload["longitude"] = float(payload["longitude"])
        if "radius_km" in payload and payload["radius_km"] is not None:
            payload["radius_km"] = float(payload["radius_km"])
        return payload

    def _validate_against_project_rules(self, plan: QueryPlan) -> list[str]:
        warnings: list[str] = []
        supported_params = {key for key in QueryPlanner.SUPPORTED_PARAMETERS}
        unsupported = [p for p in plan.parameters if p not in supported_params]
        if unsupported:
            warnings.append(f"Unsupported scientific parameters were mentioned: {', '.join(sorted(set(unsupported)))}. Only temperature, salinity, and depth are validated in the current retrieval layer.")

        if plan.region and plan.region not in QueryPlanner.REGION_ALIASES:
            warnings.append(f"The location '{plan.region}' is not in the supported regional list for this project. Please use a supported region or a precise coordinate pair.")

        if plan.latitude is not None and not (-90.0 <= float(plan.latitude) <= 90.0):
            warnings.append("Latitude is outside the supported range [-90, 90].")
        if plan.longitude is not None and not (-180.0 <= float(plan.longitude) <= 180.0):
            warnings.append("Longitude is outside the supported range [-180, 180].")
        if plan.radius_km is not None and plan.radius_km <= 0:
            warnings.append("Radius must be greater than zero.")
        if plan.start_date and plan.end_date and plan.start_date > plan.end_date:
            warnings.append("Start date is later than end date; the query cannot be executed as written.")
        warnings.extend(plan.validation_warnings)
        return warnings

    def interpret(self, question: str, *, fallback_plan: QueryPlan | None = None) -> LLMPlanResult:
        if not isinstance(question, str) or not question.strip():
            return LLMPlanResult(
                original_query="",
                structured_query={},
                provider=self.provider_name,
                model=self.model,
                validation_warnings=["A natural-language question is required to invoke the LLM interpretation layer."],
                status="invalid",
                error="Question is empty.",
            )

        raw_question = " ".join(question.strip().split())
        try:
            raw = self.provider.generate(raw_question)
            payload = _coerce_dict_payload(raw, raw_question)
            if "parameters" not in payload:
                raise ValueError("LLM output missing required field: parameters")
            payload = self._normalise_plan_payload(payload, raw_question)
            plan = QueryPlan.model_validate(payload)
            validation_warnings = self._validate_against_project_rules(plan)
            if validation_warnings:
                status = "clarification_required" if any("could not be resolved reliably" in warning.lower() or "unsupported scientific parameters" in warning.lower() or "not in the supported regional list" in warning.lower() for warning in validation_warnings) else "invalid"
                return LLMPlanResult(
                    original_query=raw_question,
                    structured_query=plan.model_dump(),
                    provider=self.provider_name,
                    model=self.model,
                    validation_warnings=validation_warnings,
                    interpretation_notes=list(plan.interpretation_notes),
                    status=status,
                )
            return LLMPlanResult(
                original_query=raw_question,
                structured_query=plan.model_dump(),
                provider=self.provider_name,
                model=self.model,
                validation_warnings=[],
                interpretation_notes=list(plan.interpretation_notes),
                status="success",
            )
        except (LLMProviderError, ValueError, TypeError, json.JSONDecodeError, TimeoutError) as exc:
            msg = str(exc)
            lower_msg = msg.lower()
            invalid_range = any(token in lower_msg for token in ("less than or equal to 90", "less than or equal to 180", "greater than or equal", "latitude", "longitude"))
            if invalid_range:
                return LLMPlanResult(
                    original_query=raw_question,
                    structured_query={},
                    provider=self.provider_name,
                    model=self.model,
                    validation_warnings=[f"LLM output failed validation: {msg}"],
                    status="invalid",
                    error=msg,
                )
            if fallback_plan is not None and any(token in lower_msg for token in ("not valid json", "empty response", "missing required field", "timed out", "timeout", "rate limited", "provider request failed", "provider response", "simulated timeout", "simulated rate limit")):
                return LLMPlanResult(
                    original_query=raw_question,
                    structured_query=fallback_plan.model_dump(),
                    provider=self.provider_name,
                    model=self.model,
                    validation_warnings=list(fallback_plan.validation_warnings),
                    interpretation_notes=list(fallback_plan.interpretation_notes),
                    fallback_used=True,
                    status="fallback",
                    error=msg,
                )
            return LLMPlanResult(
                original_query=raw_question,
                structured_query={},
                provider=self.provider_name,
                model=self.model,
                validation_warnings=[f"LLM provider failed: {msg}"],
                status="provider_error",
                error=msg,
            )

    def plan(self, question: str, *, fallback_plan: QueryPlan | None = None) -> LLMPlanResult:
        return self.interpret(question, fallback_plan=fallback_plan)


def get_llm_service() -> LLMService:
    """Return the module singleton for the configured LLM service."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


_llm_service: LLMService | None = None
