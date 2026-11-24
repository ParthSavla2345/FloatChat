import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.hybrid_service import HybridRetrievalQuery, get_hybrid_retrieval_service


svc = get_hybrid_retrieval_service()


def test_semantic_only_retrieval():
    result = svc.retrieve({"query": "Bay of Bengal temperature profiles", "max_results": 3})
    assert result["semantic_results"]
    assert result["results"]
    assert all(item["float_id"] for item in result["results"])


def test_spatial_only_retrieval():
    result = svc.retrieve({"query": "Bangladesh coastal waters", "region": "Bay of Bengal", "max_results": 5})
    assert result["results"]
    assert result["applied_filters"]["region"] == "Bay of Bengal"


def test_temporal_only_retrieval():
    result = svc.retrieve({
        "query": "temperature anomalies",
        "start_datetime": "2022-01-01T00:00:00Z",
        "end_datetime": "2022-01-31T23:59:59Z",
        "max_results": 5,
    })
    assert result["results"]


def test_semantic_plus_spatial_retrieval():
    result = svc.retrieve({
        "query": "Indian Ocean temperature observations",
        "semantic_text": "Bay of Bengal salinity and temperature",
        "region": "Bay of Bengal",
        "max_results": 5,
    })
    assert result["results"]


def test_semantic_plus_temporal_retrieval():
    result = svc.retrieve({
        "query": "Indian Ocean temperature observations",
        "semantic_text": "Indian Ocean heat content",
        "start_datetime": "2022-06-01T00:00:00Z",
        "end_datetime": "2022-06-30T23:59:59Z",
        "max_results": 5,
    })
    assert result["results"]


def test_semantic_plus_spatial_plus_temporal_retrieval():
    result = svc.retrieve({
        "query": "Indian Ocean salinity anomalies",
        "semantic_text": "Bay of Bengal salinity anomalies",
        "region": "Bay of Bengal",
        "start_datetime": "2022-01-01T00:00:00Z",
        "end_datetime": "2022-12-31T23:59:59Z",
        "parameters": ["temperature", "salinity"],
        "max_results": 5,
    })
    assert result["results"]
    assert all(item["available_parameters"].get("temperature") or item["available_parameters"].get("salinity") for item in result["results"])


def test_empty_results_are_returned_when_no_data_matches():
    result = svc.retrieve({
        "query": "far away ocean state",
        "latitude": 0.0,
        "longitude": 0.0,
        "radius_km": 0.1,
        "start_datetime": "2099-01-01T00:00:00Z",
        "end_datetime": "2099-01-02T00:00:00Z",
        "max_results": 5,
    })
    assert result["results"] == []
    assert result["matched_float_ids"] == []


def test_duplicate_profiles_are_deduplicated():
    query = HybridRetrievalQuery(query="duplicate review", max_results=5)
    merged = svc._merge_candidates(
        [
            {"float_id": "F1", "semantic_score": 0.75, "document": "first", "source_file": "a.nc"},
            {"float_id": "F1", "semantic_score": 0.85, "document": "second", "source_file": "b.nc"},
        ],
        [
            {"float_id": "F1", "source_file": "a.nc", "latitude": 10.0, "longitude": 20.0, "available_parameters": {"temperature": True, "salinity": True}},
            {"float_id": "F1", "source_file": "b.nc", "latitude": 10.0, "longitude": 20.0, "available_parameters": {"temperature": True, "salinity": True}},
        ],
        query,
    )
    assert len(merged) == 1
    assert merged[0]["float_id"] == "F1"


def test_ranking_is_consistent():
    query = {"query": "Bay of Bengal temperature profiles", "max_results": 3}
    first = svc.retrieve(query)
    second = svc.retrieve(query)
    assert first["matched_float_ids"] == second["matched_float_ids"]
    assert first["results"][0]["hybrid_score"] == second["results"][0]["hybrid_score"]


def test_invalid_constraints_raise_value_error():
    with pytest.raises(ValueError):
        HybridRetrievalQuery.from_dict({"query": "bad", "max_results": 0})
    with pytest.raises(ValueError):
        svc.retrieve({"query": "bad", "radius_km": -1.0})


def test_missing_metadata_is_ignored():
    query = HybridRetrievalQuery(query="missing metadata", max_results=5)
    merged = svc._merge_candidates(
        [{"document": "no id", "semantic_score": 0.1, "metadata": {}}],
        [],
        query,
    )
    assert merged == []


def test_chroma_and_duckdb_results_are_consistent():
    result = svc.retrieve({
        "query": "Bay of Bengal oxygen profile",
        "region": "Bay of Bengal",
        "max_results": 5,
    })
    assert result["matched_float_ids"]
    for float_id in result["matched_float_ids"]:
        assert float_id
