"""Pydantic models for LLM call ingestion."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Payload sent by the SDK / seed script to /api/ingest."""

    template_id: Optional[UUID] = None
    prompt: str
    response: str
    model: str = "gpt-4o-mini"
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # allow back-filling timestamps for seed data
    created_at: Optional[datetime] = None


class IngestResponse(BaseModel):
    call_id: UUID
    message: str = "Ingested successfully"


class LLMCallRecord(BaseModel):
    id: UUID
    template_id: Optional[UUID]
    prompt: str
    response: str
    model: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_usd: float
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class QualityScoreRecord(BaseModel):
    id: UUID
    call_id: UUID
    semantic_drift: Optional[float]
    quality_score: Optional[float]
    quality_rationale: Optional[str]
    is_toxic: bool
    toxicity_flags: List[str]
    flagged: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AlertRecord(BaseModel):
    id: UUID
    template_id: Optional[UUID]
    call_id: Optional[UUID]
    alert_type: str
    severity: str
    metric_value: Optional[float]
    threshold_value: Optional[float]
    z_score: Optional[float]
    diagnosis: Optional[str]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


class PromptFixRecord(BaseModel):
    id: UUID
    alert_id: UUID
    template_id: Optional[UUID]
    original_prompt: str
    proposed_prompt: str
    diff_json: List[Any]
    agent_reasoning: Optional[str]
    status: str
    reviewed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class LiveCallPayload(BaseModel):
    """WebSocket broadcast payload."""

    call_id: str
    template_id: Optional[str]
    model: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost_usd: float
    semantic_drift: Optional[float]
    quality_score: Optional[float]
    is_toxic: bool
    flagged: bool
    created_at: str
