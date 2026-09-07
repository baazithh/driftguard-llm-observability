const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export const API_BASE = `${BACKEND_URL}/api`;
export const WS_URL = BACKEND_URL.replace(/^http/, "ws") + "/ws/live";

async function fetcher<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  dashboard: () => fetcher<DashboardData>("/stats/dashboard"),
  liveFeed: (limit = 50) => fetcher<LiveCall[]>(`/stats/live-feed?limit=${limit}`),
  alerts: (status?: string) =>
    fetcher<Alert[]>(`/alerts${status ? `?status=${status}` : ""}`),
  alert: (id: string) => fetcher<Alert>(`/alerts/${id}`),
  fixes: (status?: string) =>
    fetcher<PromptFix[]>(`/fixes${status ? `?status=${status}` : ""}`),
  fix: (id: string) => fetcher<PromptFix>(`/fixes/${id}`),
  applyFix: (id: string) =>
    fetch(`${API_BASE}/fixes/${id}/apply`, { method: "POST" }),
  rejectFix: (id: string) =>
    fetch(`${API_BASE}/fixes/${id}/reject`, { method: "POST" }),
  resolveAlert: (id: string) =>
    fetch(`${API_BASE}/alerts/${id}/resolve`, { method: "POST" }),
};

// ── Types ──────────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  total_calls: number;
  avg_quality: number;
  avg_drift: number;
  total_flagged: number;
  total_cost: number;
  open_alerts: number;
}

export interface SeriesPoint {
  bucket: string;
  avg_drift: number | null;
  avg_quality: number | null;
  avg_latency: number | null;
  total_cost: number;
  call_count: number;
  flagged_count: number;
}

export interface TemplateTimeSeries {
  template_id: string;
  template_name: string;
  series: SeriesPoint[];
}

export interface DashboardData {
  summary: DashboardSummary;
  templates: TemplateTimeSeries[];
}

export interface LiveCall {
  call_id: string;
  template_id: string | null;
  template_name: string | null;
  model: string;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
  created_at: string;
  semantic_drift: number | null;
  quality_score: number | null;
  quality_rationale: string | null;
  is_toxic: boolean;
  flagged: boolean;
}

export interface Alert {
  id: string;
  template_id: string | null;
  template_name: string | null;
  call_id: string | null;
  alert_type: string;
  severity: string;
  metric_value: number | null;
  threshold_value: number | null;
  z_score: number | null;
  diagnosis: string | null;
  status: string;
  created_at: string;
  resolved_at: string | null;
}

export interface PromptFix {
  id: string;
  alert_id: string;
  template_id: string | null;
  template_name: string | null;
  original_prompt: string;
  proposed_prompt: string;
  diff_json: { line: string }[];
  agent_reasoning: string | null;
  status: string;
  reviewed_at: string | null;
  created_at: string;
}
