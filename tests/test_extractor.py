"""Tests for OpenAPI validation, dereferencing, and extraction."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mcp_toolsmith.deref import dereference_local_refs
from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.models import OperationModel
from mcp_toolsmith.validator import SpecValidationError, validate_spec


def _load_fixture(name: str) -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_validate_spec_accepts_openapi_3_document() -> None:
    spec = _load_fixture("valid_openapi.yaml")

    validate_spec(spec)


def test_validate_spec_rejects_missing_paths() -> None:
    spec = {"openapi": "3.0.3", "info": {"title": "Bad", "version": "1.0.0"}}

    with pytest.raises(SpecValidationError) as exc_info:
        validate_spec(spec)

    assert exc_info.value.errors == [
        {"field": "paths", "message": "Top-level 'paths' object is required.", "value": None}
    ]


def test_validate_spec_rejects_invalid_version() -> None:
    spec = {"openapi": "2.0", "info": {"title": "Bad", "version": "1.0.0"}, "paths": {}}

    with pytest.raises(SpecValidationError) as exc_info:
        validate_spec(spec)

    assert exc_info.value.errors == [
        {"field": "openapi", "message": "OpenAPI version must be a 3.x string.", "value": "2.0"}
    ]


def test_dereference_rejects_circular_refs() -> None:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Loop", "version": "1.0.0"},
        "paths": {},
        "components": {"schemas": {"Loop": {"$ref": "#/components/schemas/Loop"}}},
    }

    with pytest.raises(SpecValidationError) as exc_info:
        dereference_local_refs(spec)

    assert exc_info.value.errors[0]["message"].startswith("Circular $ref detected")


def test_dereference_rejects_external_refs() -> None:
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "External", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {"schema": {"$ref": "https://example.com/schemas/Pet"}}
                            },
                        }
                    }
                }
            }
        },
    }

    with pytest.raises(SpecValidationError) as exc_info:
        dereference_local_refs(spec)

    assert exc_info.value.errors == [
        {
            "field": "$ref",
            "message": "External $ref values are not supported: https://example.com/schemas/Pet",
            "value": "https://example.com/schemas/Pet",
        }
    ]


def test_extract_operations_builds_operation_models() -> None:
    spec = _load_fixture("valid_openapi.yaml")

    operations = extract_operations(spec)

    assert all(isinstance(operation, OperationModel) for operation in operations)
    assert [operation.operation_id for operation in operations] == ["getPet", "post_pets_petId"]

    get_pet = operations[0]
    assert get_pet.source_path == "/pets/{petId}"
    assert get_pet.http_method == "get"
    assert [param.name for param in get_pet.path_params] == ["petId"]
    assert [param.name for param in get_pet.query_params] == ["includeVaccines"]
    assert get_pet.responses["200"] is not None
    assert get_pet.responses["200"].type == "object"
    assert set(get_pet.responses["200"].properties) == {"id", "name"}

    post_pet = operations[1]
    assert post_pet.request_body is not None
    assert post_pet.request_body.type == "object"
    assert set(post_pet.request_body.properties) == {"name"}
    assert post_pet.responses["202"] is not None
