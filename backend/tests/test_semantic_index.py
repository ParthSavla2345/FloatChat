import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ingestion.build_chroma_index import _normalise_float_metadata, generate_summary
from services.semantic_service import SemanticService


def test_normalise_float_metadata_midpoints():
    df = pd.DataFrame(
        [
            {
                "float_id": "f-001",
                "latitude_min": -10.0,
                "latitude_max": 10.0,
                "longitude_min": 50.0,
                "longitude_max": 100.0,
                "observation_start": "2023-01-01",
                "total_profiles": 12,
                "total_observations": 400,
            }
        ]
    )

    normalised = _normalise_float_metadata(df)

    assert normalised["latitude"].iloc[0] == 0.0
    assert normalised["longitude"].iloc[0] == 75.0
    assert normalised["time"].iloc[0] == "2023-01-01"
    assert "file_name" in normalised.columns


def test_generate_summary_contains_expected_context():
    row = pd.Series(
        {
            "float_id": "f-001",
            "latitude": 10.0,
            "longitude": 80.0,
            "time": "2023-03-15",
            "n_profiles": 4,
            "n_levels": 120,
            "file_name": "f-001.nc",
        }
    )

    summary = generate_summary(row)

    assert "f-001" in summary
    assert "4 profiles" in summary
    assert "120 depth-level" in summary
    assert "Bay of Bengal" in summary or "Indian Ocean" in summary


def test_semantic_service_returns_results():
    service = SemanticService()
    results = service.semantic_search("Bay of Bengal temperature profiles 2023", top_k=3)

    assert isinstance(results, list)
    assert len(results) > 0
    first = results[0]
    assert "document" in first and "score" in first and "metadata" in first
    assert first["metadata"].get("float_id")
