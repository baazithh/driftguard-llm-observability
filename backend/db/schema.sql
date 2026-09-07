-- DriftGuard Database Schema
-- PostgreSQL 16 + pgvector

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Prompt Templates ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_templates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    template_text   TEXT NOT NULL,
    active_version  INT DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── LLM Calls ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_calls (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id     UUID REFERENCES prompt_templates(id) ON DELETE SET NULL,
    prompt          TEXT NOT NULL,
    response        TEXT NOT NULL,
    model           TEXT NOT NULL DEFAULT 'gpt-4o-mini',
    latency_ms      FLOAT NOT NULL DEFAULT 0,
    tokens_in       INT NOT NULL DEFAULT 0,
    tokens_out      INT NOT NULL DEFAULT 0,
    cost_usd        FLOAT NOT NULL DEFAULT 0,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_llm_calls_template_id ON llm_calls(template_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at  ON llm_calls(created_at DESC);

-- ─── Response Embeddings ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS response_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id         UUID NOT NULL REFERENCES llm_calls(id) ON DELETE CASCADE,
    embedding       vector(384),   -- sentence-transformers/all-MiniLM-L6-v2
    model_name      TEXT NOT NULL DEFAULT 'all-MiniLM-L6-v2',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_call_id ON response_embeddings(call_id);

-- ─── Quality Scores ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_scores (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id             UUID NOT NULL REFERENCES llm_calls(id) ON DELETE CASCADE,
    semantic_drift      FLOAT,          -- cosine distance from baseline centroid (0-1)
    quality_score       FLOAT,          -- LLM-as-judge score (1-10)
    quality_rationale   TEXT,           -- judge explanation
    is_toxic            BOOLEAN NOT NULL DEFAULT FALSE,
    toxicity_flags      TEXT[],         -- which keywords/rules triggered
    flagged             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scores_call_id  ON quality_scores(call_id);
CREATE INDEX IF NOT EXISTS idx_scores_flagged  ON quality_scores(flagged) WHERE flagged = TRUE;

-- ─── Rolling Stats (per template, computed after each scoring run) ─────────────
CREATE TABLE IF NOT EXISTS rolling_stats (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id         UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    window_size         INT NOT NULL DEFAULT 50,
    avg_semantic_drift  FLOAT,
    std_semantic_drift  FLOAT,
    avg_quality_score   FLOAT,
    std_quality_score   FLOAT,
    avg_latency_ms      FLOAT,
    avg_cost_usd        FLOAT,
    call_count          INT NOT NULL DEFAULT 0,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rolling_stats_template ON rolling_stats(template_id, computed_at DESC);

-- ─── Alerts ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_id     UUID REFERENCES prompt_templates(id) ON DELETE SET NULL,
    call_id         UUID REFERENCES llm_calls(id) ON DELETE SET NULL,
    alert_type      TEXT NOT NULL,          -- 'semantic_drift' | 'quality_drop' | 'toxicity'
    severity        TEXT NOT NULL DEFAULT 'medium',  -- 'low' | 'medium' | 'high' | 'critical'
    metric_value    FLOAT,
    threshold_value FLOAT,
    z_score         FLOAT,
    diagnosis       TEXT,                   -- AI-generated root-cause summary
    status          TEXT NOT NULL DEFAULT 'open',    -- 'open' | 'resolved' | 'suppressed'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_template ON alerts(template_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status   ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_created  ON alerts(created_at DESC);

-- ─── Prompt Fixes (agent proposals) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_fixes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id            UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    template_id         UUID REFERENCES prompt_templates(id) ON DELETE SET NULL,
    original_prompt     TEXT NOT NULL,
    proposed_prompt     TEXT NOT NULL,
    diff_json           JSONB DEFAULT '[]',     -- array of diff hunks
    agent_reasoning     TEXT,                   -- agent chain-of-thought
    status              TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'applied' | 'rejected'
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fixes_alert    ON prompt_fixes(alert_id);
CREATE INDEX IF NOT EXISTS idx_fixes_status   ON prompt_fixes(status);
CREATE INDEX IF NOT EXISTS idx_fixes_template ON prompt_fixes(template_id);

-- ─── Trigger: update prompt_templates.updated_at ─────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prompt_templates_updated_at
    BEFORE UPDATE ON prompt_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
