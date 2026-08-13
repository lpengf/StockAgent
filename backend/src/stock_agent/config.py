"""Configuration loaded from environment variables.

Uses pydantic-settings so every option is typed and can be overridden via env.
Values are read once at process start.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    log_json: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8989
    api_workers: int = 2
    api_root_path: str = ""
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_per_minute: int = 120

    database_url: str = "postgresql+psycopg://stock:stock@localhost:5432/stock_agent"
    database_pool_size: int = 10
    database_pool_max_overflow: int = 20

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "stock-agent-data"
    s3_access_key_id: SecretStr = SecretStr("minioadmin")
    s3_secret_access_key: SecretStr = SecretStr("minioadmin")
    s3_force_path_style: bool = True

    data_connector: Literal["akshare", "demo"] = "demo"
    akshare_rate_limit_per_minute: int = 30
    market: Literal["CN_A"] = "CN_A"

    scheduler_timezone: str = "Asia/Shanghai"
    scheduler_run_cron: str = "0 16 * * 1-5"

    jwt_secret: SecretStr = SecretStr("change-me-in-prod")
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 12
    admin_api_key: SecretStr = SecretStr("dev-admin-key")

    strategy_version: str = "mvp-1.0.0"
    coverage_hard_threshold: float = 95.0
    max_focus_candidates: int = 5
    max_total_candidates: int = 10
    max_per_industry: int = 2

    otel_exporter_endpoint: str | None = None
    prometheus_enabled: bool = True

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
