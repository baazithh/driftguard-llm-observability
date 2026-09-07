"""Quality scoring — semantic drift, LLM-as-judge, toxicity."""
from __future__ import annotations

import logging
import random
import re
from typing import Dict, List, Optional, Tuple

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from backend.config import get_settings
from backend.workers.embedder import cosine_distance

logger = logging.getLogger(__name__)

_vader = SentimentIntensityAnalyzer()

# ── Toxicity ──────────────────────────────────────────────────────────────────
TOXIC_KEYWORDS: List[str] = [
    "kill", "hate", "stupid", "idiot", "garbage", "worthless",
    "harm", "attack", "destroy", "violent", "offensive",
]


def score_toxicity(text: str) -> Tuple[bool, List[str]]:
    """
    Returns (is_toxic, triggered_flags).
    Flags: keyword match + VADER compound < -0.6.
    """
    flags: List[str] = []
    lower = text.lower()

    for kw in TOXIC_KEYWORDS:
        if re.search(r"\b" + kw + r"\b", lower):
            flags.append(f"keyword:{kw}")

    vader_score = _vader.polarity_scores(text)["compound"]
    if vader_score < -0.6:
        flags.append(f"vader_compound:{vader_score:.2f}")

    return bool(flags), flags


# ── Semantic drift ─────────────────────────────────────────────────────────────
def score_semantic_drift(
    embedding: List[float],
    centroid: Optional[List[float]],
) -> float:
    """
    Cosine distance between this response embedding and the rolling centroid.
    If no centroid exists (first call), drift is 0.
    """
    if centroid is None:
        return 0.0
    return cosine_distance(embedding, centroid)


# ── LLM-as-judge ──────────────────────────────────────────────────────────────
def score_quality(prompt: str, response: str) -> Tuple[float, str]:
    """
    Returns (quality_score 1-10, rationale).
    Uses GPT-4o-mini if OpenAI key present, otherwise heuristic stub.
    """
    cfg = get_settings()
    if cfg.use_openai:
        try:
            return _judge_openai(prompt, response, cfg)
        except Exception as exc:
            logger.warning("LLM judge failed (%s), using heuristic.", exc)
    return _judge_heuristic(response)


def _judge_openai(prompt: str, response: str, cfg) -> Tuple[float, str]:
    from openai import OpenAI
    client = OpenAI(api_key=cfg.openai_api_key)

    system = (
        "You are a strict LLM output quality evaluator. "
        "Given a prompt and response, output a JSON object with keys: "
        "score (float 1-10, where 10 is perfect) and rationale (one sentence)."
    )
    user_msg = f"Prompt:\n{prompt}\n\nResponse:\n{response}"

    resp = client.chat.completions.create(
        model=cfg.judge_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        response_format={"type": "json_object"},
        max_tokens=150,
        temperature=0.0,
    )
    import json
    data = json.loads(resp.choices[0].message.content)
    score = float(data.get("score", 5.0))
    rationale = data.get("rationale", "")
    return max(1.0, min(10.0, score)), rationale


def _judge_heuristic(response: str) -> Tuple[float, str]:
    """
    Offline quality heuristic:
    - Length relative to ideal (50-300 words)
    - Sentiment compound (neutral/positive preferred)
    - Coherence proxy: avg word length
    """
    words = response.split()
    n = len(words)

    # Length score: penalise very short or very long responses
    if n < 10:
        length_score = 2.0
    elif n < 30:
        length_score = 5.0
    elif n <= 200:
        length_score = 9.0
    elif n <= 400:
        length_score = 7.0
    else:
        length_score = 4.0  # excessively verbose → drift penalty

    # Sentiment: extreme negativity → lower score
    vader_compound = _vader.polarity_scores(response)["compound"]
    sentiment_score = 5.0 + vader_compound * 3.0

    # Coherence: avg word length (too short → filler, too long → jargon)
    avg_word_len = sum(len(w) for w in words) / max(n, 1)
    if 4 <= avg_word_len <= 7:
        coherence_score = 9.0
    else:
        coherence_score = 6.0

    score = (length_score + sentiment_score + coherence_score) / 3.0
    score = max(1.0, min(10.0, score))
    rationale = (
        f"Heuristic: length={n}w, vader={vader_compound:.2f}, "
        f"avg_word_len={avg_word_len:.1f}"
    )
    return round(score, 2), rationale
