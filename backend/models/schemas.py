"""
FloatChat Pydantic Schemas
All request/response models for the API and internal data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Request Models ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000, description="Natural language oceanographic query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of semantic matches to retrieve")

    model_config = {"json_schema_extra": {"example": {"query": "Show temperature anomalies in the Bay of Bengal during monsoon 2023", "top_k": 5}}}


class SQLQueryRequest(BaseModel):
    sql: str = Field(..., min_length=6, description="SQL SELECT query to execute against argo_profiles")

    model_config = {"json_schema_extra": {"example": {"sql": "SELECT float_id, AVG(temperature) as avg_temp FROM argo_profiles WHERE year=2023 GROUP BY float_id LIMIT 10"}}}


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


# ── Internal Data Models ───────────────────────────────────────────────────────

class ParsedIntent(BaseModel):
    """Structured result of intent parsing from a user query."""
    raw_query: str
    regions: list[str] = Field(default_factory=list)
    bboxes: list[dict[str, float]] = Field(default_factory=list)  # [{"lat_min":..,"lat_max":..,"lon_min":..,"lon_max":..}]
    variables: list[str] = Field(default_factory=list)
    years: list[int] = Field(default_factory=list)
    months: list[int] = Field(default_factory=list)
    has_spatial_filter: bool = False
    has_temporal_filter: bool = False


class QueryPlannerRequest(BaseModel):
    """Natural-language query input for rule-based planning."""
    query: str = Field(..., min_length=3, max_length=1000, description="Original user question to convert to a retrieval query")


class QueryPlan(BaseModel):
    """Structured output produced by the query-planning layer."""
    original_query: str
    semantic_query: str = Field(default="", description="Text to pass to Chroma semantic retrieval")
    parameters: list[str] = Field(default_factory=list, description="Supported scientific parameters extracted from the query")
    region: str | None = Field(default=None, description="Supported named region if recognized")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    radius_km: float | None = Field(default=None, gt=0, description="Radius in kilometres")
    bounding_box: dict[str, float] | None = Field(default=None, description="Bounding box in the Stage 7 format: latitude_min, latitude_max, longitude_min, longitude_max")
    start_date: str | None = Field(default=None, description="Inclusive start date in ISO format")
    end_date: str | None = Field(default=None, description="Inclusive end date in ISO format")
    top_k: int = Field(default=5, ge=1, le=20, description="Maximum number of results requested")
    interpretation_notes: list[str] = Field(default_factory=list, description="Planned interpretation notes")
    validation_warnings: list[str] = Field(default_factory=list, description="Warnings for ambiguous or invalid constraints")

    def to_hybrid_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": self.original_query,
            "semantic_text": self.semantic_query or self.original_query,
            "parameters": list(self.parameters),
            "region": self.region,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "radius_km": self.radius_km,
            "start_datetime": self.start_date,
            "end_datetime": self.end_date,
            "max_results": self.top_k,
        }
        if self.bounding_box:
            payload.update(self.bounding_box)
        return {key: value for key, value in payload.items() if value is not None and value != []}


class LLMPlanResult(BaseModel):
    """Structured output produced by the optional LLM interpretation layer."""
    original_query: str
    structured_query: dict[str, Any] = Field(default_factory=dict, description="Query plan payload that can be validated against QueryPlan")
    provider: str = Field(default="mock", description="Configured provider name without leaking credentials")
    model: str = Field(default="mock-model", description="Configured model name for the provider")
    validation_warnings: list[str] = Field(default_factory=list, description="Warnings raised during LLM output validation")
    interpretation_notes: list[str] = Field(default_factory=list, description="Notes about how the question was interpreted")
    fallback_used: bool = Field(default=False, description="Whether the rule-based planner was used instead of the LLM output")
    status: str = Field(default="success", description="One of: success, fallback, invalid, provider_error, clarification_required")
    error: str | None = Field(default=None, description="Error message when the LLM provider fails")


class SemanticMatch(BaseModel):
    """Single semantic search result."""
    document: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class XAIExplanation(BaseModel):
    """Explainable AI reasoning output."""
    detected_region: str
    detected_variables: list[str]
    temporal_filters: dict[str, Any]
    semantic_matches: list[SemanticMatch]
    generated_sql: str
    scientific_reasoning: str
    confidence_note: str = "Results are observational and may require expert validation."


# ── Response Models ────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = "FloatChat backend is operational"


class SummaryResponse(BaseModel):
    total_rows: int
    unique_floats: int
    date_range: dict[str, str]   # {"min": "2022-01-01", "max": "2024-12-20"}
    depth_range: dict[str, float]  # {"min_m": 0.0, "max_m": 2000.0}
    files_processed: int
    regions_covered: list[str]


class SQLQueryResponse(BaseModel):
    sql: str
    row_count: int
    columns: list[str]
    data: list[dict[str, Any]]
    execution_time_ms: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SemanticMatch]
    total_results: int


class HybridRetrievalRequest(BaseModel):
    """Structured input for the hybrid semantic + DuckDB retrieval engine."""
    query: str = Field(..., min_length=3, max_length=1000, description="Original natural-language query")
    semantic_text: str | None = Field(default=None, description="Optional semantic search text; falls back to the main query when omitted")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0, description="Latitude used for radius-based spatial search")
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0, description="Longitude used for radius-based spatial search")
    latitude_min: float | None = Field(default=None, ge=-90.0, le=90.0, description="Minimum latitude for bounding-box search")
    latitude_max: float | None = Field(default=None, ge=-90.0, le=90.0, description="Maximum latitude for bounding-box search")
    longitude_min: float | None = Field(default=None, ge=-180.0, le=180.0, description="Minimum longitude for bounding-box search")
    longitude_max: float | None = Field(default=None, ge=-180.0, le=180.0, description="Maximum longitude for bounding-box search")
    radius_km: float | None = Field(default=None, gt=0, description="Radius in kilometres for coordinate search")
    region: str | None = Field(default=None, description="Named region such as Arabian Sea or Bay of Bengal")
    start_datetime: datetime | str | None = Field(default=None, description="Inclusive start timestamp for temporal filtering")
    end_datetime: datetime | str | None = Field(default=None, description="Inclusive end timestamp for temporal filtering")
    parameters: list[str] = Field(default_factory=list, description="Requested oceanographic parameters: temperature, salinity, depth")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum number of final hybrid matches to return")


class HybridCandidate(BaseModel):
    """A single hybrid candidate returned after semantic and structured merging."""
    float_id: str | None = None
    source_file: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    earliest_datetime: str | None = None
    latest_datetime: str | None = None
    semantic_score: float | None = None
    hybrid_score: float | None = None
    available_parameters: dict[str, bool] = Field(default_factory=dict)
    is_semantic_match: bool = False
    is_structured_match: bool = False


class HybridRetrievalResponse(BaseModel):
    original_query: str
    semantic_search_text: str | None = None
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    semantic_results: list[dict[str, Any]] = Field(default_factory=list)
    spatial_filtering: dict[str, Any] = Field(default_factory=dict)
    temporal_filtering: dict[str, Any] = Field(default_factory=dict)
    matched_float_ids: list[str] = Field(default_factory=list)
    results: list[HybridCandidate] = Field(default_factory=list)
    candidate_counts: dict[str, int] = Field(default_factory=dict)
    ranking_explanation: dict[str, Any] = Field(default_factory=dict)
    unavailable_parameters: list[str] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class OrchestrationRequest(BaseModel):
    """Natural-language question to be interpreted and executed by the orchestration layer."""
    query: str = Field(..., min_length=1, max_length=1000, description="User question to interpret and execute")


class OrchestrationResponse(BaseModel):
    """Structured orchestration response combining planner, retrieval, and explainability output."""
    original_query: str
    query_plan: dict[str, Any] = Field(default_factory=dict)
    interpretation_notes: list[str] = Field(default_factory=list)
    applied_filters: dict[str, Any] = Field(default_factory=dict)
    validation_warnings: list[str] = Field(default_factory=list)
    retrieval_status: str = Field(default="success", description="One of: success, success_zero_results, invalid_query, clarification_required, retrieval_failed")
    results: list[dict[str, Any]] = Field(default_factory=list)
    result_count: int = Field(default=0, ge=0)
    ranking_explanation: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    llm_metadata: dict[str, Any] = Field(default_factory=dict, description="Optional metadata about the LLM interpretation step if enabled")


class ChatResponse(BaseModel):
    query: str
    intent: ParsedIntent
    explanation: XAIExplanation
    sql_results: SQLQueryResponse | None = None
    processing_time_ms: float
