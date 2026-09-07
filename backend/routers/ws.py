"""WebSocket connection manager for live feed broadcasts."""
from __future__ import annotations

import asyncio
import logging
from typing import Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._active.add(ws)
        logger.info("WS client connected (total=%d)", len(self._active))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._active.discard(ws)
        logger.info("WS client disconnected (total=%d)", len(self._active))

    async def broadcast(self, data: dict) -> None:
        dead: Set[WebSocket] = set()
        async with self._lock:
            targets = set(self._active)

        for ws in targets:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._active -= dead


manager = ConnectionManager()
