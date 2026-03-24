"""Extract normalized operations from an OpenAPI 3.x document."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from mcp_toolsmith.deref import dereference_local_refs
from mcp_toolsmith.models import AuthType, HttpMethod, OperationModel, ParameterModel, SchemaModel
from mcp_toolsmith.validator import SpecValidationError
from mcp_toolsmith.validator import validate_spec

_HTTP_METHODS: tuple[HttpMethod, ...] = ("get", "post", "put", "patch", "delete", "options", "head")
_PATH_PARAMETER_PATTERN = re.compile(r"{([^}/]+)}")


def extract_operations(document: Mapping[str, Any]) -> list[OperationModel]:
    """Validate, dereference, and normalize OpenAPI operations.

    Args:
        document: Parsed OpenAPI document data.

    Returns:
        A list of normalized operation models derived from the spec.

    Raises:
        SpecValidationError: If the document is invalid, contains unresolved refs,
            or declares a path template variable without a matching parameter.
    """
    validate_spec(document)
    dereferenced = dereference_local_refs(document)
    components = dereferenced.get("components")
    security_schemes = _extract_security_schemes(components)
    global_security = dereferenced.get("security")
    paths = cast(Mapping[str, Any], dereferenced["paths"])
    operations: list[OperationModel] = []
    generated_operation_ids: set[str] = set()

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
            _validate_path_parameters(source_path, merged_parameters)
            grouped = _group_parameters(merged_parameters)
            operation_id = _operation_id(source_path, method, operation.get("operationId"))
            if operation_id in generated_operation_ids:
                raise SpecValidationError(
                    "Invalid OpenAPI specification.",
                    errors=[
                        {
                            "field": "operationId",
                            "message": f"Duplicate operationId detected: {operation_id}",
                            "value": {"path": source_path, "method": method, "operationId": operation_id},
                        }
                    ],
                )
            generated_operation_ids.add(operation_id)
            operations.append(
                _build_operation_model(
                    source_path=source_path,
                    method=method,
                    operation=operation,
                    grouped=grouped,
                    operation_id=operation_id,
                    security_schemes=security_schemes,
                    global_security=global_security,
                )
            )
    return operations


def _build_operation_model(
    source_path: str,
    method: HttpMethod,
    operation: Mapping[str, Any],
    grouped: dict[str, list[ParameterModel]],
    operation_id: str,
    security_schemes: Mapping[str, Mapping[str, Any]],
    global_security: Any,
) -> OperationModel:
    auth_type, auth_name = _resolve_operation_auth(
        operation_security=operation.get("security"),
        global_security=global_security,
        security_schemes=security_schemes,
    )
    return OperationModel(
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
        auth_type=auth_type,
        auth_name=auth_name,
    )


def _extract_security_schemes(raw_components: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(raw_components, Mapping):
        return {}
    raw_security_schemes = raw_components.get("securitySchemes")
    if not isinstance(raw_security_schemes, Mapping):
        return {}
    return {
        str(name): value
        for name, value in raw_security_schemes.items()
        if isinstance(value, Mapping)
    }


def _resolve_operation_auth(
    operation_security: Any,
    global_security: Any,
    security_schemes: Mapping[str, Mapping[str, Any]],
) -> tuple[AuthType, str | None]:
    # Operation-level security overrides global security.
    candidates = operation_security if operation_security is not None else global_security
    if not isinstance(candidates, list):
        return ("none", None)
    for requirement in candidates:
        if requirement == {}:
            return ("none", None)
        if not isinstance(requirement, Mapping):
            continue
        for scheme_name in requirement.keys():
            scheme = security_schemes.get(str(scheme_name))
            if not isinstance(scheme, Mapping):
                continue
            scheme_type = _clean_str(scheme.get("type"))
            if scheme_type == "http" and _clean_str(scheme.get("scheme")) == "bearer":
                return ("http_bearer", None)
            if scheme_type == "apiKey":
                location = _clean_str(scheme.get("in"))
                param_name = _clean_str(scheme.get("name"))
                if location == "header" and param_name:
                    return ("api_key_header", param_name)
                if location == "query" and param_name:
                    return ("api_key_query", param_name)
    return ("none", None)


def _normalize_parameters(raw_parameters: Any) -> list[ParameterModel]:
    """Convert OpenAPI parameter objects into normalized parameter models."""

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
    """Merge path- and operation-level parameters, preferring operation values."""

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
    """Build a normalized schema tree from raw OpenAPI schema data."""

    if not isinstance(raw_schema, Mapping):
        return None
    raw_all_of = raw_schema.get("allOf")
    if isinstance(raw_all_of, list):
        merged = _merge_all_of_schemas(raw_schema, raw_all_of)
        if merged is not None:
            return merged
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


def _merge_all_of_schemas(raw_schema: Mapping[str, Any], all_of: list[Any]) -> SchemaModel | None:
    merged_properties: dict[str, SchemaModel] = {}
    merged_required: list[str] = []
    has_merged_schema = False

    for item in all_of:
        nested = _schema_from_raw(item)
        if nested is None:
            continue
        has_merged_schema = True
        merged_properties.update(nested.properties)
        for required_name in nested.required:
            if required_name not in merged_required:
                merged_required.append(required_name)

    if not has_merged_schema:
        return None

    return SchemaModel(
        type="object",
        description=_clean_str(raw_schema.get("description")),
        properties=merged_properties,
        required=merged_required,
        raw_schema=dict(raw_schema),
    )


def _extract_request_body(raw_request_body: Any) -> SchemaModel | None:
    """Extract a preferred request-body schema from the content map.

    Args:
        raw_request_body: The raw OpenAPI requestBody object.

    Returns:
        The preferred request body schema, or ``None`` if no valid media type
        schema is defined.

    Raises:
        SpecValidationError: If the request body content contains invalid
            media-type structures.
    """

    if not isinstance(raw_request_body, Mapping):
        return None
    content = raw_request_body.get("content")
    if not isinstance(content, Mapping):
        return None
    valid_media_types = [(str(media_type), media_value) for media_type, media_value in content.items() if isinstance(media_value, Mapping)]
    if not valid_media_types:
        raise SpecValidationError(
            "Invalid OpenAPI specification.",
            errors=[{"field": "requestBody.content", "message": "requestBody.content must define at least one media type object.", "value": dict(content)}],
        )
    preferred = _select_media_type(valid_media_types)
    if preferred is None:
        return None
    return _schema_from_raw(preferred.get("schema"))


def _extract_responses(raw_responses: Any) -> dict[str, SchemaModel | None]:
    """Extract the first schema available for each response status code."""

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
    """Normalize tag strings by removing empty or whitespace-only entries."""

    if not isinstance(raw_tags, list):
        return []
    return [tag.strip() for tag in raw_tags if isinstance(tag, str) and tag.strip()]


def _clean_str(value: Any) -> str | None:
    """Return a stripped string value, or ``None`` for missing/blank inputs."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _operation_id(source_path: str, method: str, raw_operation_id: Any) -> str:
    """Return an explicit operationId or a deterministic fallback identifier."""

    if isinstance(raw_operation_id, str) and raw_operation_id.strip():
        return raw_operation_id.strip()
    normalized_path = re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", source_path.strip("/").lower())).strip("_") or "root"
    return f"{method}_{normalized_path}"


def _select_media_type(media_types: list[tuple[str, Mapping[str, Any]]]) -> Mapping[str, Any] | None:
    """Choose a deterministic request-body media type.

    Preference order:
    1. ``application/json``
    2. ``application/*`` wildcard media types
    3. The first defined valid media type
    """

    exact_json = next((media for media_type, media in media_types if media_type == "application/json"), None)
    if exact_json is not None:
        return exact_json

    wildcard_application = next(
        (media for media_type, media in media_types if media_type.startswith("application/") and "*" in media_type),
        None,
    )
    if wildcard_application is not None:
        return wildcard_application

    return media_types[0][1] if media_types else None


def _validate_path_parameters(source_path: str, parameters: list[ParameterModel]) -> None:
    """Ensure every path template variable has a corresponding path parameter."""

    required_parameters = {match.group(1) for match in _PATH_PARAMETER_PATTERN.finditer(source_path)}
    defined_parameters = {parameter.name for parameter in parameters if parameter.location == "path"}
    missing_parameters = sorted(required_parameters - defined_parameters)
    if not missing_parameters:
        return
    raise SpecValidationError(
        "Invalid OpenAPI specification.",
        errors=[
            {
                "field": "paths",
                "message": f"Path template parameters are missing definitions for {missing_parameters}.",
                "value": {"path": source_path, "missing": missing_parameters},
            }
        ],
    )
