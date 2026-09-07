"""Alerts router — GET /api/alerts, GET /api/alerts/{id}."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


def _row_to_dict(r: Dict) -> Dict:
    d = dict(r)
    d["id"] = str(d["id"])
    d["template_id"] = str(d["template_id"]) if d["template_id"] else None
    d["call_id"] = str(d["call_id"]) if d["call_id"] else None
    d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
    d["resolved_at"] = d["resolved_at"].isoformat() if d["resolved_at"] else None
    return d


@router.get("")
def list_alerts(
    status: Optional[str] = Query(None, description="open|resolved|suppressed"),
    limit: int = Query(100, ge=1, le=500),
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if status:
                cur.execute(
                    """
                    SELECT a.*, pt.name AS template_name
                    FROM alerts a
                    LEFT JOIN prompt_templates pt ON pt.id = a.template_id
                    WHERE a.status = %s
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT a.*, pt.name AS template_name
                    FROM alerts a
                    LEFT JOIN prompt_templates pt ON pt.id = a.template_id
                    ORDER BY a.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@router.get("/{alert_id}")
def get_alert(alert_id: UUID) -> Dict[str, Any]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT a.*, pt.name AS template_name
                FROM alerts a
                LEFT JOIN prompt_templates pt ON pt.id = a.template_id
                WHERE a.id = %s
                """,
                (str(alert_id),),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        return _row_to_dict(row)
    finally:
        conn.close()


@router.post("/{alert_id}/resolve")
def resolve_alert(alert_id: UUID) -> Dict[str, str]:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE alerts SET status = 'resolved', resolved_at = NOW()
                    WHERE id = %s
                    """,
                    (str(alert_id),),
                )
        return {"message": "Alert resolved"}
    finally:
        conn.close()
