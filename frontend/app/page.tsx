import { api, DashboardData } from "@/lib/api";
import { StatCard } from "@/components/StatCard";
import Link from "next/link";
import { ArrowRight, Activity, AlertTriangle, GitPullRequest, Radio } from "lucide-react";

export const revalidate = 15;

export default async function OverviewPage() {
  let data: DashboardData | null = null;
  try {
    data = await api.dashboard();
  } catch {
    // backend not ready
  }

  const s = data?.summary;

  const cards = [
    {
      label: "Total Calls (7d)",
      value: s ? Math.round(s.total_calls).toLocaleString() : "—",
      sub: "LLM requests ingested",
      accent: true,
    },
    {
      label: "Avg Quality",
      value: s ? s.avg_quality.toFixed(2) : "—",
      sub: "/ 10 (LLM-as-judge)",
      warning: s ? s.avg_quality < 6 : false,
    },
    {
      label: "Avg Drift",
      value: s ? s.avg_drift.toFixed(4) : "—",
      sub: "cosine distance",
      danger: s ? s.avg_drift > 0.3 : false,
    },
    {
      label: "Flagged",
      value: s ? Math.round(s.total_flagged).toLocaleString() : "—",
      sub: "calls above threshold",
      danger: s ? s.total_flagged > 0 : false,
    },
    {
      label: "Open Alerts",
      value: s ? Math.round(s.open_alerts).toLocaleString() : "—",
      sub: "require attention",
      danger: s ? s.open_alerts > 0 : false,
    },
    {
      label: "Total Cost",
      value: s ? `$${s.total_cost.toFixed(4)}` : "—",
      sub: "USD (7d)",
    },
  ];

  const quickLinks = [
    {
      href: "/live-feed",
      icon: Radio,
      title: "Live Feed",
      desc: "WebSocket stream of real-time LLM calls with scores",
      color: "#6366f1",
    },
    {
      href: "/dashboard",
      icon: Activity,
      title: "Drift Dashboard",
      desc: "Time-series charts: drift, quality, latency, cost per template",
      color: "#10b981",
    },
    {
      href: "/alerts",
      icon: AlertTriangle,
      title: "Alerts",
      desc: "AI-diagnosed anomalies with severity bands",
      color: "#f59e0b",
    },
    {
      href: "/fixes",
      icon: GitPullRequest,
      title: "Fix Review",
      desc: "Agent-proposed prompt fixes ready for human approval",
      color: "#a78bfa",
    },
  ];

  return (
    <>
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>
            <span className="gradient-text">DriftGuard</span> Command Center
          </h1>
          {data && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 99, background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
              <div className="pulse-dot green" />
              <span style={{ fontSize: "0.72rem", color: "#34d399" }}>System Online</span>
            </div>
          )}
        </div>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", margin: "0.5rem 0 0" }}>
          Real-time LLM observability · Semantic drift detection · Autonomous prompt repair
        </p>
      </div>

      <div className="page-body" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
        {/* KPI Cards */}
        <section>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.75rem" }}>
            7-Day Overview
          </div>
          <div className="stat-grid">
            {cards.map((c) => (
              <StatCard key={c.label} {...c} />
            ))}
          </div>
        </section>

        {/* Quick Links */}
        <section>
          <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.75rem" }}>
            Modules
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "1rem" }}>
            {quickLinks.map(({ href, icon: Icon, title, desc, color }) => (
              <Link
                key={href}
                href={href}
                style={{ textDecoration: "none" }}
              >
                <div
                  className="card"
                  style={{
                    cursor: "pointer",
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.75rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div
                      style={{
                        width: 36, height: 36,
                        borderRadius: 8,
                        background: `${color}18`,
                        border: `1px solid ${color}35`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}
                    >
                      <Icon size={16} color={color} />
                    </div>
                    <ArrowRight size={14} color="var(--text-muted)" />
                  </div>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: "0.925rem", marginBottom: 4 }}>{title}</div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>{desc}</div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* Architecture note */}
        <section className="card" style={{ background: "rgba(99,102,241,0.04)", borderColor: "rgba(99,102,241,0.2)" }}>
          <div style={{ fontSize: "0.72rem", color: "#818cf8", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.75rem" }}>
            Pipeline Architecture
          </div>
          <div style={{ fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)", fontSize: "0.78rem", color: "var(--text-secondary)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
{`SDK Client → POST /api/ingest → PostgreSQL (llm_calls)
                                    ↓
                         Async Scoring Workers
                         ├─ Embedder (all-MiniLM-L6-v2)
                         ├─ Semantic Drift (cosine vs centroid)
                         ├─ LLM-as-Judge (gpt-4o-mini / heuristic)
                         └─ Toxicity (keyword + VADER)
                                    ↓ anomaly detected
                         Agent Loop (diagnose → propose fix)
                                    ↓
                         Human Review (Apply / Reject)`}
          </div>
        </section>
      </div>
    </>
  );
}
