"""DriftGuard — central configuration (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql://driftguard:driftguard_secret@localhost:5432/driftguard"
    postgres_user: str = "driftguard"
    postgres_password: str = "driftguard_secret"
    postgres_db: str = "driftguard"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── OpenAI (optional) ─────────────────────────────────────────────────────
    openai_api_key: Optional[str] = None
    judge_model: str = "gpt-4o-mini"
    agent_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # ── Backend ───────────────────────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # ── Scoring thresholds ────────────────────────────────────────────────────
    drift_alert_zscore: float = 2.0
    quality_alert_threshold: float = 5.0
    rolling_window_size: int = 50

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def use_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
