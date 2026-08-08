"""Future Web UI / WebSocket channel stub."""

from __future__ import annotations

from channels.base import BaseChannel, OutboundMessage
from utils.logging import get_logger

log = get_logger("marianaos.web")


class WebChannel(BaseChannel):
    """Placeholder for a FastAPI + WebSocket control panel."""

    name = "web"

    async def start(self) -> None:
        log.warning("Web channel not implemented yet — stub only")

    async def stop(self) -> None:
        return

    async def send(self, user_id: str, message: OutboundMessage) -> None:
        raise NotImplementedError("Web channel coming soon")
