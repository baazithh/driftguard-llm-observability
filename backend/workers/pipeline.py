"""Scoring pipeline — orchestrates embedder → scorer → aggregator."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional
from uuid import UUID

import psycopg2

from backend.config import get_settings
from backend.workers.aggregator import (
    check_anomaly,
    compute_and_store_rolling_stats,
    get_baseline_centroid,
)
from backend.workers.embedder import embed_text
from backend.workers.scorer import score_quality, score_semantic_drift, score_toxicity

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


def run_scoring_pipeline(call_id: UUID) -> dict:
    """
    Synchronous pipeline. Called via asyncio.create_task from ingest endpoint.
    1. Fetch the call record
    2. Embed response
    3. Score drift, quality, toxicity
    4. Persist scores
    5. Update rolling stats
    6. Anomaly check → create alert if needed → trigger agent
    """
    conn = _get_conn()
    try:
        # ── 1. Fetch call ─────────────────────────────────────────────────────
        with conn.cursor() as cur:
            cur.execute(
                "SELECT prompt, response, template_id FROM llm_calls WHERE id = %s",
                (str(call_id),),
            )
            row = cur.fetchone()

        if not row:
            logger.warning("call_id %s not found during scoring", call_id)
            return {}

        prompt, response, template_id = row

        # ── 2. Embed ──────────────────────────────────────────────────────────
        embedding = embed_text(response)
        with conn:
            with conn.cursor() as cur:
                # pgvector expects a list literal
                cur.execute(
                    """
                    INSERT INTO response_embeddings (call_id, embedding)
                    VALUES (%s, %s::vector)
                    """,
                    (str(call_id), str(embedding)),
                )

        # ── 3. Score ──────────────────────────────────────────────────────────
        centroid = get_baseline_centroid(template_id) if template_id else None
        semantic_drift = score_semantic_drift(embedding, centroid)
        quality_score, quality_rationale = score_quality(prompt, response)
        is_toxic, toxicity_flags = score_toxicity(response)

        cfg = get_settings()
        flagged = (
            is_toxic
            or (quality_score < cfg.quality_alert_threshold)
            or (semantic_drift > 0.35)
        )

        # ── 4. Persist scores ─────────────────────────────────────────────────
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO quality_scores
                        (call_id, semantic_drift, quality_score, quality_rationale,
                         is_toxic, toxicity_flags, flagged)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(call_id),
                        semantic_drift,
                        quality_score,
                        quality_rationale,
                        is_toxic,
                        toxicity_flags,
                        flagged,
                    ),
                )

        # ── 5. Rolling stats ──────────────────────────────────────────────────
        if template_id:
            compute_and_store_rolling_stats(template_id)

        # ── 6. Anomaly → alert → agent ────────────────────────────────────────
        alert_id = None
        if template_id and flagged:
            alert_id = check_anomaly(
                template_id=template_id,
                call_id=call_id,
                semantic_drift=semantic_drift,
                quality_score=quality_score,
                is_toxic=is_toxic,
            )

        if alert_id:
            # Fire agent in background thread (non-blocking)
            from backend.agent.graph import run_agent_for_alert
            asyncio.get_event_loop().run_in_executor(
                None, run_agent_for_alert, alert_id
            )

        result = {
            "call_id": str(call_id),
            "semantic_drift": semantic_drift,
            "quality_score": quality_score,
            "is_toxic": is_toxic,
            "flagged": flagged,
            "alert_id": str(alert_id) if alert_id else None,
        }
        logger.info("Scoring complete: %s", result)
        return result

    finally:
        conn.close()


async def run_scoring_pipeline_async(call_id: UUID) -> dict:
    """Async wrapper — runs the synchronous pipeline in a thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_scoring_pipeline, call_id)
