"""Application settings loaded from environment / .env (python-dotenv)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import List

from dotenv import load_dotenv

from config.providers import ResolvedLLM, list_providers, resolve_llm


ROOT_DIR = Path(__file__).resolve().parent.parent
# Prefer .env over leftover process env (e.g. IDE / prior shell tests)
load_dotenv(ROOT_DIR / ".env", override=True)


def _env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _env_int(key: str, default: int) -> int:
    raw = _env(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    raw = _env(key)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env(key).lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_vision_model: str
    llm_max_tokens: int
    llm_temperature: float
    telegram_bot_token: str
    telegram_allowed_users: str
    agent_name: str
    agent_max_tool_rounds: int
    agent_screenshot_dir: str
    agent_workspace: str
    require_confirmation: bool
    tool_discovery: bool
    tool_core: str
    log_level: str

    @classmethod
    def load(cls) -> "Settings":
        token = _env("TELEGRAM_BOT_TOKEN")
        if not token or token.startswith("your_"):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is required. Copy .env.example → .env and fill it in."
            )
        return cls(
            llm_provider=_env("LLM_PROVIDER", "openrouter") or "openrouter",
            llm_api_key=_env("LLM_API_KEY"),
            llm_base_url=_env("LLM_BASE_URL"),
            llm_model=_env("LLM_MODEL"),
            llm_vision_model=_env("LLM_VISION_MODEL"),
            llm_max_tokens=_env_int("LLM_MAX_TOKENS", 4096),
            llm_temperature=_env_float("LLM_TEMPERATURE", 0.2),
            telegram_bot_token=token,
            telegram_allowed_users=_env("TELEGRAM_ALLOWED_USERS"),
            agent_name=_env("AGENT_NAME", "MarianaOS") or "MarianaOS",
            agent_max_tool_rounds=_env_int("AGENT_MAX_TOOL_ROUNDS", 25),
            agent_screenshot_dir=_env("AGENT_SCREENSHOT_DIR", "data/screenshots")
            or "data/screenshots",
            agent_workspace=_env("AGENT_WORKSPACE")
            or str(Path.home() / "Desktop"),
            require_confirmation=_env_bool("REQUIRE_CONFIRMATION", False),
            tool_discovery=_env_bool("TOOL_DISCOVERY", True),
            tool_core=_env("TOOL_CORE"),
            log_level=_env("LOG_LEVEL", "INFO") or "INFO",
        )

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
        if not self.telegram_allowed_users:
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
        _settings = Settings.load()
    return _settings


def reload_settings() -> Settings:
    global _settings
    load_dotenv(ROOT_DIR / ".env", override=True)
    _settings = Settings.load()
    return _settings


__all__ = ["Settings", "get_settings", "reload_settings", "list_providers"]
