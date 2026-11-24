"""Hybrid retrieval engine combining semantic and structured retrieval.

The engine intentionally keeps Chroma and DuckDB separate but merges their
results when a caller provides a query with semantic, spatial, temporal, and
parameter constraints. Spatial and temporal filters are enforced as database
constraints and are not treated as soft ranking preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

import pandas as pd

from services.semantic_service import get_semantic_service
from services.spatial_temporal_service import get_spatial_temporal_service


def _normalise_param_name(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower().replace(" ", "_")
    aliases = {
        "temp": "temperature",
        "temperature": "temperature",
        "sal": "salinity",
        "salt": "salinity",
        "salinity": "salinity",
        "pressure": "depth",
        "depth": "depth",
        "pres": "depth",
        "temp_profile": "temperature",
    }
    return aliases.get(key, key)


@dataclass
class HybridRetrievalQuery:
    """Controlled input for the hybrid retrieval engine."""

    query: str = ""
    semantic_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    latitude_min: float | None = None
    latitude_max: float | None = None
    longitude_min: float | None = None
    longitude_max: float | None = None
    radius_km: float | None = None
    region: str | None = None
    start_datetime: Any | None = None
    end_datetime: Any | None = None
    parameters: list[str] = field(default_factory=list)
    max_results: int = 10

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | "HybridRetrievalQuery") -> "HybridRetrievalQuery":
        if isinstance(payload, cls):
            return payload
        if not isinstance(payload, Mapping):
            raise TypeError("HybridRetrievalQuery requires a mapping or HybridRetrievalQuery instance.")

        max_results = int(payload.get("max_results", payload.get("top_k", 10)))
        if max_results <= 0:
            raise ValueError("max_results must be > 0.")

        query = str(payload.get("query") or payload.get("semantic_text") or "")
        semantic_text = payload.get("semantic_text")
        if semantic_text is None:
            semantic_text = query or None

        params = payload.get("parameters", [])
        if params is None:
            params = []
        if isinstance(params, str):
            params = [params]

        instance = cls(
            query=query,
            semantic_text=str(semantic_text) if semantic_text else None,
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            latitude_min=payload.get("latitude_min"),
            latitude_max=payload.get("latitude_max"),
            longitude_min=payload.get("longitude_min"),
            longitude_max=payload.get("longitude_max"),
            radius_km=payload.get("radius_km"),
            region=payload.get("region"),
            start_datetime=payload.get("start_datetime"),
            end_datetime=payload.get("end_datetime"),
            parameters=[str(item) for item in params],
            max_results=max_results,
        )

        if instance.radius_km is not None and instance.radius_km <= 0:
            raise ValueError("radius_km must be greater than zero.")
        if instance.latitude is not None and not (-90.0 <= float(instance.latitude) <= 90.0):
            raise ValueError("latitude must be between -90 and 90 degrees.")
        if instance.longitude is not None and not (-180.0 <= float(instance.longitude) <= 180.0):
            raise ValueError("longitude must be between -180 and 180 degrees.")
        if instance.latitude_min is not None and instance.latitude_max is not None and float(instance.latitude_min) > float(instance.latitude_max):
            raise ValueError("latitude_min must be less than or equal to latitude_max.")
        if instance.longitude_min is not None and instance.longitude_max is not None and float(instance.longitude_min) > float(instance.longitude_max):
            raise ValueError("longitude_min must be less than or equal to longitude_max.")
        if instance.start_datetime is not None and instance.end_datetime is not None:
            start = pd.Timestamp(instance.start_datetime)
            end = pd.Timestamp(instance.end_datetime)
            if start > end:
                raise ValueError("start_datetime must be earlier than or equal to end_datetime.")

        return instance

    def applied_filters(self) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if self.region:
            filters["region"] = self.region
        if self.latitude is not None or self.longitude is not None:
            filters["coordinates"] = {
                "latitude": self.latitude,
                "longitude": self.longitude,
                "radius_km": self.radius_km,
            }
        if self.latitude_min is not None or self.latitude_max is not None or self.longitude_min is not None or self.longitude_max is not None:
            filters["bbox"] = {
                "latitude_min": self.latitude_min,
                "latitude_max": self.latitude_max,
                "longitude_min": self.longitude_min,
                "longitude_max": self.longitude_max,
            }
        if self.start_datetime is not None or self.end_datetime is not None:
            filters["time_range"] = {
                "start_datetime": self.start_datetime,
                "end_datetime": self.end_datetime,
            }
        if self.parameters:
            filters["parameters"] = list(self.parameters)
        return filters

    def has_spatial_filter(self) -> bool:
        return bool(
            self.region or self.latitude is not None or self.longitude is not None or self.latitude_min is not None or self.latitude_max is not None or self.longitude_min is not None or self.longitude_max is not None
        )

    def has_temporal_filter(self) -> bool:
        return self.start_datetime is not None or self.end_datetime is not None

    def requested_parameters(self) -> list[str]:
        return [_normalise_param_name(p) for p in self.parameters if _normalise_param_name(p) is not None]


class HybridRetrievalService:
    """Combine Chroma semantic retrieval with DuckDB spatial/temporal constraints."""

    def __init__(self, semantic_service=None, spatial_service=None):
        self.semantic_service = semantic_service or get_semantic_service()
        self.spatial_service = spatial_service or get_spatial_temporal_service()

    def _semantic_hits(self, query: HybridRetrievalQuery) -> list[dict[str, Any]]:
        text = query.semantic_text or query.query
        if not text:
            return []
        hits = self.semantic_service.semantic_search(text, top_k=query.max_results)
        return [
            {
                "float_id": (match.get("metadata") or {}).get("float_id"),
                "source_file": (match.get("metadata") or {}).get("file_name"),
                "document": match.get("document"),
                "semantic_score": float(match.get("score", 0.0)),
                "metadata": match.get("metadata", {}),
            }
            for match in hits
        ]

    def _structured_rows(self, query: HybridRetrievalQuery) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []

        if query.region:
            rows = self.spatial_service.search_by_region(
                query.region,
                start_datetime=query.start_datetime,
                end_datetime=query.end_datetime,
                limit=max(10, query.max_results * 20),
            )
            return rows

        if (
            query.latitude_min is not None
            or query.latitude_max is not None
            or query.longitude_min is not None
            or query.longitude_max is not None
        ):
            if all(v is not None for v in (query.latitude_min, query.latitude_max, query.longitude_min, query.longitude_max)):
                rows = self.spatial_service.search_bbox(
                    query.latitude_min,
                    query.latitude_max,
                    query.longitude_min,
                    query.longitude_max,
                    start_datetime=query.start_datetime,
                    end_datetime=query.end_datetime,
                    limit=max(10, query.max_results * 20),
                )
                return rows

        if query.latitude is not None and query.longitude is not None:
            if query.radius_km is not None:
                rows = self.spatial_service.search_radius(
                    query.latitude,
                    query.longitude,
                    query.radius_km,
                    start_datetime=query.start_datetime,
                    end_datetime=query.end_datetime,
                    limit=max(10, query.max_results * 20),
                )
                return rows

        if query.start_datetime is not None or query.end_datetime is not None:
            if query.start_datetime is not None and query.end_datetime is not None:
                rows = self.spatial_service.search_date_range(
                    query.start_datetime,
                    query.end_datetime,
                    limit=max(10, query.max_results * 20),
                )
                return rows

        return rows

    def _group_by_float(self, rows: Iterable[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            float_id = row.get("float_id")
            if not float_id:
                continue
            grouped.setdefault(str(float_id), []).append(dict(row))
        return grouped

    def _parameter_summary(self, rows: list[dict[str, Any]]) -> dict[str, bool]:
        available = {
            "temperature": any(_value_present(row.get("temperature")) for row in rows),
            "salinity": any(_value_present(row.get("salinity")) for row in rows),
            "depth": any(_value_present(row.get("depth")) for row in rows),
        }
        return available

    def _filter_structured_candidates(self, query: HybridRetrievalQuery, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped = self._group_by_float(rows)
        required = query.requested_parameters()
        candidates: list[dict[str, Any]] = []

        for float_id, float_rows in grouped.items():
            first = float_rows[0]
            available = self._parameter_summary(float_rows)
            if required and not set(required).issubset({k for k, v in available.items() if v}):
                continue
            candidates.append(
                {
                    "float_id": str(float_id),
                    "source_file": first.get("file_name"),
                    "latitude": first.get("latitude"),
                    "longitude": first.get("longitude"),
                    "earliest_datetime": min((item.get("datetime") for item in float_rows if item.get("datetime") is not None), default=None),
                    "latest_datetime": max((item.get("datetime") for item in float_rows if item.get("datetime") is not None), default=None),
                    "available_parameters": available,
                    "source": "structured",
                    "structured_match": True,
                }
            )
        return candidates

    def _merge_candidates(
        self,
        semantic_hits: list[dict[str, Any]],
        structured_candidates: list[dict[str, Any]],
        query: HybridRetrievalQuery,
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}

        for hit in semantic_hits:
            float_id = hit.get("float_id")
            if not float_id:
                continue
            merged.setdefault(str(float_id), {
                "float_id": str(float_id),
                "source_file": hit.get("source_file"),
                "fields": {"semantic_score": 0.0, "semantic_document": None},
                "semantic": False,
                "structured": False,
            })
            merged[str(float_id)]["fields"]["semantic_score"] = hit.get("semantic_score", 0.0)
            merged[str(float_id)]["fields"]["semantic_document"] = hit.get("document")
            merged[str(float_id)]["semantic"] = True
            merged[str(float_id)]["source_file"] = hit.get("source_file") or merged[str(float_id)].get("source_file")

        for candidate in structured_candidates:
            float_id = candidate.get("float_id")
            if not float_id:
                continue
            key = str(float_id)
            merged.setdefault(key, {
                "float_id": key,
                "source_file": candidate.get("source_file"),
                "fields": {"semantic_score": 0.0, "semantic_document": None},
                "semantic": False,
                "structured": False,
            })
            merged[key].update({
                "source_file": candidate.get("source_file") or merged[key].get("source_file"),
                "latitude": candidate.get("latitude"),
                "longitude": candidate.get("longitude"),
                "earliest_datetime": candidate.get("earliest_datetime"),
                "latest_datetime": candidate.get("latest_datetime"),
                "available_parameters": candidate.get("available_parameters", {}),
            })
            merged[key]["structured"] = True

        if query.has_spatial_filter() or query.has_temporal_filter():
            allow_ids = {str(item.get("float_id")) for item in structured_candidates}
            filtered = {}
            for key, value in merged.items():
                if key in allow_ids or not (query.has_spatial_filter() or query.has_temporal_filter()):
                    filtered[key] = value
            merged = filtered

        return list(merged.values())

    def _hybrid_score(self, candidate: Mapping[str, Any], query: HybridRetrievalQuery) -> tuple[float, dict[str, Any]]:
        semantic_score = float(candidate.get("fields", {}).get("semantic_score", 0.0) or 0.0)
        spatial_match = 1.0 if query.region is None and query.latitude is None and query.longitude is None and query.latitude_min is None and query.latitude_max is None and query.longitude_min is None and query.longitude_max is None else 1.0
        if query.region or query.latitude is not None or query.longitude is not None or query.latitude_min is not None or query.latitude_max is not None or query.longitude_min is not None or query.longitude_max is not None:
            spatial_match = 1.0
        temporal_match = 1.0 if query.start_datetime is None and query.end_datetime is None else 1.0
        param_hits = 0
        required = query.requested_parameters()
        if required:
            available = candidate.get("available_parameters", {}) or {}
            param_hits = sum(1 for p in required if available.get(p, False))
            param_ratio = param_hits / len(required) if required else 0.0
        else:
            param_ratio = 1.0

        semantic_weight = 0.8 if semantic_score > 0 else 0.0
        constraint_weight = 0.2
        if query.has_spatial_filter() or query.has_temporal_filter() or required:
            constraint_score = 0.0
            if query.has_spatial_filter():
                constraint_score += 0.5
            if query.has_temporal_filter():
                constraint_score += 0.25
            if required:
                constraint_score += 0.25 * param_ratio
            constraint_score = min(1.0, constraint_score)
        else:
            constraint_score = 1.0

        if semantic_score > 0:
            hybrid_score = min(1.0, (semantic_score * (1.0 - constraint_weight)) + (constraint_score * constraint_weight))
        else:
            hybrid_score = constraint_score

        explanation = {
            "semantic_score": semantic_score,
            "constraint_score": round(constraint_score, 4),
            "semantic_weight": round(semantic_weight, 4),
            "constraint_weight": round(constraint_weight, 4),
            "required_parameters": required,
            "matched_parameters": [p for p in required if (candidate.get("available_parameters") or {}).get(p)],
            "hybrid_score": round(hybrid_score, 6),
        }
        return hybrid_score, explanation

    def retrieve(self, query: HybridRetrievalQuery | Mapping[str, Any]) -> dict[str, Any]:
        req = HybridRetrievalQuery.from_dict(query)
        semantic_hits = self._semantic_hits(req)
        structured_rows = self._structured_rows(req)
        structured_candidates = self._filter_structured_candidates(req, structured_rows)

        merged = self._merge_candidates(semantic_hits, structured_candidates, req)
        ranked: list[dict[str, Any]] = []
        for item in merged:
            score, explanation = self._hybrid_score(item, req)
            ranked_item = {
                "float_id": item.get("float_id"),
                "source_file": item.get("source_file"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "semantic_score": item.get("fields", {}).get("semantic_score", 0.0),
                "semantic_document": item.get("fields", {}).get("semantic_document"),
                "available_parameters": item.get("available_parameters", {}),
                "earliest_datetime": item.get("earliest_datetime"),
                "latest_datetime": item.get("latest_datetime"),
                "hybrid_score": round(score, 6),
                "ranking_explanation": explanation,
                "is_semantic_match": bool(item.get("semantic")),
                "is_structured_match": bool(item.get("structured")),
            }
            ranked.append(ranked_item)

        ranked.sort(key=lambda row: (-float(row.get("hybrid_score", 0.0)), str(row.get("float_id", ""))))
        ranked = ranked[: max(1, req.max_results)]

        unavailable = []
        if req.parameters:
            known = {"temperature", "salinity", "depth"}
            unavailable = [p for p in req.requested_parameters() if p not in known]

        return {
            "original_query": req.query,
            "semantic_search_text": req.semantic_text or req.query,
            "applied_filters": req.applied_filters(),
            "semantic_results": semantic_hits[: req.max_results],
            "spatial_filtering": {
                "requested": {
                    "region": req.region,
                    "latitude": req.latitude,
                    "longitude": req.longitude,
                    "radius_km": req.radius_km,
                    "latitude_min": req.latitude_min,
                    "latitude_max": req.latitude_max,
                    "longitude_min": req.longitude_min,
                    "longitude_max": req.longitude_max,
                },
                "candidate_count_before_filter": len(structured_rows),
                "candidate_count_after_filter": len(structured_candidates),
            },
            "temporal_filtering": {
                "start_datetime": req.start_datetime,
                "end_datetime": req.end_datetime,
                "candidate_count_before_filter": len(structured_rows),
                "candidate_count_after_filter": len(structured_candidates),
            },
            "matched_float_ids": [item["float_id"] for item in ranked if item.get("float_id")],
            "results": ranked,
            "candidate_counts": {
                "semantic_before_filter": len(semantic_hits),
                "structured_before_filter": len(structured_rows),
                "after_filtering": len(ranked),
            },
            "ranking_explanation": {
                "method": "semantic_score * 0.8 + structured_constraint_score * 0.2",
                "notes": "Spatial and temporal filters are enforced, not only ranked. Chroma relevance is used only when available; structured-only results rely on deterministic filter satisfaction.",
            },
            "unavailable_parameters": unavailable,
            "data_limitations": [
                "Processed DuckDB tables use float_id as the project-level float key; raw NetCDF PLATFORM_NUMBER must be read directly if a true WMO identifier is required.",
                "The semantic index is float-level and does not natively expose per-profile row identity.",
            ],
        }


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


def get_hybrid_retrieval_service() -> HybridRetrievalService:
    global _service
    if _service is None:
        _service = HybridRetrievalService()
    return _service


_service: HybridRetrievalService | None = None
