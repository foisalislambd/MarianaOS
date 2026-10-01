"""Channel abstractions for Telegram / future WhatsApp / Web."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional


@dataclass
class InboundMessage:
    channel: str
    user_id: str
    session_id: str
    text: str
    display_name: str = ""
    raw: Any = None


@dataclass
class OutboundMessage:
    text: str = ""
    media_paths: List[str] = field(default_factory=list)
    # "rich" = Telegram sendRichMessage(markdown=…) — preferred for AI replies
    # "html" = legacy sendMessage HTML fallback
    parse_mode: Optional[str] = "rich"


MessageHandler = Callable[[InboundMessage], Awaitable[OutboundMessage]]


class BaseChannel(ABC):
    name: str = "base"

    def __init__(self) -> None:
        self._handler: Optional[MessageHandler] = None

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def send(self, user_id: str, message: OutboundMessage) -> None:
        ...
