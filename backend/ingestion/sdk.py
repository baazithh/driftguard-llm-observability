"""DriftGuardClient — SDK wrapper for capturing LLM calls."""
from __future__ import annotations

import time
import logging
from typing import Any, Dict, Optional
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


class DriftGuardClient:
    """
    Thin SDK client that wraps an OpenAI-compatible API call,
    logs the request/response to DriftGuard, and returns the response.

    Usage::

        client = DriftGuardClient(backend_url="http://localhost:8000")
        response_text = client.call(
            template_id="...",
            prompt="Tell me about ...",
            model="gpt-4o-mini",
            openai_response=openai_response_object,
        )
    """

    def __init__(
        self,
        backend_url: str = "http://localhost:8000",
        timeout: float = 10.0,
    ) -> None:
        self._backend = backend_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout)

    def log_call(
        self,
        *,
        prompt: str,
        response: str,
        model: str = "gpt-4o-mini",
        template_id: Optional[str] = None,
        latency_ms: float = 0.0,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Fire-and-forget POST to /api/ingest.
        Returns the call_id on success, None on failure.
        """
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "response": response,
            "model": model,
            "latency_ms": latency_ms,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
            "metadata": metadata or {},
        }
        if template_id:
            payload["template_id"] = template_id

        try:
            resp = self._http.post(f"{self._backend}/api/ingest", json=payload)
            resp.raise_for_status()
            return resp.json().get("call_id")
        except Exception as exc:
            logger.warning("DriftGuard ingest failed: %s", exc)
            return None

    def __enter__(self) -> "DriftGuardClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self._http.close()
