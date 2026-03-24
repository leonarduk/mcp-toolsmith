"""Normalized OpenAPI models used by the ingestion pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

HttpMethod = Literal["get", "post", "put", "patch", "delete", "options", "head"]
ParameterLocation = Literal["path", "query", "header", "cookie"]
AuthType = Literal["none", "http_bearer", "api_key_header", "api_key_query"]


class SpecMeta(BaseModel):
    """Top-level OpenAPI metadata extracted from the source document."""

    model_config = ConfigDict(extra="ignore")

    openapi: str
    title: str
    version: str
    description: str | None = None


class SchemaModel(BaseModel):
    """A lightweight normalized schema wrapper."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None
    format: str | None = None
    description: str | None = None
    enum: list[Any] = Field(default_factory=list)
    default: Any | None = None
    properties: dict[str, "SchemaModel"] = Field(default_factory=dict)
    items: "SchemaModel | None" = None
    required: list[str] = Field(default_factory=list)
    raw_schema: dict[str, Any] = Field(default_factory=dict)


class ParameterModel(BaseModel):
    """Normalized operation parameter."""

    model_config = ConfigDict(extra="ignore")

    name: str
    location: ParameterLocation
    required: bool = False
    description: str | None = None
    schema_model: SchemaModel | None = None
    style: str | None = None
    explode: bool | None = None


class OperationModel(BaseModel):
    """Normalized representation of a single OpenAPI operation."""

    model_config = ConfigDict(extra="ignore")

    source_path: str
    http_method: HttpMethod
    operation_id: str
    summary: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    deprecated: bool = False
    path_params: list[ParameterModel] = Field(default_factory=list)
    query_params: list[ParameterModel] = Field(default_factory=list)
    header_params: list[ParameterModel] = Field(default_factory=list)
    cookie_params: list[ParameterModel] = Field(default_factory=list)
    request_body: SchemaModel | None = None
    responses: dict[str, SchemaModel | None] = Field(default_factory=dict)
    auth_type: AuthType = "none"
    auth_name: str | None = None


def rebuild_models() -> None:
    """Rebuild deferred model references for runtime use."""

    SchemaModel.model_rebuild()


if not TYPE_CHECKING:
    rebuild_models()
