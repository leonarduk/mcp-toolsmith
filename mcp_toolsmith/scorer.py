"""Quality scoring for normalized OpenAPI operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Literal
import re

from mcp_toolsmith.models import OperationModel, ParameterModel, SchemaModel

_UNSAFE_METHODS = {"delete", "put", "patch"}
_ACTION_OBJECT_PATTERN = re.compile(r"^[a-z][a-z0-9]*_[a-z0-9]+(?:_[a-z0-9]+)*$")
_SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
_PATH_PARAMETER_PATTERN = re.compile(r"{([^}/]+)}")


@dataclass(frozen=True)
class Finding:
    """A single scorer finding tied to one operation."""

    level: Literal["error", "warning", "info"]
    dimension: str
    operation_id: str
    message: str


@dataclass(frozen=True)
class ScoringResult:
    """Deterministic quality-scoring output for a batch of operations."""

    total: int
    dimensions: dict[str, int]
    findings: list[Finding]


def score_operations(
    ops: list[OperationModel], *, allow_unsafe: bool = False
) -> ScoringResult:
    """Score normalized operations across naming, safety, schema coverage, and usability."""

    dimensions = {
        "naming": _score_naming(ops),
        "safety": _score_safety(ops, allow_unsafe=allow_unsafe),
        "schema_coverage": _score_schema_coverage(ops),
        "usability": _score_usability(ops),
    }
    findings = sorted(
        [finding for result in dimensions.values() for finding in result.findings],
        # Keep findings grouped consistently for deterministic CLI/test output.
        key=lambda finding: (
            finding.dimension,
            finding.operation_id,
            finding.level,
            finding.message,
        ),
    )
    dimension_scores = {name: result.score for name, result in dimensions.items()}
    return ScoringResult(
        total=sum(dimension_scores.values()),
        dimensions=dimension_scores,
        findings=findings,
    )


@dataclass(frozen=True)
class _DimensionResult:
    score: int
    findings: list[Finding]


def _score_naming(ops: list[OperationModel]) -> _DimensionResult:
    checks: list[bool] = []
    findings: list[Finding] = []
    for op in ops:
        checks.append(bool(_SNAKE_CASE_PATTERN.fullmatch(op.operation_id)))
        if not checks[-1]:
            findings.append(
                Finding(
                    "warning",
                    "naming",
                    op.operation_id,
                    "operation_id should be snake_case.",
                )
            )

        checks.append(bool(_ACTION_OBJECT_PATTERN.fullmatch(op.operation_id)))
        if not checks[-1]:
            findings.append(
                Finding(
                    "warning",
                    "naming",
                    op.operation_id,
                    "operation_id should follow an action_object naming pattern.",
                )
            )

        checks.append(len(op.operation_id) < 40)
        if not checks[-1]:
            findings.append(
                Finding(
                    "warning",
                    "naming",
                    op.operation_id,
                    "operation_id should be shorter than 40 characters.",
                )
            )
    return _DimensionResult(_ratio_score(checks), findings)


def _score_safety(ops: list[OperationModel], *, allow_unsafe: bool) -> _DimensionResult:
    checks: list[bool] = []
    findings: list[Finding] = []
    for op in ops:
        is_safe_method = allow_unsafe or op.http_method not in _UNSAFE_METHODS
        checks.append(is_safe_method)
        if not is_safe_method:
            findings.append(
                Finding(
                    "error",
                    "safety",
                    op.operation_id,
                    f"{op.http_method.upper()} requires the --unsafe flag.",
                )
            )

        declared_path_params = {param.name for param in op.path_params}
        expected_path_params = set(_PATH_PARAMETER_PATTERN.findall(op.source_path))
        all_required_present = declared_path_params == expected_path_params
        checks.append(all_required_present)
        if not all_required_present:
            missing = sorted(expected_path_params - declared_path_params)
            findings.append(
                Finding(
                    "error",
                    "safety",
                    op.operation_id,
                    f"required path parameters are missing definitions: {', '.join(missing)}",
                )
            )
    return _DimensionResult(_ratio_score(checks), findings)


def _score_schema_coverage(ops: list[OperationModel]) -> _DimensionResult:
    checks: list[bool] = []
    findings: list[Finding] = []
    for op in ops:
        for param in _iter_parameters(op):
            covered = _schema_is_typed(param.schema_model)
            checks.append(covered)
            if not covered:
                findings.append(
                    Finding(
                        "warning",
                        "schema_coverage",
                        op.operation_id,
                        f"parameter '{param.name}' is missing a concrete schema type.",
                    )
                )

        body_covered, body_messages = _schema_properties_are_typed(op.request_body)
        checks.extend(body_covered)
        findings.extend(
            Finding("warning", "schema_coverage", op.operation_id, message)
            for message in body_messages
        )
    return _DimensionResult(_ratio_score(checks), findings)


def _score_usability(ops: list[OperationModel]) -> _DimensionResult:
    checks: list[bool] = []
    findings: list[Finding] = []
    for op in ops:
        has_summary = bool(op.summary or op.description)
        checks.append(has_summary)
        if not has_summary:
            findings.append(
                Finding(
                    "info",
                    "usability",
                    op.operation_id,
                    "operation should include a summary or description.",
                )
            )

        for param in _iter_parameters(op):
            has_description = bool(param.description)
            checks.append(has_description)
            if not has_description:
                findings.append(
                    Finding(
                        "info",
                        "usability",
                        op.operation_id,
                        f"parameter '{param.name}' should include a description.",
                    )
                )
    return _DimensionResult(_ratio_score(checks), findings)


def _iter_parameters(op: OperationModel) -> Iterator[ParameterModel]:
    yield from op.path_params
    yield from op.query_params
    yield from op.header_params
    yield from op.cookie_params


def _ratio_score(checks: list[bool]) -> int:
    if not checks:
        return 25
    passed = sum(1 for check in checks if check)
    return (passed * 25) // len(checks)


def _schema_is_typed(schema: SchemaModel | None) -> bool:
    return schema is not None and schema.type not in {None, "object", "any"}


def _schema_properties_are_typed(
    schema: SchemaModel | None, *, path: str = "requestBody"
) -> tuple[list[bool], list[str]]:
    if schema is None:
        return [True], []

    checks: list[bool] = []
    messages: list[str] = []

    if schema.properties:
        for name in sorted(schema.properties):
            prop = schema.properties[name]
            prop_path = f"{path}.{name}"
            typed = prop.type not in {None, "object", "any"}
            checks.append(typed)
            if not typed:
                messages.append(f"{prop_path} is missing a concrete schema type.")
            # Intentionally recurse even when the property itself fails the type check:
            # this allows leaf nodes under an untyped intermediate object to still
            # contribute passing checks, producing a graded score rather than all-or-nothing.
            nested_checks, nested_messages = _schema_properties_are_typed(
                prop, path=prop_path
            )
            checks.extend(nested_checks)
            messages.extend(nested_messages)
    elif schema.items is not None:
        item_typed = schema.items.type not in {None, "object", "any"}
        checks.append(item_typed)
        if not item_typed:
            messages.append(f"{path}[] is missing a concrete schema type.")
        nested_checks, nested_messages = _schema_properties_are_typed(
            schema.items, path=f"{path}[]"
        )
        checks.extend(nested_checks)
        messages.extend(nested_messages)
    else:
        checks.append(schema.type not in {None, "object", "any"})
        if not checks[-1]:
            messages.append(f"{path} is missing a concrete schema type.")

    return checks, messages
