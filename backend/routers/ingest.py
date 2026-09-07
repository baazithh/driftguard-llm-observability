"""Ingest router — POST /api/ingest."""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

import psycopg2
from fastapi import APIRouter, HTTPException

from backend.ingestion.models import IngestRequest, IngestResponse
from backend.config import get_settings
from backend.workers.pipeline import run_scoring_pipeline_async

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["ingest"])


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_call(payload: IngestRequest) -> IngestResponse:
    """Receive an LLM call, persist it, and launch async scoring."""
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                if payload.created_at:
                    cur.execute(
                        """
                        INSERT INTO llm_calls
                            (template_id, prompt, response, model,
                             latency_ms, tokens_in, tokens_out, cost_usd, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            str(payload.template_id) if payload.template_id else None,
                            payload.prompt,
                            payload.response,
                            payload.model,
                            payload.latency_ms,
                            payload.tokens_in,
                            payload.tokens_out,
                            payload.cost_usd,
                            psycopg2.extras.Json(payload.metadata),
                            payload.created_at,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO llm_calls
                            (template_id, prompt, response, model,
                             latency_ms, tokens_in, tokens_out, cost_usd, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            str(payload.template_id) if payload.template_id else None,
                            payload.prompt,
                            payload.response,
                            payload.model,
                            payload.latency_ms,
                            payload.tokens_in,
                            payload.tokens_out,
                            payload.cost_usd,
                            psycopg2.extras.Json(payload.metadata),
                        ),
                    )
                call_id = cur.fetchone()[0]
    except Exception as exc:
        logger.exception("Failed to persist LLM call")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        conn.close()

    # Launch scoring in background — non-blocking
    asyncio.create_task(run_scoring_pipeline_async(call_id))

    return IngestResponse(call_id=call_id)
