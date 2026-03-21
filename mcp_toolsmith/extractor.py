"""Extract normalized operations from an OpenAPI 3.x document."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from mcp_toolsmith.deref import dereference_local_refs
from mcp_toolsmith.models import HttpMethod, OperationModel, ParameterModel, SchemaModel
from mcp_toolsmith.validator import validate_spec

_HTTP_METHODS: tuple[HttpMethod, ...] = ("get", "post", "put", "patch", "delete", "options", "head")


def extract_operations(document: Mapping[str, Any]) -> list[OperationModel]:
    """Validate, dereference, and normalize OpenAPI operations."""
    validate_spec(document)
    dereferenced = dereference_local_refs(document)
    paths = cast(Mapping[str, Any], dereferenced["paths"])
    operations: list[OperationModel] = []

    for source_path, path_item_value in paths.items():
        if not isinstance(path_item_value, Mapping):
            continue
        path_item = cast(Mapping[str, Any], path_item_value)
        path_parameters = _normalize_parameters(path_item.get("parameters", []))
        for method in _HTTP_METHODS:
            operation_value = path_item.get(method)
            if not isinstance(operation_value, Mapping):
                continue
            operation = cast(Mapping[str, Any], operation_value)
            merged_parameters = _merge_parameters(path_parameters, _normalize_parameters(operation.get("parameters", [])))
            grouped = _group_parameters(merged_parameters)
            operation_id = _operation_id(source_path, method, operation.get("operationId"))
            operations.append(
                OperationModel(
                    source_path=source_path,
                    http_method=method,
                    operation_id=operation_id,
                    summary=_clean_str(operation.get("summary")),
                    description=_clean_str(operation.get("description")),
                    tags=_normalize_tags(operation.get("tags")),
                    deprecated=bool(operation.get("deprecated", False)),
                    path_params=grouped["path"],
                    query_params=grouped["query"],
                    header_params=grouped["header"],
                    cookie_params=grouped["cookie"],
                    request_body=_extract_request_body(operation.get("requestBody")),
                    responses=_extract_responses(operation.get("responses", {})),
                )
            )
    return operations


def _normalize_parameters(raw_parameters: Any) -> list[ParameterModel]:
    if not isinstance(raw_parameters, list):
        return []
    parameters: list[ParameterModel] = []
    for parameter in raw_parameters:
        if not isinstance(parameter, Mapping):
            continue
        location = parameter.get("in")
        name = parameter.get("name")
        if location not in {"path", "query", "header", "cookie"} or not isinstance(name, str):
            continue
        required = bool(parameter.get("required", False)) or location == "path"
        parameters.append(
            ParameterModel(
                name=name,
                location=location,
                required=required,
                description=_clean_str(parameter.get("description")),
                schema_model=_schema_from_raw(parameter.get("schema")),
                style=_clean_str(parameter.get("style")),
                explode=parameter.get("explode") if isinstance(parameter.get("explode"), bool) else None,
            )
        )
    return parameters


def _merge_parameters(path_parameters: list[ParameterModel], operation_parameters: list[ParameterModel]) -> list[ParameterModel]:
    merged: dict[tuple[str, str], ParameterModel] = {(param.location, param.name): param for param in path_parameters}
    for param in operation_parameters:
        merged[(param.location, param.name)] = param
    return list(merged.values())


def _group_parameters(parameters: list[ParameterModel]) -> dict[str, list[ParameterModel]]:
    grouped: dict[str, list[ParameterModel]] = {"path": [], "query": [], "header": [], "cookie": []}
    for parameter in parameters:
        grouped[parameter.location].append(parameter)
    return grouped


def _schema_from_raw(raw_schema: Any) -> SchemaModel | None:
    if not isinstance(raw_schema, Mapping):
        return None
    properties: dict[str, SchemaModel] = {}
    raw_properties = raw_schema.get("properties")
    if isinstance(raw_properties, Mapping):
        for key, value in raw_properties.items():
            nested = _schema_from_raw(value)
            if nested is not None:
                properties[str(key)] = nested
    items = _schema_from_raw(raw_schema.get("items"))
    raw_enum_values = raw_schema.get("enum")
    enum_values = raw_enum_values if isinstance(raw_enum_values, list) else []
    raw_required = raw_schema.get("required")
    required = raw_required if isinstance(raw_required, list) else []
    return SchemaModel(
        type=_clean_str(raw_schema.get("type")),
        format=_clean_str(raw_schema.get("format")),
        description=_clean_str(raw_schema.get("description")),
        enum=list(enum_values),
        default=raw_schema.get("default"),
        properties=properties,
        items=items,
        required=[str(item) for item in required],
        raw_schema=dict(raw_schema),
    )


def _extract_request_body(raw_request_body: Any) -> SchemaModel | None:
    if not isinstance(raw_request_body, Mapping):
        return None
    content = raw_request_body.get("content")
    if not isinstance(content, Mapping):
        return None
    preferred = None
    for media_type in ("application/json", "application/*+json"):
        if media_type in content and isinstance(content[media_type], Mapping):
            preferred = content[media_type]
            break
    if preferred is None:
        for media in content.values():
            if isinstance(media, Mapping):
                preferred = media
                break
    if preferred is None:
        return None
    return _schema_from_raw(preferred.get("schema"))


def _extract_responses(raw_responses: Any) -> dict[str, SchemaModel | None]:
    if not isinstance(raw_responses, Mapping):
        return {}
    responses: dict[str, SchemaModel | None] = {}
    for status_code, response in raw_responses.items():
        if not isinstance(response, Mapping):
            continue
        content = response.get("content")
        schema: SchemaModel | None = None
        if isinstance(content, Mapping):
            for media in content.values():
                if isinstance(media, Mapping):
                    schema = _schema_from_raw(media.get("schema"))
                    if schema is not None:
                        break
        responses[str(status_code)] = schema
    return responses


def _normalize_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    return [tag.strip() for tag in raw_tags if isinstance(tag, str) and tag.strip()]


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _operation_id(source_path: str, method: str, raw_operation_id: Any) -> str:
    if isinstance(raw_operation_id, str) and raw_operation_id.strip():
        return raw_operation_id.strip()
    normalized_path = source_path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
    return f"{method}_{normalized_path}"
