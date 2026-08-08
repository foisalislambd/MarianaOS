"""Per-user conversation memory."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List


@dataclass
class ConversationMemory:
    max_messages: int = 40
    _store: Dict[str, Deque[Dict[str, Any]]] = field(default_factory=dict)

    def _q(self, session_id: str) -> Deque[Dict[str, Any]]:
        if session_id not in self._store:
            self._store[session_id] = deque(maxlen=self.max_messages)
        return self._store[session_id]

    def add(self, session_id: str, message: Dict[str, Any]) -> None:
        self._q(session_id).append(message)

    def extend(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        q = self._q(session_id)
        for m in messages:
            q.append(m)

    def get(self, session_id: str) -> List[Dict[str, Any]]:
        return list(self._q(session_id))

    def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
