"""Agent graph — diagnose drift and propose a prompt fix."""
from __future__ import annotations

import difflib
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

from backend.config import get_settings
from backend.agent.prompts import (
    DIAGNOSE_SYSTEM,
    DIAGNOSE_USER_TEMPLATE,
    FIX_SYSTEM,
    FIX_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)


def _get_conn():
    return psycopg2.connect(get_settings().database_url)


# ── Node helpers ───────────────────────────────────────────────────────────────

def _fetch_flagged_samples(template_id: UUID, limit: int = 5) -> List[Dict]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT lc.prompt, lc.response, qs.semantic_drift, qs.quality_score
                FROM quality_scores qs
                JOIN llm_calls lc ON lc.id = qs.call_id
                WHERE lc.template_id = %s AND qs.flagged = TRUE
                ORDER BY qs.created_at DESC
                LIMIT %s
                """,
                (str(template_id), limit),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _fetch_template(template_id: UUID) -> Optional[Dict]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, template_text FROM prompt_templates WHERE id = %s",
                (str(template_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def _fetch_alert(alert_id: UUID) -> Optional[Dict]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM alerts WHERE id = %s",
                (str(alert_id),),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def _call_llm(system: str, user: str, cfg) -> str:
    """Single LLM call, returns the text content."""
    from openai import OpenAI
    client = OpenAI(api_key=cfg.openai_api_key)
    resp = client.chat.completions.create(
        model=cfg.agent_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=512,
    )
    return resp.choices[0].message.content.strip()


def _build_diff(original: str, proposed: str) -> List[Dict]:
    """Generate a unified diff as a JSON-serialisable list of hunks."""
    diff = list(
        difflib.unified_diff(
            original.splitlines(),
            proposed.splitlines(),
            lineterm="",
            n=2,
        )
    )
    return [{"line": ln} for ln in diff]


def _store_fix(
    alert_id: UUID,
    template_id: Optional[UUID],
    original: str,
    proposed: str,
    diff: List[Dict],
    reasoning: str,
) -> UUID:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO prompt_fixes
                        (alert_id, template_id, original_prompt, proposed_prompt,
                         diff_json, agent_reasoning)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        str(alert_id),
                        str(template_id) if template_id else None,
                        original,
                        proposed,
                        json.dumps(diff),
                        reasoning,
                    ),
                )
                return cur.fetchone()[0]
    finally:
        conn.close()


def _update_alert_diagnosis(alert_id: UUID, diagnosis: str) -> None:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE alerts SET diagnosis = %s WHERE id = %s",
                    (diagnosis, str(alert_id)),
                )
    finally:
        conn.close()


# ── Offline stubs ──────────────────────────────────────────────────────────────

def _stub_diagnose(alert_type: str, template_name: str) -> str:
    stubs = {
        "semantic_drift": (
            f"The '{template_name}' template is producing responses that deviate "
            "significantly from established baseline semantics. "
            "Recent outputs appear more verbose and off-topic, suggesting the model "
            "is generating filler content rather than targeted responses."
        ),
        "quality_drop": (
            f"Quality scores for '{template_name}' have dropped below acceptable thresholds. "
            "Responses appear shorter, less coherent, or with increased negative sentiment. "
            "This may indicate prompt ambiguity or model degradation."
        ),
        "toxicity": (
            f"A response from '{template_name}' was flagged as potentially toxic "
            "based on keyword and sentiment analysis. Manual review is recommended."
        ),
    }
    return stubs.get(alert_type, "Unexplained quality regression detected.")


def _stub_fix(original: str, diagnosis: str) -> str:
    suffix = (
        "\n\nIMPORTANT: Be concise, accurate, and maintain a professional tone. "
        "Avoid verbose filler content and stay strictly on topic."
    )
    return original.rstrip() + suffix


# ── Main pipeline ──────────────────────────────────────────────────────────────

def run_agent_for_alert(alert_id: UUID) -> Optional[UUID]:
    """
    Full agentic loop for one alert:
      1. Fetch context
      2. Diagnose
      3. Produce fix proposal
      4. Store fix
    Returns fix_id or None.
    """
    cfg = get_settings()

    alert = _fetch_alert(alert_id)
    if not alert:
        logger.warning("Alert %s not found", alert_id)
        return None

    template_id = alert.get("template_id")
    if not template_id:
        logger.warning("Alert %s has no template_id, skipping agent.", alert_id)
        return None

    template = _fetch_template(template_id)
    if not template:
        logger.warning("Template %s not found", template_id)
        return None

    samples = _fetch_flagged_samples(template_id)

    # ── Step 2: Diagnose ──────────────────────────────────────────────────────
    if cfg.use_openai and samples:
        sample_text = "\n\n---\n\n".join(
            f"Prompt: {s['prompt'][:300]}\nResponse: {s['response'][:300]}"
            for s in samples
        )
        user_msg = DIAGNOSE_USER_TEMPLATE.format(
            template_name=template["name"],
            alert_type=alert["alert_type"],
            metric_value=float(alert.get("metric_value") or 0),
            threshold_value=float(alert.get("threshold_value") or 0),
            samples=sample_text,
        )
        diagnosis = _call_llm(DIAGNOSE_SYSTEM, user_msg, cfg)
    else:
        diagnosis = _stub_diagnose(alert["alert_type"], template["name"])

    _update_alert_diagnosis(alert_id, diagnosis)
    logger.info("Diagnosis complete for alert %s", alert_id)

    # ── Step 3: Propose fix ───────────────────────────────────────────────────
    original_prompt = template["template_text"]
    if cfg.use_openai:
        user_msg = FIX_USER_TEMPLATE.format(
            original_prompt=original_prompt,
            diagnosis=diagnosis,
        )
        proposed_prompt = _call_llm(FIX_SYSTEM, user_msg, cfg)
    else:
        proposed_prompt = _stub_fix(original_prompt, diagnosis)

    diff = _build_diff(original_prompt, proposed_prompt)

    # ── Step 4: Store ─────────────────────────────────────────────────────────
    fix_id = _store_fix(
        alert_id=alert_id,
        template_id=template_id,
        original=original_prompt,
        proposed=proposed_prompt,
        diff=diff,
        reasoning=diagnosis,
    )
    logger.info("Fix proposal stored: fix_id=%s", fix_id)
    return fix_id
