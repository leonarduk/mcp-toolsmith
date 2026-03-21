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
        """Expand local JSON Pointer references into a deep-copied document."""

        return cast(dict[str, Any], self._resolve_node(deepcopy(dict(self.document)), stack=None))

    def _resolve_node(self, node: Any, *, stack: list[str] | None) -> Any:
        """Resolve refs recursively while tracking the active reference chain."""

        active_stack = [] if stack is None else stack
        if isinstance(node, Mapping):
            if "$ref" in node:
                ref = node["$ref"]
                if not isinstance(ref, str):
                    raise SpecValidationError("Invalid OpenAPI specification.", errors=[{"field": "$ref", "message": "$ref must be a string.", "value": ref}])
                return self._resolve_ref(ref, stack=active_stack)
            return {key: self._resolve_node(value, stack=active_stack) for key, value in node.items()}
        if isinstance(node, list):
            return [self._resolve_node(item, stack=active_stack) for item in node]
        return node

    def _resolve_ref(self, ref: str, *, stack: list[str]) -> Any:
        """Resolve a local JSON Pointer and recursively expand its target.

        OpenAPI uses JSON Pointer fragments for local `$ref` values. Pointer tokens
        are split on `/`, then unescaped token-by-token so `~0` becomes `~` and
        `~1` becomes `/` without double-decoding overlapping sequences.
        """

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
            key = _unescape_json_pointer_token(token)
            if not isinstance(target, Mapping) or key not in target:
                raise SpecValidationError(
                    "Invalid OpenAPI specification.",
                    errors=[{"field": "$ref", "message": f"Unresolvable local $ref: {ref}", "value": ref}],
                )
            target = target[key]

        return self._resolve_node(deepcopy(target), stack=[*stack, ref])

def dereference_local_refs(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep-copied document with local refs expanded inline.

    The resolver only supports local references (`#/...`) and raises structured
    validation errors for invalid pointer syntax, unresolved tokens, external
    references, or circular reference chains.
    """

    return _RefResolver(document).dereference()


def _unescape_json_pointer_token(token: str) -> str:
    """Decode a single JSON Pointer token.

    Malformed escape sequences now raise structured validation errors instead of
    being silently tolerated.
    """

    characters: list[str] = []
    index = 0
    while index < len(token):
        if token[index] != "~":
            characters.append(token[index])
            index += 1
            continue
        if index + 1 >= len(token):
            raise SpecValidationError(
                "Invalid OpenAPI specification.",
                errors=[
                    {
                        "field": "$ref",
                        "message": f"Invalid JSON Pointer escape sequence in token: {token}",
                        "value": token,
                    }
                ],
            )

        escaped = token[index + 1]
        if escaped == "0":
            characters.append("~")
            index += 2
            continue
        if escaped == "1":
            characters.append("/")
            index += 2
            continue

        raise SpecValidationError(
            "Invalid OpenAPI specification.",
            errors=[
                {
                    "field": "$ref",
                    "message": f"Invalid JSON Pointer escape sequence in token: {token}",
                    "value": token,
                }
            ],
        )
    return "".join(characters)
