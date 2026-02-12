"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ImportPackage {
  name: string;
  version: string;
  coherence: number | null;
  status: string;
  dependencies: string[];
}

interface RiskSummary {
  unknown: number;
  low: number;
  medium: number;
  high: number;
}

interface ImportResult {
  packages: ImportPackage[];
  risk_summary: RiskSummary;
}

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">(
    "idle"
  );
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setStatus("loading");
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_URL}/api/import/stack`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const json = await res.json();
      setResult(json);
      setStatus("ok");
    } catch (e) {
      setError(String(e));
      setStatus("error");
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
      </div>
      <h1 className="text-2xl font-bold mb-4">Import stack</h1>
      <p className="text-muted-foreground mb-6">
        Upload package-lock.json or requirements.txt to analyze dependencies and coherence risk.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 mb-8">
        <div>
          <label
            htmlFor="file"
            className="block text-sm font-medium mb-2"
          >
            package-lock.json or requirements.txt
          </label>
          <Input
            id="file"
            type="file"
            accept=".json,.txt,application/json,text/plain"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="w-full"
          />
        </div>
        <Button type="submit" disabled={status === "loading" || !file}>
          {status === "loading" ? "Analyzing…" : "Analyze"}
        </Button>
      </form>
      {status === "error" && (
        <p className="text-destructive mb-4">
          {error}. Is the API running?
        </p>
      )}
      {status === "ok" && result && (
        <section className="space-y-6">
          <h2 className="text-lg font-semibold">Risk summary</h2>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <dt className="text-muted-foreground">Unknown</dt>
              <dd className="font-medium">{result.risk_summary.unknown}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Low (&lt;0.4)</dt>
              <dd className="font-medium">{result.risk_summary.low}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Medium (0.4–0.7)</dt>
              <dd className="font-medium">{result.risk_summary.medium}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">High (≥0.7)</dt>
              <dd className="font-medium">{result.risk_summary.high}</dd>
            </div>
          </dl>
          <h2 className="text-lg font-semibold">
            Packages ({result.packages.length})
          </h2>
          <ul className="space-y-2 text-sm">
            {result.packages.map((p) => (
              <li
                key={`${p.name}@${p.version}`}
                className="flex items-center justify-between p-2 rounded border border-border"
              >
                <span>
                  <strong>{p.name}</strong>@{p.version}
                </span>
                <span
                  className={
                    p.status === "known"
                      ? p.coherence !== null && p.coherence >= 0.7
                        ? "text-green-600"
                        : p.coherence !== null && p.coherence >= 0.4
                        ? "text-yellow-600"
                        : "text-orange-600"
                      : "text-muted-foreground"
                  }
                >
                  {p.status === "known"
                    ? p.coherence !== null
                      ? `coherence ${p.coherence}`
                      : ""
                    : "unknown"}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
