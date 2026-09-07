"""DriftGuard FastAPI application entrypoint."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.db.migrations import apply_schema
from backend.routers import alerts, fixes, ingest, stats, ws as ws_module

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("DriftGuard starting — applying DB schema…")
    await asyncio.get_event_loop().run_in_executor(None, apply_schema)
    logger.info("DB schema ready.")
    yield
    logger.info("DriftGuard shutting down…")


cfg = get_settings()

app = FastAPI(
    title="DriftGuard",
    description="LLM Observability & Self-Correcting Evaluation Pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(ingest.router)
app.include_router(stats.router)
app.include_router(alerts.router)
app.include_router(fixes.router)


# ── WebSocket live feed ───────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await ws_module.manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_module.manager.disconnect(websocket)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "driftguard"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=cfg.backend_host,
        port=cfg.backend_port,
        reload=True,
    )
