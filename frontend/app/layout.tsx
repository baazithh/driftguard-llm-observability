import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "DriftGuard — LLM Observability",
  description:
    "Real-time LLM observability and self-correcting evaluation pipeline with semantic drift detection and autonomous prompt repair.",
  keywords: ["LLM", "observability", "drift detection", "AI monitoring"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="layout">
          <Sidebar />
          <main className="main-content">{children}</main>
        </div>
      </body>
    </html>
  );
}
