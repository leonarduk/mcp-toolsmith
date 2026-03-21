"""Tests for local and remote spec loading."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import httpx
import pytest

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

    def _fake_getaddrinfo(host: str, port: int, type: int) -> list[tuple[Any, ...]]:
        requested["resolved_host"] = host
        requested["resolved_port"] = port
        requested["resolved_type"] = type
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    class _FakeResponse:
        text = 'openapi: 3.0.3\ninfo:\n  title: Remote\n  version: 1.0.0\n'

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        def __init__(self, *, timeout: httpx.Timeout, follow_redirects: bool) -> None:
            requested["timeout"] = timeout
            requested["follow_redirects"] = follow_redirects

        def __enter__(self) -> _FakeClient:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def get(self, url: str) -> _FakeResponse:
            requested["url"] = url
            return _FakeResponse()

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(httpx, "Client", _FakeClient)

    loaded = load_spec("https://example.com/openapi.yaml")

    assert loaded["info"]["title"] == "Remote"
    assert requested["resolved_host"] == "example.com"
    assert requested["url"] == "https://example.com/openapi.yaml"
    assert requested["follow_redirects"] is True
    assert requested["timeout"].connect == CONNECT_TIMEOUT_SECONDS
    assert requested["timeout"].read == READ_TIMEOUT_SECONDS


def test_load_spec_rejects_non_https_url() -> None:
    with pytest.raises(UnsupportedSchemeError, match="https://"):
        load_spec("http://example.com/openapi.yaml")


def test_load_spec_blocks_private_remote_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_getaddrinfo(host: str, port: int, type: int) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.10", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)

    with pytest.raises(SSRFBlockedError, match="blocked private or loopback"):
        load_spec("https://internal.example/openapi.yaml")


def test_load_spec_surfaces_remote_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_getaddrinfo(host: str, port: int, type: int) -> list[tuple[Any, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    class _TimeoutClient:
        def __init__(self, *, timeout: httpx.Timeout, follow_redirects: bool) -> None:
            return None

        def __enter__(self) -> _TimeoutClient:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def get(self, url: str) -> Any:
            raise httpx.ReadTimeout("boom")

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(httpx, "Client", _TimeoutClient)

    with pytest.raises(SpecLoadError, match="Timed out while fetching remote spec"):
        load_spec("https://example.com/openapi.yaml")
