"""Local OpenAPI $ref dereferencing."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any, cast

from mcp_toolsmith.validator import SpecValidationError


class _RefResolver:
    def __init__(self, document: Mapping[str, Any]) -> None:
        self.document = document

    def dereference(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._resolve_node(deepcopy(dict(self.document)), stack=[]))

    def _resolve_node(self, node: Any, *, stack: list[str]) -> Any:
        if isinstance(node, Mapping):
            if "$ref" in node:
                ref = node["$ref"]
                if not isinstance(ref, str):
                    raise SpecValidationError("Invalid OpenAPI specification.", errors=[{"field": "$ref", "message": "$ref must be a string.", "value": ref}])
                return self._resolve_ref(ref, stack=stack)
            return {key: self._resolve_node(value, stack=stack) for key, value in node.items()}
        if isinstance(node, list):
            return [self._resolve_node(item, stack=stack) for item in node]
        return node

    def _resolve_ref(self, ref: str, *, stack: list[str]) -> Any:
        if not ref.startswith("#/"):
            raise SpecValidationError(
                "Invalid OpenAPI specification.",
                errors=[{"field": "$ref", "message": f"External $ref values are not supported: {ref}", "value": ref}],
            )
        if ref in stack:
            cycle = " -> ".join([*stack, ref])
            raise SpecValidationError(
                "Invalid OpenAPI specification.",
                errors=[{"field": "$ref", "message": f"Circular $ref detected: {cycle}", "value": ref}],
            )

        target: Any = self.document
        for token in ref.removeprefix("#/").split("/"):
            key = token.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, Mapping) or key not in target:
                raise SpecValidationError(
                    "Invalid OpenAPI specification.",
                    errors=[{"field": "$ref", "message": f"Unresolvable local $ref: {ref}", "value": ref}],
                )
            target = target[key]

        return self._resolve_node(deepcopy(target), stack=[*stack, ref])



def dereference_local_refs(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied document with local refs expanded inline."""

    return _RefResolver(document).dereference()
