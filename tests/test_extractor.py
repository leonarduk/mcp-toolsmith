"""Tests for OpenAPI validation, dereferencing, and extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from mcp_toolsmith.deref import dereference_local_refs
from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.models import OperationModel
from mcp_toolsmith.validator import SpecValidationError, validate_spec


def _load_fixture(name: str) -> dict[str, object]:
    path = Path(__file__).parent / "fixtures" / name
    return cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))


def _minimal_spec() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {"title": "Spec", "version": "1.0.0"},
        "paths": {},
    }


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


def test_dereference_handles_empty_document() -> None:
    assert dereference_local_refs({}) == {}


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


def test_dereference_unescapes_json_pointer_tokens_in_spec_order() -> None:
    spec = _minimal_spec()
    spec["components"] = {
        "schemas": {
            "slash/name": {"type": "string", "description": "slash"},
            "~1": {"type": "string", "description": "tilde one"},
        }
    }
    spec["paths"] = {
        "/pets": {
            "get": {
                "responses": {
                    "200": {"description": "ok", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/slash~1name"}}}},
                    "201": {"description": "ok", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/~01"}}}},
                }
            }
        }
    }

    dereferenced = dereference_local_refs(spec)
    response_content = cast(dict[str, Any], dereferenced["paths"])["/pets"]["get"]["responses"]

    assert response_content["200"]["content"]["application/json"]["schema"]["description"] == "slash"
    assert response_content["201"]["content"]["application/json"]["schema"]["description"] == "tilde one"


def test_dereference_rejects_invalid_json_pointer_escape_sequences() -> None:
    invalid_refs = ["#/components/schemas/bad~2token", "#/components/schemas/bad~xtoken", "#/components/schemas/bad~"]

    for ref in invalid_refs:
        spec = _minimal_spec()
        spec["components"] = {
            "schemas": {
                "bad~2token": {"type": "string"},
                "bad~xtoken": {"type": "string"},
                "bad~": {"type": "string"},
            }
        }
        spec["paths"] = {
            "/pets": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"$ref": ref}}},
                        }
                    }
                }
            }
        }

        with pytest.raises(SpecValidationError) as exc_info:
            dereference_local_refs(spec)

        token = ref.rsplit("/", 1)[-1]
        assert exc_info.value.errors == [
            {
                "field": "$ref",
                "message": f"Invalid JSON Pointer escape sequence in token: {token}",
                "value": token,
            }
        ]


def test_dereference_supports_deeply_nested_and_unusual_pointer_paths() -> None:
    spec = _minimal_spec()
    spec["components"] = {
        "schemas": {
            "outer~name": {
                "properties": {
                    "nested/value": {
                        "$ref": "#/components/schemas/leaf~0node",
                    }
                }
            },
            "leaf~node": {"type": "object", "properties": {"depth": {"type": "integer"}}},
        }
    }
    spec["paths"] = {
        "/deep": {
            "get": {
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/outer~0name/properties/nested~1value"}
                            }
                        },
                    }
                }
            }
        }
    }

    dereferenced = dereference_local_refs(spec)
    schema = dereferenced["paths"]["/deep"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    assert schema["type"] == "object"
    assert schema["properties"]["depth"]["type"] == "integer"


def test_extract_operations_builds_operation_models() -> None:
    spec = _load_fixture("valid_openapi.yaml")

    operations = extract_operations(spec)

    assert all(isinstance(operation, OperationModel) for operation in operations)
    assert [operation.operation_id for operation in operations] == ["getPet", "post_pets_petid"]

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


def test_extract_operations_rejects_empty_openapi_document() -> None:
    with pytest.raises(SpecValidationError) as exc_info:
        extract_operations({})

    assert {error["field"] for error in exc_info.value.errors} == {"openapi", "info", "paths"}


def test_extract_operations_validates_missing_path_parameters() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/pets/{petId}": {
            "get": {
                "responses": {"200": {"description": "ok"}},
            }
        }
    }

    with pytest.raises(SpecValidationError) as exc_info:
        extract_operations(spec)

    assert exc_info.value.errors == [
        {
            "field": "paths",
            "message": "Path template parameters are missing definitions for ['petId'].",
            "value": {"path": "/pets/{petId}", "missing": ["petId"]},
        }
    ]


def test_extract_operations_merges_parameters_with_operation_override() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/pets/{petId}": {
            "parameters": [
                {
                    "name": "petId",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": "path level",
                },
                {"name": "trace", "in": "header", "schema": {"type": "string"}},
            ],
            "get": {
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                        "description": "operation level",
                    }
                ],
                "responses": {"200": {"description": "ok"}},
            },
        }
    }

    [operation] = extract_operations(spec)

    assert operation.path_params[0].description == "operation level"
    assert operation.path_params[0].schema_model is not None
    assert operation.path_params[0].schema_model.type == "integer"
    assert [param.name for param in operation.header_params] == ["trace"]


def test_extract_operations_prefers_application_json_then_application_wildcard_then_first_defined() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/pets": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/xml": {"schema": {"type": "string"}},
                        "application/json": {"schema": {"type": "object"}},
                    }
                },
                "responses": {"200": {"description": "ok"}},
            }
        }
    }

    [operation] = extract_operations(spec)

    assert operation.request_body is not None
    assert operation.request_body.type == "object"

    wildcard_spec = _minimal_spec()
    wildcard_spec["paths"] = {
        "/pets": {
            "post": {
                "requestBody": {
                    "content": {
                        "text/plain": {"schema": {"type": "string"}},
                        "application/*": {"schema": {"type": "integer"}},
                    }
                },
                "responses": {"200": {"description": "ok"}},
            }
        }
    }

    [wildcard_operation] = extract_operations(wildcard_spec)

    assert wildcard_operation.request_body is not None
    assert wildcard_operation.request_body.type == "integer"

    fallback_spec = _minimal_spec()
    fallback_spec["paths"] = {
        "/pets": {
            "post": {
                "requestBody": {
                    "content": {
                        "text/plain": {"schema": {"type": "string"}},
                        "application/xml": {"schema": {"type": "object"}},
                    }
                },
                "responses": {"200": {"description": "ok"}},
            }
        }
    }

    [fallback_operation] = extract_operations(fallback_spec)

    assert fallback_operation.request_body is not None
    assert fallback_operation.request_body.type == "string"


def test_extract_operations_rejects_invalid_request_body_media_type_structures() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/pets": {
            "post": {
                "requestBody": {"content": {"application/json": "not-a-media-type-object"}},
                "responses": {"200": {"description": "ok"}},
            }
        }
    }

    with pytest.raises(SpecValidationError) as exc_info:
        extract_operations(spec)

    assert exc_info.value.errors == [
        {
            "field": "requestBody.content",
            "message": "requestBody.content must define at least one media type object.",
            "value": {"application/json": "not-a-media-type-object"},
        }
    ]


def test_extract_operations_rejects_duplicate_generated_operation_ids() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/pets/list": {"get": {"responses": {"200": {"description": "ok"}}}},
        "/pets//list": {"get": {"responses": {"200": {"description": "ok"}}}},
    }

    with pytest.raises(SpecValidationError) as exc_info:
        extract_operations(spec)

    assert exc_info.value.errors == [
        {
            "field": "operationId",
            "message": "Duplicate operationId detected: get_pets_list",
            "value": {"path": "/pets//list", "method": "get", "operationId": "get_pets_list"},
        }
    ]


def test_extract_operations_rejects_duplicate_explicit_operation_ids() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/pets": {"get": {"operationId": "listPets", "responses": {"200": {"description": "ok"}}}},
        "/animals": {"get": {"operationId": "listPets", "responses": {"200": {"description": "ok"}}}},
    }

    with pytest.raises(SpecValidationError) as exc_info:
        extract_operations(spec)

    assert exc_info.value.errors == [
        {
            "field": "operationId",
            "message": "Duplicate operationId detected: listPets",
            "value": {"path": "/animals", "method": "get", "operationId": "listPets"},
        }
    ]


def test_extract_operations_preserves_schema_nesting_depth() -> None:
    spec = _minimal_spec()
    spec["paths"] = {
        "/nested": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "level1": {
                                        "type": "object",
                                        "properties": {
                                            "level2": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {"level3": {"type": "string"}},
                                                },
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    }
                },
                "responses": {"200": {"description": "ok"}},
            }
        }
    }

    [operation] = extract_operations(spec)

    assert operation.request_body is not None
    assert operation.request_body.properties["level1"].properties["level2"].items is not None
    assert operation.request_body.properties["level1"].properties["level2"].items.properties["level3"].type == "string"
