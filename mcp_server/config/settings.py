"""Application settings loaded from environment variables."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RetryConfig(BaseModel):
    """Retry behavior for outbound HTTP calls."""

    attempts: int = Field(default=3, ge=1, le=10)
    min_seconds: float = Field(default=0.5, ge=0.1, le=10.0)
    max_seconds: float = Field(default=4.0, ge=0.1, le=20.0)


class ScoringWeights(BaseModel):
    """Weights used for composite score calculation."""

    value: float = Field(default=0.2, ge=0, le=1)
    growth: float = Field(default=0.25, ge=0, le=1)
    quality: float = Field(default=0.2, ge=0, le=1)
    momentum: float = Field(default=0.2, ge=0, le=1)
    risk: float = Field(default=0.15, ge=0, le=1)


class Settings(BaseSettings):
    """Runtime application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "stock-research-mcp"
    app_version: str = "1.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    transport_mode: Literal["auto", "stdio", "http"] = "auto"
    http_transport: Literal["sse", "streamable"] = "sse"
    host: str = "0.0.0.0"
    port: int = 8000
    mcp_path: str = "/mcp"
    health_path: str = "/health"

    request_timeout_seconds: float = Field(default=12.0, ge=1, le=120)
    retry: RetryConfig = RetryConfig()
    scoring_weights: ScoringWeights = ScoringWeights()

    claude_api_key: str = Field(alias="CLAUDE_API_KEY")
    alpha_vantage_api_key: str = Field(alias="ALPHA_VANTAGE_API_KEY")
    finnhub_api_key: str = Field(alias="FINNHUB_API_KEY")
    claude_model: str = "claude-3-5-sonnet-latest"


def get_settings() -> Settings:
    """Return application settings."""

    return Settings()


