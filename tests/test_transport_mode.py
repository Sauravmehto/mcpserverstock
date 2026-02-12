"""Tests for transport mode resolution behavior."""

from __future__ import annotations

from mcp_server.main import resolve_http_transport, resolve_transport_mode


def test_resolve_transport_mode_auto_prefers_stdio_without_host_env(monkeypatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    assert resolve_transport_mode("auto") == "stdio"


def test_resolve_transport_mode_auto_prefers_http_with_port(monkeypatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("PORT", "8000")
    assert resolve_transport_mode("auto") == "http"


def test_resolve_transport_mode_forces_http_on_render(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    assert resolve_transport_mode("stdio") == "http"


def test_resolve_http_transport_defaults_to_sse_for_unknown_value() -> None:
    assert resolve_http_transport("unknown") == "sse"


def test_resolve_http_transport_accepts_streamable() -> None:
    assert resolve_http_transport("streamable") == "streamable"

