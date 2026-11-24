import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.spatial_temporal_service import get_spatial_temporal_service


svc = get_spatial_temporal_service()


def test_bbox_search_filters_by_lat_lon():
    rows = svc.search_bbox(5, 25, 80, 100, limit=25)
    assert rows
    for row in rows:
        assert 5.0 <= float(row["latitude"]) <= 25.0
        assert 80.0 <= float(row["longitude"]) <= 100.0


def test_radius_search_filters_by_haversine_distance():
    rows = svc.search_radius(10.0, 90.0, 100.0, limit=25)
    assert rows
    for row in rows:
        assert float(row["distance_km"]) <= 100.0


def test_nearest_floats_groups_by_float_id():
    rows = svc.nearest_floats(10.0, 90.0, top_k=5, max_radius_km=500.0)
    assert len(rows) == 5
    float_ids = [row["float_id"] for row in rows]
    assert len(float_ids) == len(set(float_ids))
    assert rows == sorted(rows, key=lambda row: float(row["nearest_distance_km"]))


def test_search_date_range_filters_by_time_window():
    rows = svc.search_date_range("2022-01-01T00:00:00Z", "2022-01-02T00:00:00Z", limit=25)
    assert rows
    for row in rows:
        dt = pd.Timestamp(row["datetime"])
        assert pd.Timestamp("2022-01-01T00:00:00+00:00") <= dt <= pd.Timestamp("2022-01-02T00:00:00+00:00")


def test_search_by_month_filters_month_and_year():
    rows = svc.search_by_month(2022, 1, limit=25)
    assert rows
    for row in rows:
        dt = pd.Timestamp(row["datetime"])
        assert dt.year == 2022
        assert dt.month == 1


def test_empty_results_are_returned_when_no_match_exists():
    rows = svc.search_bbox(80, 90, 80, 90, limit=20)
    assert rows == []


def test_invalid_coordinates_raise_value_error():
    with pytest.raises(ValueError):
        svc.search_bbox(91, 92, 80, 90)
    with pytest.raises(ValueError):
        svc.search_radius(10, 200, 50)


def test_invalid_date_ranges_raise_value_error():
    with pytest.raises(ValueError):
        svc.search_date_range("2022-01-05T00:00:00Z", "2022-01-01T00:00:00Z")


def test_utc_timestamps_are_normalized_to_utc():
    rows = svc.search_by_month(2022, 1, limit=5)
    assert rows
    for row in rows:
        assert "+00:00" in row["datetime"]
        assert "Asia/Calcutta" not in row["datetime"]
