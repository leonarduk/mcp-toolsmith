"""Specification loading utilities for local files and HTTPS URLs."""

from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml


class SpecLoadError(Exception):
    """Raised when a specification cannot be loaded or parsed."""


class SSRFBlockedError(SpecLoadError):
    """Raised when a remote target is blocked by SSRF protection."""


class UnsupportedSchemeError(SpecLoadError):
    """Raised when a remote source uses an unsupported URL scheme."""


CONNECT_TIMEOUT_SECONDS = 10.0
READ_TIMEOUT_SECONDS = 30.0


def load_spec(source: str | Path) -> dict[str, Any]:
    """Load an OpenAPI document from a local file path or HTTPS URL."""
    if isinstance(source, Path):
        return _load_local_spec(source)

    parsed = urlparse(source)
    if parsed.scheme:
        return _load_remote_spec(source)

    return _load_local_spec(Path(source))


def _load_local_spec(path: Path) -> dict[str, Any]:
    try:
        raw_content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SpecLoadError(f"Failed to read local spec file '{path}': {exc}") from exc

    return _parse_spec(raw_content, source=str(path))


def _load_remote_spec(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise UnsupportedSchemeError(
            "Remote specs must use an https:// URL; http://, file://, and other schemes are not supported."
        )
    if not parsed.hostname:
        raise SpecLoadError("Remote spec URL must include a hostname.")

    _ensure_public_remote_target(parsed.hostname)

    timeout = httpx.Timeout(connect=CONNECT_TIMEOUT_SECONDS, read=READ_TIMEOUT_SECONDS, write=READ_TIMEOUT_SECONDS, pool=CONNECT_TIMEOUT_SECONDS)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise SpecLoadError(f"Timed out while fetching remote spec '{url}'.") from exc
    except httpx.HTTPError as exc:
        raise SpecLoadError(f"Failed to fetch remote spec '{url}': {exc}") from exc

    return _parse_spec(response.text, source=url)


def _ensure_public_remote_target(hostname: str) -> None:
    try:
        addrinfo = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SpecLoadError(f"Could not resolve remote spec host '{hostname}': {exc}") from exc

    blocked_addresses: list[str] = []
    for entry in addrinfo:
        sockaddr = entry[4]
        candidate = sockaddr[0]
        ip = ip_address(candidate)
        if ip.is_loopback or ip.is_private:
            blocked_addresses.append(str(ip))

    if blocked_addresses:
        blocked = ", ".join(sorted(set(blocked_addresses)))
        raise SSRFBlockedError(
            f"Remote spec host '{hostname}' resolves to blocked private or loopback address(es): {blocked}."
        )


def _parse_spec(raw_content: str, *, source: str) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(raw_content)
    except yaml.YAMLError:
        try:
            parsed = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise SpecLoadError(f"Failed to parse spec from '{source}' as YAML or JSON: {exc}") from exc

    if not isinstance(parsed, Mapping):
        raise SpecLoadError(f"Spec from '{source}' must parse to a JSON object / YAML mapping.")

    return dict(parsed)
