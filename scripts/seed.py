"""
DriftGuard Synthetic Data Seeder
Generates 200 realistic LLM calls across 3 templates over 7 days,
injects a drift event at day 4, and fires the full scoring pipeline.

Usage:
    python scripts/seed.py [--backend http://localhost:8000] [--reset]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import uuid

import httpx

# ─── Seed config ──────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8000"
TOTAL_CALLS = 200
DAYS = 7
DRIFT_START_DAY = 4   # day index (0-based) when drift kicks in
TEMPLATES = [
    {
        "name": "customer-support-v1",
        "description": "Handles customer support queries for a SaaS product",
        "template_text": (
            "You are a helpful customer support agent for Acme SaaS. "
            "Answer the user's question clearly and concisely in 2-3 sentences. "
            "Be professional and empathetic. "
            "Question: {question}"
        ),
    },
    {
        "name": "code-explainer-v1",
        "description": "Explains code snippets to developers",
        "template_text": (
            "You are an expert software engineer. Explain the following code snippet "
            "in plain English. Keep your explanation under 100 words and focus on "
            "what the code does, not how. "
            "Code: {code}"
        ),
    },
    {
        "name": "summarizer-v1",
        "description": "Summarizes long-form text into bullet points",
        "template_text": (
            "Summarize the following text into 3-5 concise bullet points. "
            "Each bullet should be one sentence. "
            "Text: {text}"
        ),
    },
]

# ─── Sample content pools ──────────────────────────────────────────────────────
NORMAL_RESPONSES = {
    "customer-support-v1": [
        "Your account renewal is handled automatically each billing cycle. You can view and update your payment method in Settings → Billing. If you need to cancel, please reach out at least 3 days before renewal.",
        "To reset your password, click 'Forgot Password' on the login page and follow the link sent to your email. The link expires after 24 hours.",
        "Our API rate limit is 1,000 requests per minute by default. You can request a higher limit by upgrading to the Enterprise plan.",
        "Data exports are available in CSV and JSON formats from the Admin dashboard under Reports → Export. Processing may take up to 10 minutes for large datasets.",
        "We offer a 14-day free trial with full feature access. No credit card is required to start your trial.",
    ],
    "code-explainer-v1": [
        "This function iterates over a list and applies a transformation to each element, returning a new list with the results. It is a functional programming pattern known as 'map'.",
        "The code opens a database connection, executes a parameterized query to prevent SQL injection, and closes the connection in a finally block to ensure cleanup.",
        "This class implements a singleton pattern — it ensures only one instance is created by checking if an instance already exists before creating a new one.",
        "The decorator wraps a function to measure and log its execution time. It uses functools.wraps to preserve the original function's metadata.",
        "This async generator yields items from a paginated API, automatically fetching the next page until no more results are available.",
    ],
    "summarizer-v1": [
        "• The study found a 23% improvement in efficiency after the intervention.\n• Participants reported higher satisfaction scores across all demographics.\n• The results were statistically significant with p < 0.05.\n• Long-term effects require further monitoring over a 12-month period.",
        "• Global temperatures rose by 1.1°C above pre-industrial levels in 2023.\n• Extreme weather events increased in frequency and intensity.\n• Renewable energy adoption grew but remains insufficient to meet targets.\n• International cooperation on emissions reduction showed limited progress.",
        "• The product launch exceeded revenue targets by 40% in Q1.\n• Customer acquisition cost decreased due to improved marketing efficiency.\n• Churn rate dropped to 2.3%, the lowest in company history.\n• The engineering team delivered all milestones on schedule.",
    ],
}

DRIFT_RESPONSES = {
    "customer-support-v1": [
        "I am so sorry to hear that you are experiencing this issue but let me tell you that this is a very complex situation and there are many factors involved and you should know that our team is working very hard on this and we will get back to you as soon as possible maybe sometime next week or the week after that depending on the workload and various other considerations that I cannot go into detail about right now but rest assured we are committed to resolving this for you eventually.",
        "That is a great question and I appreciate you reaching out to us today. Unfortunately, I hate to inform you that this feature is terrible and garbage and our product team is completely incompetent and has failed to deliver a working solution for years now.",
        "Your problem is stupid and there is nothing we can do. Please read the documentation. We cannot help you.",
        "Um well I think maybe you could try logging out and logging back in? Or maybe clear your cache? I'm not sure actually. Have you tried turning it off and on again? That usually works for most things in general.",
        "ERROR: Unable to process your request. The system has encountered an unexpected error. Please try again later. ERROR 500. NULL POINTER EXCEPTION. SEGMENTATION FAULT.",
    ],
    "code-explainer-v1": [
        "Well this code does stuff. It has variables and functions and things happen. The loop goes through items. There are conditions. Output is produced. Code runs. Computation occurs. Results follow from inputs as per the logic encoded therein.",
        "I hate this code. It is terrible code written by someone who clearly does not understand programming. The variable names are awful and meaningless garbage that makes the code completely unreadable and impossible to maintain.",
        "The code is a loop that iterates. It iterates through iterations. Each iteration is an iteration. The iterating loop loops. Variables vary. Functions function. Objects objectify. Classes classify. This is a programming paradigm.",
        "UNDEFINED BEHAVIOR. MEMORY LEAK. RACE CONDITION. BUFFER OVERFLOW. DO NOT USE THIS CODE.",
        "I cannot explain this code as it makes no sense whatsoever and whoever wrote it should be fired immediately from their position as a software engineer at whatever company employs them.",
    ],
    "summarizer-v1": [
        "• The text discusses things.\n• Various points are made.\n• Conclusions are drawn.\n• Something important happened.\n• The end result was a result.",
        "I refuse to summarize this text as it is offensive to my sensibilities and contains information that I find personally disagreeable and would prefer not to engage with whatsoever under any circumstances.",
        "Summary: Yes. Also no. Maybe. It depends. The answer is complicated. More information is needed. Please provide additional context. Thank you for your patience.",
        "• ERROR\n• ERROR\n• ERROR\n• ERROR\n• ERROR",
        "The text says many things. So many things. Countless things. More things than can be counted. The things said are important things. Important things are said. Things. Things. Things things things things things.",
    ],
}

PROMPTS = {
    "customer-support-v1": [
        "How do I reset my password?",
        "Can I export my data?",
        "What is your API rate limit?",
        "How does billing work?",
        "Do you offer a free trial?",
        "How do I add team members?",
        "Can I change my plan mid-cycle?",
        "Is my data encrypted?",
    ],
    "code-explainer-v1": [
        "def fib(n): return n if n<2 else fib(n-1)+fib(n-2)",
        "SELECT * FROM users WHERE id = ? LIMIT 1",
        "const fn = arr => arr.reduce((a,b) => a+b, 0)",
        "class Singleton: _instance=None\n  def __new__(cls): ...",
        "@wraps(fn)\ndef wrapper(*args): t=time.time(); r=fn(*args); log(time.time()-t); return r",
    ],
    "summarizer-v1": [
        "A new study published in Nature Climate Change shows that global temperatures...",
        "The quarterly earnings report from Acme Corp reveals strong growth...",
        "Researchers at MIT have developed a novel approach to protein folding...",
        "The latest data from the WHO indicates that vaccination rates globally...",
    ],
}

MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def random_latency(is_drift: bool = False) -> float:
    base = random.gauss(450, 80)
    if is_drift:
        base += random.gauss(300, 100)  # drift → higher latency
    return max(100.0, base)


def random_cost(tokens_in: int, tokens_out: int) -> float:
    # gpt-4o-mini pricing approximation
    return round((tokens_in * 0.00015 + tokens_out * 0.0006) / 1000, 6)


def create_templates(client: httpx.Client, base_url: str) -> Dict[str, str]:
    """POST templates directly to DB via a helper endpoint (or seed via psycopg2)."""
    import psycopg2
    import os

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://driftguard:driftguard_secret@localhost:5432/driftguard",
    )
    conn = psycopg2.connect(db_url)
    ids: Dict[str, str] = {}
    try:
        with conn:
            with conn.cursor() as cur:
                for t in TEMPLATES:
                    cur.execute(
                        """
                        INSERT INTO prompt_templates (name, description, template_text)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (name) DO UPDATE
                            SET description = EXCLUDED.description,
                                template_text = EXCLUDED.template_text
                        RETURNING id
                        """,
                        (t["name"], t["description"], t["template_text"]),
                    )
                    tid = str(cur.fetchone()[0])
                    ids[t["name"]] = tid
                    print(f"  ✓ Template '{t['name']}' → {tid}")
    finally:
        conn.close()
    return ids


def ingest_call(
    client: httpx.Client,
    base_url: str,
    template_id: str,
    prompt: str,
    response: str,
    is_drift: bool,
    created_at: datetime,
) -> Optional[str]:
    tokens_in = random.randint(50, 200)
    tokens_out = len(response.split()) + random.randint(0, 30)
    latency = random_latency(is_drift)

    payload = {
        "template_id": template_id,
        "prompt": prompt,
        "response": response,
        "model": random.choice(MODELS),
        "latency_ms": round(latency, 1),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": random_cost(tokens_in, tokens_out),
        "metadata": {"is_drift_injected": is_drift},
        "created_at": created_at.isoformat(),
    }
    try:
        r = client.post(f"{base_url}/api/ingest", json=payload, timeout=30)
        r.raise_for_status()
        return r.json().get("call_id")
    except Exception as e:
        print(f"  ✗ Ingest failed: {e}")
        return None


def reset_data() -> None:
    import psycopg2
    import os

    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://driftguard:driftguard_secret@localhost:5432/driftguard",
    )
    conn = psycopg2.connect(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE prompt_fixes, alerts, rolling_stats, quality_scores, response_embeddings, llm_calls, prompt_templates CASCADE")
        print("✓ Database reset complete.")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="DriftGuard seed script")
    parser.add_argument("--backend", default=BACKEND_URL, help="Backend base URL")
    parser.add_argument("--reset", action="store_true", help="Clear all data before seeding")
    args = parser.parse_args()

    base_url = args.backend.rstrip("/")

    # Wait for backend to be ready
    print(f"⏳ Waiting for backend at {base_url} …")
    for _ in range(30):
        try:
            r = httpx.get(f"{base_url}/health", timeout=5)
            if r.status_code == 200:
                print("✓ Backend is ready.")
                break
        except Exception:
            pass
        time.sleep(2)
    else:
        print("✗ Backend not reachable. Make sure uvicorn is running.")
        sys.exit(1)

    if args.reset:
        print("🗑  Resetting database …")
        reset_data()

    print("\n📦 Creating prompt templates …")
    client = httpx.Client()
    template_ids = create_templates(client, base_url)

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAYS)
    drift_start = start + timedelta(days=DRIFT_START_DAY)

    print(f"\n🚀 Ingesting {TOTAL_CALLS} synthetic calls over {DAYS} days …")
    print(f"   Drift event injects at: {drift_start.strftime('%Y-%m-%d')}")

    template_names = list(template_ids.keys())
    success = 0
    failed = 0

    for i in range(TOTAL_CALLS):
        # Spread calls over the 7-day window with some randomness
        offset_seconds = (DAYS * 24 * 3600 * i) // TOTAL_CALLS + random.randint(-1800, 1800)
        call_ts = start + timedelta(seconds=offset_seconds)
        is_drift = call_ts >= drift_start

        template_name = template_names[i % len(template_names)]
        template_id = template_ids[template_name]

        # Pick prompt and response
        prompts = PROMPTS[template_name]
        prompt = random.choice(prompts)

        if is_drift and random.random() < 0.75:
            # 75% drift probability after day 4
            response = random.choice(DRIFT_RESPONSES[template_name])
        else:
            response = random.choice(NORMAL_RESPONSES[template_name])

        call_id = ingest_call(
            client, base_url, template_id, prompt, response, is_drift, call_ts
        )

        if call_id:
            success += 1
        else:
            failed += 1

        # Brief pause to avoid overwhelming the scoring workers
        if i % 20 == 19:
            print(f"   Progress: {i+1}/{TOTAL_CALLS} ({success} succeeded, {failed} failed)")
            time.sleep(0.5)

    print(f"\n✅ Seeding complete: {success} succeeded, {failed} failed")
    print("\n⏳ Waiting 5 seconds for scoring workers to process …")
    time.sleep(5)

    # Summary
    print("\n📊 Summary:")
    try:
        r = client.get(f"{base_url}/api/stats/dashboard", timeout=15)
        data = r.json()
        s = data.get("summary", {})
        print(f"   Total calls:   {int(s.get('total_calls', 0))}")
        print(f"   Open alerts:   {int(s.get('open_alerts', 0))}")
        print(f"   Total flagged: {int(s.get('total_flagged', 0))}")
        print(f"   Avg quality:   {s.get('avg_quality', 0):.2f}/10")
        print(f"   Avg drift:     {s.get('avg_drift', 0):.4f}")
        print(f"   Total cost:    ${s.get('total_cost', 0):.4f}")
    except Exception as e:
        print(f"   Could not fetch summary: {e}")

    try:
        r = client.get(f"{base_url}/api/fixes", timeout=10)
        fixes = r.json()
        print(f"   Fix proposals: {len(fixes)}")
    except Exception:
        pass

    print("\n🎯 DriftGuard is seeded and ready! Open http://localhost:3000")
    client.close()


if __name__ == "__main__":
    main()
