"""Shared runtime configuration for the FloatChat backend.

This project is organized as a staged pipeline:
1. ingest and inspect NetCDF Argo files,
2. flatten them to parquet for analytical access,
3. materialize the DuckDB table,
4. build a semantic search index, and
5. serve read-only queries through the app services.

The module exposes both the legacy constant-based paths and the modern
``settings`` singleton expected by the ingestion and service modules.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional in minimal local runs
    def load_dotenv(*_args, **_kwargs):
        return False

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = BASE_DIR / "archive"
DATA_DIR = BASE_DIR / "backend" / "data"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = BASE_DIR / "backend" / "logs"
CHROMA_DIR = DATA_DIR / "chroma"

ARCHIVE_GLOB = "*.nc"
PARQUET_FILE = PROCESSED_DIR / "argo_profiles.parquet"
SUMMARY_FILE = PROCESSED_DIR / "processing_summary.json"
REPORT_FILE = LOGS_DIR / "inspection_report.txt"
DUCKDB_FILE = PROCESSED_DIR / "floatchat.duckdb"
METADATA_PARQUET = PROCESSED_DIR / "float_metadata.parquet"
METADATA_JSON = PROCESSED_DIR / "float_metadata.json"
VALIDATION_REPORT = LOGS_DIR / "database_validation.txt"

FILL_VALUE = 99999.0

VAR_CONFIG = {
    "temperature": {"adjusted": "TEMP_ADJUSTED", "standard": "TEMP"},
    "salinity": {"adjusted": "PSAL_ADJUSTED", "standard": "PSAL"},
    "pressure": {"adjusted": "PRES_ADJUSTED", "standard": "PRES"},
}

OUTPUT_COLUMNS = [
    "file_name",
    "float_id",
    "profile_number",
    "cycle_number",
    "datetime",
    "latitude",
    "longitude",
    "depth",
    "temperature",
    "salinity",
]

LOGGING_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOGGING_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = (BASE_DIR / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate if value.strip() else default


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


def _env_int(name: str, default: int, *, minimum: int | None = None, maximum: int | None = None) -> int:
    value = os.getenv(name)
    try:
        parsed = int(value) if value not in (None, "") else default
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc
    if minimum is not None and parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    try:
        return float(value) if value not in (None, "") else default
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be numeric.") from exc


@dataclass(frozen=True)
class AppSettings:
    """Project-wide file paths and runtime configuration.

    This singleton is used by the ingestion scripts and service layer that expect
    a `settings` object instead of direct module constants.
    """

    root_dir: Path = BASE_DIR
    archive_dir: Path = ARCHIVE_DIR
    data_dir: Path = DATA_DIR
    processed_dir: Path = PROCESSED_DIR
    logs_dir: Path = LOGS_DIR
    chroma_dir: Path = CHROMA_DIR
    argo_profiles_parquet: Path = PARQUET_FILE
    duckdb_path: Path = DUCKDB_FILE
    float_metadata_parquet: Path = METADATA_PARQUET
    float_metadata_json: Path = METADATA_JSON
    validation_report: Path = VALIDATION_REPORT
    environment: str = "development"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_api_base_url: str = "http://localhost:3000"
    python_executable: str | None = None
    request_timeout_seconds: float = 30.0
    chroma_collection_name: str = "argo_profiles"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_provider: str = "mock"
    llm_model: str = "mock-model"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_timeout: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_dir", Path(self.root_dir).expanduser())
        object.__setattr__(self, "archive_dir", Path(self.archive_dir).expanduser())
        object.__setattr__(self, "data_dir", Path(self.data_dir).expanduser())
        object.__setattr__(self, "processed_dir", Path(self.processed_dir).expanduser())
        object.__setattr__(self, "logs_dir", Path(self.logs_dir).expanduser())
        object.__setattr__(self, "chroma_dir", Path(self.chroma_dir).expanduser())
        object.__setattr__(self, "argo_profiles_parquet", Path(self.argo_profiles_parquet).expanduser())
        object.__setattr__(self, "duckdb_path", Path(self.duckdb_path).expanduser())
        object.__setattr__(self, "float_metadata_parquet", Path(self.float_metadata_parquet).expanduser())
        object.__setattr__(self, "float_metadata_json", Path(self.float_metadata_json).expanduser())
        object.__setattr__(self, "validation_report", Path(self.validation_report).expanduser())

    @classmethod
    def from_environment(cls) -> "AppSettings":
        """Create a settings object from the active environment variables."""
        return cls(
            root_dir=BASE_DIR,
            archive_dir=_env_path("FLOATCHAT_ARCHIVE_DIR", ARCHIVE_DIR),
            data_dir=_env_path("FLOATCHAT_DATA_DIR", DATA_DIR),
            processed_dir=_env_path("FLOATCHAT_PROCESSED_DIR", PROCESSED_DIR),
            logs_dir=_env_path("FLOATCHAT_LOGS_DIR", LOGS_DIR),
            chroma_dir=_env_path("FLOATCHAT_CHROMA_DIR", CHROMA_DIR),
            argo_profiles_parquet=_env_path("FLOATCHAT_PARQUET_PATH", PARQUET_FILE),
            duckdb_path=_env_path("FLOATCHAT_DUCKDB_PATH", DUCKDB_FILE),
            float_metadata_parquet=_env_path("FLOATCHAT_METADATA_PARQUET", METADATA_PARQUET),
            float_metadata_json=_env_path("FLOATCHAT_METADATA_JSON", METADATA_JSON),
            validation_report=_env_path("FLOATCHAT_VALIDATION_REPORT", VALIDATION_REPORT),
            environment=_env_str("FLOATCHAT_ENV", "development"),
            backend_host=_env_str("FLOATCHAT_BACKEND_HOST", "127.0.0.1"),
            backend_port=_env_int("FLOATCHAT_BACKEND_PORT", 8000, minimum=1, maximum=65535),
            frontend_api_base_url=_env_str("NEXT_PUBLIC_API_BASE_URL", "http://localhost:3000"),
            python_executable=os.getenv("OCEANIQ_PYTHON_PATH") or os.getenv("PYTHON_PATH"),
            request_timeout_seconds=_env_float("FLOATCHAT_REQUEST_TIMEOUT", 30.0),
            chroma_collection_name=_env_str("FLOATCHAT_CHROMA_COLLECTION", "argo_profiles"),
            embedding_model=_env_str("FLOATCHAT_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
            llm_provider=_env_str("FLOATCHAT_LLM_PROVIDER", "mock"),
            llm_model=_env_str("FLOATCHAT_LLM_MODEL", "mock-model"),
            llm_base_url=os.getenv("FLOATCHAT_LLM_BASE_URL"),
            llm_api_key=os.getenv("FLOATCHAT_LLM_API_KEY"),
            llm_timeout=_env_float("FLOATCHAT_LLM_TIMEOUT", 30.0),
        )

    def ensure_dirs(self) -> None:
        """Ensure the runtime directories required by ingestion and indexing exist."""
        for path in (
            self.data_dir,
            self.processed_dir,
            self.logs_dir,
            self.chroma_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def validate_runtime(self, *, require_dataset: bool = True, require_llm: bool = False) -> dict[str, object]:
        """Validate required project paths and optional runtime capabilities."""
        issues: list[str] = []
        checks: dict[str, bool] = {
            "data_dir": self.data_dir.exists(),
            "processed_dir": self.processed_dir.exists(),
            "logs_dir": self.logs_dir.exists(),
            "chroma_dir": self.chroma_dir.exists(),
            "duckdb": self.duckdb_path.exists(),
            "parquet": self.argo_profiles_parquet.exists(),
        }

        if require_dataset:
            if not self.duckdb_path.exists():
                issues.append(f"DuckDB file is missing: {self.duckdb_path}. Run the data build steps before starting read-only queries.")
            if not self.argo_profiles_parquet.exists():
                issues.append(f"Parquet dataset is missing: {self.argo_profiles_parquet}.")

        if require_llm and self.llm_provider not in {"mock", "disabled"} and self.llm_provider not in {"openai", "openai_compatible", "compatible"}:
            issues.append(f"Unsupported LLM provider '{self.llm_provider}'.")

        if self.llm_provider in {"openai", "openai_compatible", "compatible"} and not self.llm_api_key:
            if require_llm:
                issues.append("FLOATCHAT_LLM_API_KEY is required when the OpenAI-compatible provider is selected.")

        if self.backend_port < 1 or self.backend_port > 65535:
            issues.append("FLOATCHAT_BACKEND_PORT must be between 1 and 65535.")

        status = "ok" if not issues else "error"
        return {"status": status, "issues": issues, "checks": checks}


load_dotenv(BASE_DIR / ".env", override=False)
settings = AppSettings.from_environment()


def setup_logging(name: str = "floatchat") -> logging.Logger:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        fh = logging.FileHandler(settings.logs_dir / f"{name}.log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(LOGGING_FORMAT, LOGGING_DATE_FORMAT))
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(levelname)-8s | %(message)s"))
        logger.addHandler(fh)
        logger.addHandler(ch)
    return logger
