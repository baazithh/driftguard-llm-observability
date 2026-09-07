"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  BarChart2,
  GitPullRequest,
  Radio,
  Shield,
  Zap,
} from "lucide-react";
import clsx from "clsx";

const NAV = [
  { href: "/", icon: BarChart2, label: "Overview" },
  { href: "/live-feed", icon: Radio, label: "Live Feed" },
  { href: "/dashboard", icon: Activity, label: "Drift Dashboard" },
  { href: "/alerts", icon: AlertTriangle, label: "Alerts" },
  { href: "/fixes", icon: GitPullRequest, label: "Fix Review" },
];

export function Sidebar() {
  const path = usePathname();

  return (
    <aside
      style={{
        width: "var(--sidebar-w)",
        position: "fixed",
        top: 0,
        left: 0,
        bottom: 0,
        background: "var(--bg-surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        zIndex: 50,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: "1.5rem 1.25rem",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "8px",
            background: "linear-gradient(135deg, #6366f1, #a78bfa)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Shield size={16} color="white" />
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: "0.95rem", letterSpacing: "-0.01em" }}>
            DriftGuard
          </div>
          <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: 1 }}>
            LLM Observability
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "1rem 0.75rem", display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", padding: "0 0.5rem", marginBottom: 6 }}>
          Navigation
        </div>
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = path === href || (href !== "/" && path.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "0.55rem 0.75rem",
                borderRadius: 8,
                fontSize: "0.875rem",
                fontWeight: active ? 600 : 400,
                color: active ? "var(--text-primary)" : "var(--text-secondary)",
                background: active ? "var(--bg-card)" : "transparent",
                border: active ? "1px solid var(--border)" : "1px solid transparent",
                textDecoration: "none",
                transition: "all 0.15s",
                boxShadow: active ? "0 0 12px rgba(99,102,241,0.08)" : "none",
              }}
            >
              <Icon
                size={15}
                color={active ? "#6366f1" : "var(--text-muted)"}
                style={{ flexShrink: 0 }}
              />
              {label}
              {active && (
                <div
                  style={{
                    marginLeft: "auto",
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#6366f1",
                    boxShadow: "0 0 8px #6366f1",
                  }}
                />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        style={{
          padding: "1rem 1.25rem",
          borderTop: "1px solid var(--border)",
          fontSize: "0.72rem",
          color: "var(--text-muted)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
          <div className="pulse-dot green" />
          <span>Pipeline Active</span>
        </div>
        <div style={{ opacity: 0.6 }}>v1.0.0 · all-MiniLM-L6-v2</div>
      </div>
    </aside>
  );
}
