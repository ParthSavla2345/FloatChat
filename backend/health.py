"""Lightweight runtime health checks for the OceanIQ backend.

These checks are intentionally read-only and safe to call during local startup,
CLI validation, or deployment smoke tests. They do not execute dataset rebuilds
or issue privileged SQL.
"""

from __future__ import annotations

from typing import Any

from config import AppSettings, settings


def get_runtime_health(*, settings_obj: AppSettings | None = None, require_dataset: bool = True, require_llm: bool = False) -> dict[str, Any]:
    """Return a structured health report for the current runtime configuration."""
    cfg = settings_obj or settings
    report = cfg.validate_runtime(require_dataset=require_dataset, require_llm=require_llm)
    report["environment"] = cfg.environment
    report["backend_host"] = cfg.backend_host
    report["backend_port"] = cfg.backend_port
    report["request_timeout_seconds"] = cfg.request_timeout_seconds
    report["python_executable"] = cfg.python_executable or "python"
    report["notes"] = [
        "Read-only checks are safe to use during production-like startup validation.",
        "LLM provider configuration is optional unless a remote provider is explicitly enabled.",
    ]
    return report
