import sys
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from api_server import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"


def test_readiness_endpoint():
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"


def test_query_endpoint_returns_orchestration_payload():
    response = client.post("/api/query", json={"question": "Find temperature in the Bay of Bengal"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["original_query"] == "Find temperature in the Bay of Bengal"
    assert "retrieval_status" in payload


def test_summary_endpoint_returns_dataset_metrics():
    response = client.get("/api/data/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["observation_rows"] > 0
    assert payload["project_float_count"] > 0
