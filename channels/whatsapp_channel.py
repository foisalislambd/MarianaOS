"""Future WhatsApp channel stub (Meta Cloud API / Baileys bridge)."""

from __future__ import annotations

from channels.base import BaseChannel, OutboundMessage
from utils.logging import get_logger

log = get_logger("mros.whatsapp")


class WhatsAppChannel(BaseChannel):
    """Placeholder — wire Meta Cloud API or a local bridge later."""

    name = "whatsapp"

    async def start(self) -> None:
        log.warning("WhatsApp channel not implemented yet — stub only")

    async def stop(self) -> None:
        return

    async def send(self, user_id: str, message: OutboundMessage) -> None:
        raise NotImplementedError("WhatsApp channel coming soon")
