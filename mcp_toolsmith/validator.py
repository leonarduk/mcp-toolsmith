"""OpenAPI 3.x validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class SpecValidationError(Exception):
    """Raised when an OpenAPI document fails validation."""

    def __init__(self, message: str, *, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or []



def validate_spec(document: Mapping[str, Any]) -> None:
    """Validate the minimum OpenAPI 3.x contract needed for ingestion."""
    errors: list[dict[str, Any]] = []

    version = document.get("openapi")
    if not isinstance(version, str) or not version.startswith("3."):
        errors.append(
            {
                "field": "openapi",
                "message": "OpenAPI version must be a 3.x string.",
                "value": version,
            }
        )

    info = document.get("info")
    if not isinstance(info, Mapping):
        errors.append({"field": "info", "message": "Top-level 'info' object is required.", "value": info})

    paths = document.get("paths")
    if not isinstance(paths, Mapping):
        errors.append({"field": "paths", "message": "Top-level 'paths' object is required.", "value": paths})

    if errors:
        raise SpecValidationError("Invalid OpenAPI specification.", errors=errors)
