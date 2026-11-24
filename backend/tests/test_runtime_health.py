import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import AppSettings
from health import get_runtime_health


def test_settings_pick_up_env_overrides(monkeypatch):
    monkeypatch.setenv("FLOATCHAT_ENV", "production")
    monkeypatch.setenv("FLOATCHAT_BACKEND_PORT", "9090")
    monkeypatch.setenv("FLOATCHAT_REQUEST_TIMEOUT", "45")
    settings = AppSettings.from_environment()
    assert settings.environment == "production"
    assert settings.backend_port == 9090
    assert settings.request_timeout_seconds == 45.0


def test_health_check_reports_missing_dataset(tmp_path):
    settings = AppSettings(
        root_dir=tmp_path,
        archive_dir=tmp_path / "archive",
        data_dir=tmp_path / "data",
        processed_dir=tmp_path / "data" / "processed",
        logs_dir=tmp_path / "logs",
        chroma_dir=tmp_path / "data" / "chroma",
        argo_profiles_parquet=tmp_path / "data" / "processed" / "argo_profiles.parquet",
        duckdb_path=tmp_path / "data" / "processed" / "floatchat.duckdb",
        float_metadata_parquet=tmp_path / "data" / "processed" / "float_metadata.parquet",
        float_metadata_json=tmp_path / "data" / "processed" / "float_metadata.json",
        validation_report=tmp_path / "logs" / "database_validation.txt",
    )
    report = get_runtime_health(settings_obj=settings, require_dataset=True)
    assert report["status"] == "error"
    assert any("DuckDB file" in issue for issue in report["issues"])


def test_health_check_allows_degraded_runtime_without_dataset(tmp_path):
    settings = AppSettings(
        root_dir=tmp_path,
        archive_dir=tmp_path / "archive",
        data_dir=tmp_path / "data",
        processed_dir=tmp_path / "data" / "processed",
        logs_dir=tmp_path / "logs",
        chroma_dir=tmp_path / "data" / "chroma",
        argo_profiles_parquet=tmp_path / "data" / "processed" / "argo_profiles.parquet",
        duckdb_path=tmp_path / "data" / "processed" / "floatchat.duckdb",
        float_metadata_parquet=tmp_path / "data" / "processed" / "float_metadata.parquet",
        float_metadata_json=tmp_path / "data" / "processed" / "float_metadata.json",
        validation_report=tmp_path / "logs" / "database_validation.txt",
    )
    report = get_runtime_health(settings_obj=settings, require_dataset=False)
    assert report["status"] == "ok"
    assert report["checks"]["duckdb"] is False
