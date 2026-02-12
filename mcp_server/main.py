"""Application entrypoint for stock research MCP server."""

from __future__ import annotations

import asyncio
import logging
import os

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse, Response

from mcp_server.analysis.claude_engine import ClaudeAnalysisEngine
from mcp_server.config.settings import get_settings
from mcp_server.providers.alpha_vantage import AlphaVantageProvider
from mcp_server.providers.finnhub import FinnhubProvider
from mcp_server.providers.router import ProviderRouter
from mcp_server.tools.stock_tools import register_stock_tools
from mcp_server.utils.http import HttpClient
from mcp_server.utils.logging import configure_logging

LOGGER = logging.getLogger(__name__)


def resolve_transport_mode(configured_mode: str) -> str:
    """Resolve effective transport mode for local vs hosted environments."""

    # Render web services must bind an HTTP port. Force HTTP if stdio is configured.
    if os.getenv("RENDER") and configured_mode == "stdio":
        return "http"
    if configured_mode in {"stdio", "http"}:
        return configured_mode
    # Auto mode: prefer HTTP on hosted environments, stdio locally.
    if os.getenv("RENDER") or os.getenv("PORT"):
        return "http"
    return "stdio"


def resolve_http_transport(configured_transport: str) -> str:
    """Resolve effective HTTP transport mode for MCP over HTTP."""

    if configured_transport in {"sse", "streamable"}:
        return configured_transport
    return "sse"


async def run() -> None:
    """Initialize services and run MCP server."""

    settings = get_settings()
    configure_logging(settings.log_level)

    http_client = HttpClient(
        timeout_seconds=settings.request_timeout_seconds,
        retry_config=settings.retry,
    )
    alpha_provider = AlphaVantageProvider(settings.alpha_vantage_api_key, http_client)
    finnhub_provider = FinnhubProvider(settings.finnhub_api_key, http_client)
    router = ProviderRouter(primary=alpha_provider, secondary=finnhub_provider)
    claude_engine = ClaudeAnalysisEngine(settings.claude_api_key, settings.claude_model)

    mcp = FastMCP(
        name=settings.app_name,
        log_level=settings.log_level,
        host=settings.host,
        port=settings.port,
        streamable_http_path=settings.mcp_path,
    )
    register_stock_tools(mcp, router, claude_engine, settings)

    @mcp.custom_route(settings.health_path, methods=["GET"])
    async def health_check(_: object) -> Response:
        return JSONResponse({"status": "ok", "service": settings.app_name, "mode": resolved_mode})

    resolved_mode = resolve_transport_mode(settings.transport_mode)
    resolved_http_transport = resolve_http_transport(settings.http_transport)
    LOGGER.info(
        "Starting MCP server",
        extra={"transport_mode": resolved_mode, "http_transport": resolved_http_transport},
    )
    try:
        if resolved_mode == "stdio":
            await mcp.run_stdio_async()
        elif resolved_http_transport == "streamable":
            await mcp.run_streamable_http_async()
        else:
            await mcp.run_sse_async()
    finally:
        await http_client.close()


def main() -> None:
    """Synchronous entrypoint."""

    asyncio.run(run())


if __name__ == "__main__":
    main()


