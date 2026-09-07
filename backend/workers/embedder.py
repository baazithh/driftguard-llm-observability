"""Embedding worker — sentence-transformers (offline) or OpenAI."""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from backend.config import get_settings

logger = logging.getLogger(__name__)

_model = None  # lazy-loaded sentence-transformer model


def _get_local_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded sentence-transformers/all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> List[float]:
    """Return a 384-dim embedding for `text`."""
    cfg = get_settings()
    if cfg.use_openai:
        try:
            return _embed_openai(text, cfg)
        except Exception as exc:
            logger.warning("OpenAI embedding failed (%s), falling back to local model.", exc)
    return _embed_local(text)


def _embed_local(text: str) -> List[float]:
    model = _get_local_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _embed_openai(text: str, cfg) -> List[float]:
    from openai import OpenAI
    client = OpenAI(api_key=cfg.openai_api_key)
    resp = client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def cosine_distance(a: List[float], b: List[float]) -> float:
    """Return cosine distance (0 = identical, 1 = orthogonal, 2 = opposite)."""
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    sim = float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))
    return 1.0 - sim
