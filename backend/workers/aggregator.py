"""Rolling-window aggregator + Z-score anomaly detection."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


def compute_and_store_rolling_stats(template_id: UUID) -> Dict:
    """
    Fetch the last N scored calls for *template_id*, compute rolling stats,
    upsert into rolling_stats, and check anomalies.

    Returns a dict with the computed stats.
    """
    cfg = get_settings()
    window = cfg.rolling_window_size

    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Fetch last N quality scores for this template
            cur.execute(
                """
                SELECT qs.semantic_drift, qs.quality_score, lc.latency_ms, lc.cost_usd
                FROM quality_scores qs
                JOIN llm_calls lc ON lc.id = qs.call_id
                WHERE lc.template_id = %s
                ORDER BY qs.created_at DESC
                LIMIT %s
                """,
                (str(template_id), window),
            )
            rows = cur.fetchall()

        if not rows:
            return {}

        drifts = [r["semantic_drift"] for r in rows if r["semantic_drift"] is not None]
        qualities = [r["quality_score"] for r in rows if r["quality_score"] is not None]
        latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
        costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]

        def _stats(arr: List[float]):
            a = np.array(arr, dtype=float)
            return float(np.mean(a)) if len(a) else None, float(np.std(a)) if len(a) > 1 else None

        avg_drift, std_drift = _stats(drifts)
        avg_quality, std_quality = _stats(qualities)
        avg_latency, _ = _stats(latencies)
        avg_cost, _ = _stats(costs)

        stats = {
            "template_id": str(template_id),
            "window_size": window,
            "avg_semantic_drift": avg_drift,
            "std_semantic_drift": std_drift,
            "avg_quality_score": avg_quality,
            "std_quality_score": std_quality,
            "avg_latency_ms": avg_latency,
            "avg_cost_usd": avg_cost,
            "call_count": len(rows),
        }

        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO rolling_stats
                        (template_id, window_size, avg_semantic_drift, std_semantic_drift,
                         avg_quality_score, std_quality_score, avg_latency_ms, avg_cost_usd,
                         call_count)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        str(template_id), window,
                        avg_drift, std_drift,
                        avg_quality, std_quality,
                        avg_latency, avg_cost,
                        len(rows),
                    ),
                )

        return stats
    finally:
        conn.close()


def check_anomaly(
    template_id: UUID,
    call_id: UUID,
    semantic_drift: Optional[float],
    quality_score: Optional[float],
    is_toxic: bool,
) -> Optional[UUID]:
    """
    Compare current metrics against rolling baseline.
    Create an alert if an anomaly is detected.
    Returns the alert_id if one was created, else None.
    """
    cfg = get_settings()
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT avg_semantic_drift, std_semantic_drift,
                       avg_quality_score, std_quality_score
                FROM rolling_stats
                WHERE template_id = %s
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                (str(template_id),),
            )
            baseline = cur.fetchone()

        alert_type = None
        metric_value = None
        threshold_value = None
        z_score = None
        severity = "medium"

        if is_toxic:
            alert_type = "toxicity"
            severity = "critical"
            metric_value = 1.0
            threshold_value = 0.0

        elif (
            baseline
            and semantic_drift is not None
            and baseline["avg_semantic_drift"] is not None
            and baseline["std_semantic_drift"] is not None
            and baseline["std_semantic_drift"] > 0
        ):
            z = (semantic_drift - baseline["avg_semantic_drift"]) / baseline["std_semantic_drift"]
            if z > cfg.drift_alert_zscore:
                alert_type = "semantic_drift"
                z_score = z
                metric_value = semantic_drift
                threshold_value = cfg.drift_alert_zscore
                severity = "high" if z > 3.5 else "medium"

        elif (
            quality_score is not None
            and quality_score < cfg.quality_alert_threshold
        ):
            alert_type = "quality_drop"
            metric_value = quality_score
            threshold_value = cfg.quality_alert_threshold
            severity = "high" if quality_score < 3.0 else "medium"

        if alert_type is None:
            return None

        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alerts
                        (template_id, call_id, alert_type, severity,
                         metric_value, threshold_value, z_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        str(template_id), str(call_id),
                        alert_type, severity,
                        metric_value, threshold_value, z_score,
                    ),
                )
                alert_id = cur.fetchone()[0]

        logger.info(
            "Alert created: type=%s severity=%s template=%s",
            alert_type, severity, template_id,
        )
        return alert_id

    finally:
        conn.close()


def get_baseline_centroid(template_id: UUID) -> Optional[List[float]]:
    """
    Compute a centroid (mean vector) from the last 50 embeddings for template_id.
    Returns None if fewer than 2 embeddings exist.
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT re.embedding
                FROM response_embeddings re
                JOIN llm_calls lc ON lc.id = re.call_id
                WHERE lc.template_id = %s
                ORDER BY re.created_at DESC
                LIMIT 50
                """,
                (str(template_id),),
            )
            rows = cur.fetchall()

        if len(rows) < 2:
            return None

        vecs = np.array([list(r[0]) for r in rows], dtype=np.float32)
        centroid = np.mean(vecs, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid /= norm
        return centroid.tolist()
    finally:
        conn.close()
