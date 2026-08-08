"""Application settings loaded from environment / .env."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from config.providers import ResolvedLLM, list_providers, resolve_llm


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM — set LLM_PROVIDER to auto-fill base URL + default models
    llm_provider: str = Field("openai", alias="LLM_PROVIDER")
    llm_api_key: str = Field("", alias="LLM_API_KEY")
    # Optional overrides (leave empty to use provider defaults)
    llm_base_url: str = Field("", alias="LLM_BASE_URL")
    llm_model: str = Field("", alias="LLM_MODEL")
    llm_vision_model: str = Field("", alias="LLM_VISION_MODEL")
    llm_max_tokens: int = Field(4096, alias="LLM_MAX_TOKENS")
    llm_temperature: float = Field(0.2, alias="LLM_TEMPERATURE")

    # Telegram
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_allowed_users: str = Field("", alias="TELEGRAM_ALLOWED_USERS")

    # Agent
    agent_name: str = Field("MarianaOS", alias="AGENT_NAME")
    agent_max_tool_rounds: int = Field(25, alias="AGENT_MAX_TOOL_ROUNDS")
    agent_screenshot_dir: str = Field("data/screenshots", alias="AGENT_SCREENSHOT_DIR")
    agent_workspace: str = Field(str(Path.home() / "Desktop"), alias="AGENT_WORKSPACE")
    cursor_path: str = Field("", alias="CURSOR_PATH")
    require_confirmation: bool = Field(False, alias="REQUIRE_CONFIRMATION")

    # Tool discovery — only send core tool schemas to the LLM (saves tokens).
    # Agent must call search_tools(query) to unlock more tools for that run.
    tool_discovery: bool = Field(True, alias="TOOL_DISCOVERY")
    # Comma-separated core tool names (empty = built-in default set)
    tool_core: str = Field("", alias="TOOL_CORE")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    @field_validator("telegram_allowed_users", mode="before")
    @classmethod
    def _coerce_users(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v)

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _coerce_provider(cls, v: object) -> str:
        if v is None or str(v).strip() == "":
            return "openai"
        return str(v).strip()

    @cached_property
    def llm(self) -> ResolvedLLM:
        return resolve_llm(
            provider=self.llm_provider,
            api_key=self.llm_api_key,
            base_url=self.llm_base_url,
            model=self.llm_model,
            vision_model=self.llm_vision_model,
        )

    @property
    def allowed_user_ids(self) -> List[int]:
        if not self.telegram_allowed_users.strip():
            return []
        return [
            int(x.strip())
            for x in self.telegram_allowed_users.split(",")
            if x.strip().isdigit()
        ]

    @property
    def screenshot_dir(self) -> Path:
        path = Path(self.agent_screenshot_dir)
        if not path.is_absolute():
            path = ROOT_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def workspace(self) -> Path:
        return Path(self.agent_workspace).expanduser().resolve()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings()  # type: ignore[call-arg]
    return _settings


__all__ = ["Settings", "get_settings", "reload_settings", "list_providers"]
