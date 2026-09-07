"""Stats router — GET /api/stats/dashboard and /api/stats/live-feed."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, Query

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stats", tags=["stats"])


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


@router.get("/dashboard")
def get_dashboard() -> Dict[str, Any]:
    """
    Returns time-series data grouped by template:
      - series of (timestamp, semantic_drift, quality_score, latency_ms, cost_usd)
    Also returns summary cards.
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Per-template aggregated time series (hourly buckets)
            cur.execute(
                """
                SELECT
                    pt.id            AS template_id,
                    pt.name          AS template_name,
                    date_trunc('hour', lc.created_at) AS bucket,
                    AVG(qs.semantic_drift)             AS avg_drift,
                    AVG(qs.quality_score)              AS avg_quality,
                    AVG(lc.latency_ms)                 AS avg_latency,
                    SUM(lc.cost_usd)                   AS total_cost,
                    COUNT(*)                           AS call_count,
                    SUM(CASE WHEN qs.flagged THEN 1 ELSE 0 END) AS flagged_count
                FROM llm_calls lc
                JOIN prompt_templates pt ON pt.id = lc.template_id
                LEFT JOIN quality_scores qs ON qs.call_id = lc.id
                WHERE lc.created_at >= NOW() - INTERVAL '7 days'
                GROUP BY pt.id, pt.name, bucket
                ORDER BY pt.name, bucket
                """
            )
            rows = cur.fetchall()

            # Summary cards
            cur.execute(
                """
                SELECT
                    COUNT(DISTINCT lc.id)                                AS total_calls,
                    AVG(qs.quality_score)                                AS avg_quality,
                    AVG(qs.semantic_drift)                               AS avg_drift,
                    SUM(CASE WHEN qs.flagged THEN 1 ELSE 0 END)         AS total_flagged,
                    SUM(lc.cost_usd)                                     AS total_cost,
                    COUNT(DISTINCT a.id) FILTER (WHERE a.status = 'open') AS open_alerts
                FROM llm_calls lc
                LEFT JOIN quality_scores qs ON qs.call_id = lc.id
                LEFT JOIN alerts a ON a.call_id = lc.id
                WHERE lc.created_at >= NOW() - INTERVAL '7 days'
                """
            )
            summary = dict(cur.fetchone() or {})

        # Group rows by template
        templates: Dict[str, Dict] = {}
        for r in rows:
            tid = str(r["template_id"])
            if tid not in templates:
                templates[tid] = {
                    "template_id": tid,
                    "template_name": r["template_name"],
                    "series": [],
                }
            templates[tid]["series"].append(
                {
                    "bucket": r["bucket"].isoformat() if r["bucket"] else None,
                    "avg_drift": float(r["avg_drift"]) if r["avg_drift"] is not None else None,
                    "avg_quality": float(r["avg_quality"]) if r["avg_quality"] is not None else None,
                    "avg_latency": float(r["avg_latency"]) if r["avg_latency"] is not None else None,
                    "total_cost": float(r["total_cost"]) if r["total_cost"] is not None else 0,
                    "call_count": r["call_count"],
                    "flagged_count": r["flagged_count"],
                }
            )

        return {
            "summary": {k: (float(v) if v is not None else 0) for k, v in summary.items()},
            "templates": list(templates.values()),
        }
    finally:
        conn.close()


@router.get("/live-feed")
def get_live_feed(limit: int = Query(50, ge=1, le=200)) -> List[Dict[str, Any]]:
    """Last N LLM calls with their quality scores."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    lc.id            AS call_id,
                    lc.template_id,
                    pt.name          AS template_name,
                    lc.model,
                    lc.latency_ms,
                    lc.tokens_in,
                    lc.tokens_out,
                    lc.cost_usd,
                    lc.created_at,
                    qs.semantic_drift,
                    qs.quality_score,
                    qs.quality_rationale,
                    qs.is_toxic,
                    qs.flagged
                FROM llm_calls lc
                LEFT JOIN prompt_templates pt ON pt.id = lc.template_id
                LEFT JOIN quality_scores qs ON qs.call_id = lc.id
                ORDER BY lc.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["call_id"] = str(d["call_id"])
            d["template_id"] = str(d["template_id"]) if d["template_id"] else None
            d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
            result.append(d)
        return result
    finally:
        conn.close()
