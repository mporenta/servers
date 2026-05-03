from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="MEMORY_GRAPH_", extra="ignore")

    database_url: str = Field(
        default="postgresql://memory:memory@localhost:5432/memory",
        description="asyncpg-compatible Postgres DSN.",
    )
    pool_min_size: int = Field(default=1, ge=0)
    pool_max_size: int = Field(default=10, ge=1)
    transport: str = Field(
        default="stdio",
        description="FastMCP transport: stdio or http.",
    )
    http_host: str = Field(default="0.0.0.0")
    http_port: int = Field(default=8000)
