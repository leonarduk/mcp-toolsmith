"""Specification loading utilities for local files and HTTPS URLs."""

from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

import httpcore
import httpx
import yaml  # type: ignore[import-untyped]


class SpecLoadError(Exception):
    """Raised when a specification cannot be loaded or parsed."""


class SSRFBlockedError(SpecLoadError):
    """Raised when a remote target is blocked by SSRF protection."""


class UnsupportedSchemeError(SpecLoadError):
    """Raised when a remote source uses an unsupported URL scheme."""


CONNECT_TIMEOUT_SECONDS = 10.0
READ_TIMEOUT_SECONDS = 30.0


class _ValidatedPublicIPBackend(httpcore.NetworkBackend):
    """Resolve HTTPS targets and connect only to validated public IPs."""

    def __init__(self) -> None:
        self._backend = httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.NetworkStream:
        addresses = _resolve_public_addresses(host, port)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return self._backend.connect_tcp(
                    host=address,
                    port=port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # pragma: no cover - exercised via httpcore/httpx integration.
                last_error = exc

        if last_error is not None:
            raise last_error
        raise SpecLoadError(f"Could not resolve remote spec host '{host}'.")

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Any = None,
    ) -> httpcore.NetworkStream:
        return self._backend.connect_unix_socket(path, timeout=timeout, socket_options=socket_options)

    def sleep(self, seconds: float) -> None:
        self._backend.sleep(seconds)


class _ResponseStream(httpx.SyncByteStream):
    """Wrap an httpcore stream for use in httpx responses."""

    def __init__(self, httpcore_stream: Any) -> None:
        self._httpcore_stream = httpcore_stream

    def __iter__(self) -> Any:
        yield from self._httpcore_stream

    def close(self) -> None:
        close = getattr(self._httpcore_stream, "close", None)
        if close is not None:
            close()


class _ValidatedHTTPTransport(httpx.BaseTransport):
    """HTTP transport backed by a validated-public-IP httpcore connection pool."""

    def __init__(self) -> None:
        self._pool = httpcore.ConnectionPool(network_backend=_ValidatedPublicIPBackend())

    def __enter__(self) -> _ValidatedHTTPTransport:
        self._pool.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        self._pool.__exit__(exc_type, exc_value, traceback)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        response = self._pool.handle_request(req)
        return httpx.Response(
            status_code=response.status,
            headers=response.headers,
            stream=_ResponseStream(response.stream),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self._pool.close()


def load_spec(source: str | Path) -> dict[str, Any]:
    """Load an OpenAPI document from a local file path or HTTPS URL.

    This helper is intentionally synchronous. Async callers should run it in a
    worker thread if they need to avoid blocking an event loop.
    """
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

    timeout = httpx.Timeout(READ_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS, pool=None)
    transport = _ValidatedHTTPTransport()

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport) as client:
            response = client.get(url)
            response.raise_for_status()
    except (httpx.TimeoutException, httpcore.TimeoutException) as exc:
        raise SpecLoadError(f"Timed out while fetching remote spec '{url}'.") from exc
    except (
        httpx.HTTPError,
        httpcore.NetworkError,
        httpcore.ProtocolError,
        httpcore.ProxyError,
    ) as exc:
        raise SpecLoadError(f"Failed to fetch remote spec '{url}': {exc}") from exc

    return _parse_spec(response.text, source=url)


def _resolve_public_addresses(hostname: str, port: int) -> list[str]:
    try:
        addrinfo = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SpecLoadError(f"Could not resolve remote spec host '{hostname}': {exc}") from exc

    if not addrinfo:
        raise SpecLoadError(f"Could not resolve remote spec host '{hostname}'.")

    addresses: list[str] = []
    blocked_addresses: list[str] = []
    for entry in addrinfo:
        sockaddr = entry[4]
        candidate = sockaddr[0]
        ip = ip_address(candidate)
        if not ip.is_global:
            blocked_addresses.append(str(ip))
            continue
        addresses.append(str(ip))

    if blocked_addresses:
        blocked = ", ".join(sorted(set(blocked_addresses)))
        raise SSRFBlockedError(
            f"Remote spec host '{hostname}' resolves to blocked non-public address(es): {blocked}."
        )

    if not addresses:
        raise SpecLoadError(f"Could not resolve remote spec host '{hostname}' to any public IP addresses.")

    return list(dict.fromkeys(addresses))


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
