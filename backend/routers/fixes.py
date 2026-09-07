"""Fixes router — GET /api/fixes, POST apply/reject."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query

from backend.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/fixes", tags=["fixes"])


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


def _row_to_dict(r: Dict) -> Dict:
    d = dict(r)
    d["id"] = str(d["id"])
    d["alert_id"] = str(d["alert_id"])
    d["template_id"] = str(d["template_id"]) if d["template_id"] else None
    d["created_at"] = d["created_at"].isoformat() if d["created_at"] else None
    d["reviewed_at"] = d["reviewed_at"].isoformat() if d["reviewed_at"] else None
    return d


@router.get("")
def list_fixes(
    status: Optional[str] = Query(None, description="pending|applied|rejected"),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if status:
                cur.execute(
                    """
                    SELECT pf.*, pt.name AS template_name
                    FROM prompt_fixes pf
                    LEFT JOIN prompt_templates pt ON pt.id = pf.template_id
                    WHERE pf.status = %s
                    ORDER BY pf.created_at DESC
                    LIMIT %s
                    """,
                    (status, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT pf.*, pt.name AS template_name
                    FROM prompt_fixes pf
                    LEFT JOIN prompt_templates pt ON pt.id = pf.template_id
                    ORDER BY pf.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@router.get("/{fix_id}")
def get_fix(fix_id: UUID) -> Dict[str, Any]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT pf.*, pt.name AS template_name
                FROM prompt_fixes pf
                LEFT JOIN prompt_templates pt ON pt.id = pf.template_id
                WHERE pf.id = %s
                """,
                (str(fix_id),),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Fix not found")
        return _row_to_dict(row)
    finally:
        conn.close()


def _update_fix_status(fix_id: UUID, status: str) -> Dict[str, str]:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE prompt_fixes SET status = %s, reviewed_at = NOW()
                    WHERE id = %s AND status = 'pending'
                    RETURNING id
                    """,
                    (status, str(fix_id)),
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Fix not found or already reviewed",
            )
        return {"message": f"Fix {status}", "fix_id": str(fix_id)}
    finally:
        conn.close()


@router.post("/{fix_id}/apply")
def apply_fix(fix_id: UUID) -> Dict[str, str]:
    """Mark fix as applied. In a full system this would update the prompt_template."""
    result = _update_fix_status(fix_id, "applied")
    # Optionally update prompt_templates.template_text here
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                # Get the proposed prompt and template_id
                cur.execute(
                    "SELECT proposed_prompt, template_id FROM prompt_fixes WHERE id = %s",
                    (str(fix_id),),
                )
                row = cur.fetchone()
                if row and row[1]:
                    cur.execute(
                        """
                        UPDATE prompt_templates
                        SET template_text = %s, active_version = active_version + 1
                        WHERE id = %s
                        """,
                        (row[0], str(row[1])),
                    )
    finally:
        conn.close()
    return result


@router.post("/{fix_id}/reject")
def reject_fix(fix_id: UUID) -> Dict[str, str]:
    return _update_fix_status(fix_id, "rejected")
