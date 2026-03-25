"""Application configuration loaded from environment variables."""

import logging
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# Resolve .env relative to project root (parent of backend/)
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """GENESIS configuration — reads from .env or environment."""

    # LLM provider keys
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Search
    SERPER_API_KEY: str = ""

    # LLM defaults
    DEFAULT_LLM_PROVIDER: str = "anthropic"
    DEFAULT_MODEL: str = "claude-sonnet-4-20250514"

    # Observability
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "genesis"

    # Paths
    SKILLS_DIR: Path = Path("generated_skills")
    DB_PATH: Path = Path("data/genesis.db")
    SKILL_TREE_PATH: Path = Path("data/skill_tree.json")

    # Server
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()


async def setup_logging() -> None:
    """Configure stdlib logging from settings."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
