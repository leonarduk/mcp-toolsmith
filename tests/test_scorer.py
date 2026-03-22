"""Tests for quality scoring."""

from __future__ import annotations

from mcp_toolsmith.models import OperationModel, ParameterModel, SchemaModel
from mcp_toolsmith.scorer import score_operations


def _parameter(
    name: str,
    *,
    required: bool = False,
    description: str | None = "Parameter description",
    schema_type: str | None = "string",
) -> ParameterModel:
    return ParameterModel(
        name=name,
        location="path" if required else "query",
        required=required,
        description=description,
        schema_model=SchemaModel(type=schema_type) if schema_type is not None else None,
    )


def _operation(**overrides: object) -> OperationModel:
    data: dict[str, object] = {
        "source_path": "/users/{user_id}",
        "http_method": "get",
        "operation_id": "get_user",
        "summary": "Get a user",
        "description": None,
        "path_params": [_parameter("user_id", required=True)],
        "query_params": [_parameter("verbose")],
        "header_params": [],
        "cookie_params": [],
        "request_body": SchemaModel(
            type="object",
            properties={
                "name": SchemaModel(type="string"),
                "age": SchemaModel(type="integer"),
            },
        ),
        "responses": {},
    }
    data.update(overrides)
    return OperationModel(**data)


def test_score_operations_returns_perfect_score_for_high_quality_operations() -> None:
    result = score_operations([_operation()])

    assert result.total == 100
    assert result.dimensions == {
        "naming": 25,
        "safety": 25,
        "schema_coverage": 25,
        "usability": 25,
    }
    assert result.findings == []


def test_score_operations_returns_zero_for_comprehensively_bad_operation() -> None:
    result = score_operations(
        [
            _operation(
                source_path="/users/{user_id}",
                http_method="delete",
                operation_id="DeleteUserWithAnExtremelyLongIdentifierThatFails",
                summary=None,
                description=None,
                path_params=[],
                query_params=[_parameter("verbose", description=None, schema_type=None)],
                request_body=SchemaModel(type="object", properties={"payload": SchemaModel(type="any")}),
            )
        ]
    )

    assert result.total == 0
    assert result.dimensions == {
        "naming": 0,
        "safety": 0,
        "schema_coverage": 0,
        "usability": 0,
    }
    assert {finding.operation_id for finding in result.findings} == {"DeleteUserWithAnExtremelyLongIdentifierThatFails"}


def test_score_operations_can_fail_only_naming_dimension() -> None:
    result = score_operations([_operation(operation_id="getUser")])

    assert result.dimensions["naming"] < 25
    assert result.dimensions["safety"] == 25
    assert result.dimensions["schema_coverage"] == 25
    assert result.dimensions["usability"] == 25


def test_score_operations_can_fail_only_safety_dimension() -> None:
    result = score_operations([_operation(http_method="delete")])

    assert result.dimensions["naming"] == 25
    assert result.dimensions["safety"] == 12
    assert result.dimensions["schema_coverage"] == 25
    assert result.dimensions["usability"] == 25


def test_score_operations_can_fail_only_schema_coverage_dimension() -> None:
    result = score_operations([
        _operation(
            query_params=[_parameter("verbose", schema_type=None)],
            request_body=SchemaModel(type="object", properties={"payload": SchemaModel(type="object")}),
        )
    ])

    assert result.dimensions["naming"] == 25
    assert result.dimensions["safety"] == 25
    assert result.dimensions["schema_coverage"] < 25
    assert result.dimensions["usability"] == 25


def test_score_operations_can_fail_only_usability_dimension() -> None:
    result = score_operations([
        _operation(
            summary=None,
            description=None,
            path_params=[_parameter("user_id", required=True, description=None)],
            query_params=[_parameter("verbose", description=None)],
        )
    ])

    assert result.dimensions["naming"] == 25
    assert result.dimensions["safety"] == 25
    assert result.dimensions["schema_coverage"] == 25
    assert result.dimensions["usability"] == 0


def test_score_operations_allows_unsafe_methods_when_requested() -> None:
    result = score_operations([_operation(http_method="delete")], allow_unsafe=True)

    assert result.dimensions["safety"] == 25
