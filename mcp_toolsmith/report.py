"""Structured generation reporting models and helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mcp_toolsmith.scorer import ScoringResult


class SkippedOperation(BaseModel):
    """A generation skip entry with a machine-readable reason."""

    operation_id: str
    reason: str


class GenerationReport(BaseModel):
    """Machine-readable generation report emitted after successful runs."""

    model_config = ConfigDict(extra="forbid")

    spec_title: str
    spec_version: str
    total_operations: int
    generated_operations: int
    skipped_operations: list[SkippedOperation] = Field(default_factory=list)
    score: ScoringResult
    generated_files: list[str] = Field(default_factory=list)
    timestamp: datetime
    cli_flags: dict[str, Any] = Field(default_factory=dict)


def build_report(
    *,
    spec_title: str,
    spec_version: str,
    total_operations: int,
    generated_operations: int,
    skipped_operations: list[SkippedOperation],
    score: ScoringResult,
    generated_files: list[Path],
    cli_flags: dict[str, Any],
) -> GenerationReport:
    """Build a deterministic generation report instance."""

    return GenerationReport(
        spec_title=spec_title,
        spec_version=spec_version,
        total_operations=total_operations,
        generated_operations=generated_operations,
        skipped_operations=skipped_operations,
        score=score,
        generated_files=sorted(path.as_posix() for path in generated_files),
        timestamp=datetime.now(timezone.utc),
        cli_flags=cli_flags,
    )

