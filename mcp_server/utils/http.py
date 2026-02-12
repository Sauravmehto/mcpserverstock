"""Async HTTP client with retry and timeout support."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from mcp_server.config.settings import RetryConfig


class HttpClient:
    """Thin wrapper around httpx with retries."""

    def __init__(self, timeout_seconds: float, retry_config: RetryConfig) -> None:
        self._timeout_seconds = timeout_seconds
        self._retry_config = retry_config
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any] | list[Any]:
        """Return JSON payload or raise runtime error."""

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._retry_config.attempts),
                wait=wait_exponential(
                    min=self._retry_config.min_seconds,
                    max=self._retry_config.max_seconds,
                ),
                reraise=True,
            ):
                with attempt:
                    response = await self._client.get(url, headers=headers)
                    response.raise_for_status()
                    return response.json()
        except RetryError as error:
            raise RuntimeError(f"HTTP retries exhausted for URL: {url}") from error
        except httpx.HTTPError as error:
            raise RuntimeError(f"HTTP request failed for URL: {url}") from error

    async def close(self) -> None:
        """Close underlying transport."""

        await self._client.aclose()


