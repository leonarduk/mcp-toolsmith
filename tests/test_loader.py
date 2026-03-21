"""Tests for local and remote spec loading."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import httpx
import pytest

from mcp_toolsmith import loader
from mcp_toolsmith.loader import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    SSRFBlockedError,
    SpecLoadError,
    UnsupportedSchemeError,
    load_spec,
)


def test_load_spec_reads_local_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec_path = tmp_path / "openapi.yaml"
    spec_path.write_text("openapi: 3.0.0\ninfo:\n  title: Sample\n  version: 1.0.0\n", encoding="utf-8")

    def _unexpected_getaddrinfo(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("network resolution should not happen for local files")

    monkeypatch.setattr(socket, "getaddrinfo", _unexpected_getaddrinfo)

    loaded = load_spec(spec_path)

    assert loaded["openapi"] == "3.0.0"
    assert loaded["info"]["title"] == "Sample"


def test_load_spec_reads_local_json(tmp_path: Path) -> None:
    spec_path = tmp_path / "openapi.json"
    spec_path.write_text('{"openapi": "3.1.0", "info": {"title": "JSON", "version": "1.0.0"}}', encoding="utf-8")

    loaded = load_spec(spec_path)

    assert loaded == {"openapi": "3.1.0", "info": {"title": "JSON", "version": "1.0.0"}}


def test_load_spec_reads_https_url(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: dict[str, Any] = {}

    class _FakeResponse:
        text = 'openapi: 3.0.3\ninfo:\n  title: Remote\n  version: 1.0.0\n'

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *, timeout: httpx.Timeout, follow_redirects: bool, transport: Any) -> None:
            requested["timeout"] = timeout
            requested["follow_redirects"] = follow_redirects
            requested["transport"] = transport

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def get(self, url: str) -> _FakeResponse:
            requested["url"] = url
            return _FakeResponse()

    monkeypatch.setattr(httpx, "Client", _FakeClient)

    loaded = load_spec("https://example.com/openapi.yaml")

    assert loaded["info"]["title"] == "Remote"
    assert requested["url"] == "https://example.com/openapi.yaml"
    assert requested["follow_redirects"] is True
    assert requested["timeout"].connect == CONNECT_TIMEOUT_SECONDS
    assert requested["timeout"].read == READ_TIMEOUT_SECONDS
    assert requested["timeout"].pool is None
    assert isinstance(requested["transport"], loader._ValidatedHTTPTransport)


def test_load_spec_rejects_non_https_url() -> None:
    with pytest.raises(UnsupportedSchemeError, match="https://"):
        load_spec("http://example.com/openapi.yaml")


def test_load_spec_rejects_file_url() -> None:
    with pytest.raises(UnsupportedSchemeError, match="file://"):
        load_spec("file:///tmp/openapi.yaml")


def test_load_spec_blocks_private_remote_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_getaddrinfo(host: str, port: int, type: int) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)

    with pytest.raises(SSRFBlockedError, match="non-public"):
        load_spec("https://internal.example/openapi.yaml")


def test_load_spec_blocks_mixed_public_and_private_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_getaddrinfo(host: str, port: int, type: int) -> list[tuple[Any, ...]]:
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)

    with pytest.raises(SSRFBlockedError, match="10.0.0.5"):
        load_spec("https://mixed.example/openapi.yaml")


def test_load_spec_surfaces_remote_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_resolve(hostname: str, port: int) -> list[str]:
        return ["93.184.216.34"]

    class _TimeoutClient:
        def __init__(self, *, timeout: httpx.Timeout, follow_redirects: bool, transport: Any) -> None:
            return None

        def __enter__(self) -> _TimeoutClient:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def get(self, url: str) -> Any:
            raise httpx.ReadTimeout("boom")

    monkeypatch.setattr(loader, "_resolve_public_addresses", _fake_resolve)
    monkeypatch.setattr(httpx, "Client", _TimeoutClient)

    with pytest.raises(SpecLoadError, match="Timed out while fetching remote spec"):
        load_spec("https://example.com/openapi.yaml")


def test_load_spec_reports_invalid_documents(tmp_path: Path) -> None:
    spec_path = tmp_path / "invalid.yaml"
    spec_path.write_text("[not, an, object]", encoding="utf-8")

    with pytest.raises(SpecLoadError, match="must parse to a JSON object / YAML mapping"):
        load_spec(spec_path)


def test_validated_public_ip_backend_resolves_before_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: dict[str, Any] = {}

    def _fake_resolve(hostname: str, port: int) -> list[str]:
        requested["resolved_host"] = hostname
        requested["resolved_port"] = port
        return ["93.184.216.34"]

    class _FakeBackend:
        def connect_tcp(self, *, host: str, port: int, timeout: Any, local_address: Any, socket_options: Any) -> str:
            requested["connect_host"] = host
            requested["connect_port"] = port
            return "stream"

        def connect_unix_socket(self, path: str, timeout: Any = None, socket_options: Any = None) -> Any:
            raise AssertionError("unexpected unix socket connection")

        def sleep(self, seconds: float) -> None:
            return None

    monkeypatch.setattr(loader, "_resolve_public_addresses", _fake_resolve)

    backend = loader._ValidatedPublicIPBackend()
    monkeypatch.setattr(backend, "_backend", _FakeBackend())

    stream = backend.connect_tcp("example.com", 443, timeout=5.0)

    assert stream == "stream"
    assert requested == {
        "resolved_host": "example.com",
        "resolved_port": 443,
        "connect_host": "93.184.216.34",
        "connect_port": 443,
    }


def test_validated_http_transport_passes_backend_via_connection_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    recorded: dict[str, Any] = {}

    class _FakePool:
        def __init__(self, *, network_backend: Any) -> None:
            recorded["network_backend"] = network_backend

        def __enter__(self) -> _FakePool:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(loader.httpcore, "ConnectionPool", _FakePool)

    transport = loader._ValidatedHTTPTransport()

    assert isinstance(recorded["network_backend"], loader._ValidatedPublicIPBackend)
    transport.close()
