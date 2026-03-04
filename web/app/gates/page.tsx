"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

export default function GatesPage() {
  const [branch, setBranch] = useState("main");
  const [sha, setSha] = useState("");
  const [prReport, setPrReport] = useState<Record<string, unknown> | null>(null);
  const [contractReport, setContractReport] = useState<Record<string, unknown> | null>(null);
  const [publicDeployReport, setPublicDeployReport] = useState<Record<string, unknown> | null>(null);
  const [traceabilityReport, setTraceabilityReport] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const runLiveSnapshot = useCallback(async () => {
    setStatus((prev) => (prev === "idle" ? "loading" : prev));
    setError(null);
    try {
      const [mainRes, publicRes, traceRes] = await Promise.all([
        fetch(`${API_URL}/api/gates/main-contract`, { cache: "no-store" }),
        fetch(`${API_URL}/api/gates/public-deploy-contract`, { cache: "no-store" }),
        fetch(`${API_URL}/api/inventory/endpoint-traceability`, { cache: "no-store" }),
      ]);
      const [mainJson, publicJson, traceJson] = await Promise.all([
        mainRes.json(),
        publicRes.json(),
        traceRes.json(),
      ]);
      if (!mainRes.ok) throw new Error(JSON.stringify(mainJson));
      if (!publicRes.ok) throw new Error(JSON.stringify(publicJson));
      if (!traceRes.ok) throw new Error(JSON.stringify(traceJson));
      setContractReport(mainJson);
      if (typeof mainJson.sha === "string") setSha(mainJson.sha);
      setPublicDeployReport(publicJson);
      setTraceabilityReport(traceJson);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(runLiveSnapshot);

  async function runPrGate() {
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/gates/pr-to-public?branch=${encodeURIComponent(branch)}`,
        { cache: "no-store" }
      );
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setPrReport(json);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  async function runMainContract() {
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/gates/main-contract`, { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setContractReport(json);
      if (typeof json.sha === "string") setSha(json.sha);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  async function runShaContract() {
    if (!sha.trim()) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/gates/merged-contract?sha=${encodeURIComponent(sha.trim())}`,
        { cache: "no-store" }
      );
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setContractReport(json);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  async function runPublicDeployContract() {
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/gates/public-deploy-contract`, { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setPublicDeployReport(json);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  async function runEndpointTraceability() {
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/inventory/endpoint-traceability`, { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setTraceabilityReport(json);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  return (
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="space-y-1 px-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Gate Status In Motion</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            Live release/public gate inspection. Machine clients should continue using <code>/api/gates/*</code> directly.
          </p>
        </section>

        <section className="rounded-xl border border-border/70 bg-card/50 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { href: "/", label: "Home" },
              { href: "/tasks", label: "Tasks" },
              { href: "/flow", label: "Flow" },
              { href: "/usage", label: "Usage" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="inline-flex items-center rounded-full border border-border/70 bg-background/55 px-3 py-1.5 text-sm text-muted-foreground transition hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
          </div>
        </section>

        <section className="space-y-3 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
        <h2 className="text-lg font-semibold">PR → Public Readiness</h2>
        <div className="flex gap-2">
          <Input
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder="branch name"
          />
          <Button onClick={runPrGate} disabled={status === "loading"}>
            Check PR Gate
          </Button>
        </div>
      </section>

      <section className="space-y-3 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Merged Change Contract</h2>
        <div className="flex gap-2">
          <Input
            value={sha}
            onChange={(e) => setSha(e.target.value)}
            placeholder="merged commit SHA"
          />
          <Button onClick={runShaContract} disabled={status === "loading" || !sha.trim()}>
            Check SHA Contract
          </Button>
          <Button variant="outline" onClick={runMainContract} disabled={status === "loading"}>
            Check Main HEAD
          </Button>
        </div>
      </section>

      <section className="space-y-3 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Public Deploy Contract</h2>
        <Button variant="outline" onClick={runPublicDeployContract} disabled={status === "loading"}>
          Check Public Deploy Contract
        </Button>
        <Button variant="secondary" onClick={runLiveSnapshot} disabled={status === "loading"}>
          Refresh All Live Reports
        </Button>
      </section>

      <section className="space-y-3 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
        <h2 className="text-lg font-semibold">Endpoint Traceability Coverage</h2>
        <p className="text-sm text-muted-foreground">
          Verify every endpoint is mapped to idea, spec, process, and validation signals.
        </p>
        <Button variant="outline" onClick={runEndpointTraceability} disabled={status === "loading"}>
          Check Endpoint Traceability
        </Button>
      </section>

      {status === "error" && error && (
        <p className="text-destructive">Error: {error}</p>
      )}

      {prReport && (
        <section className="space-y-2 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
          <h3 className="font-medium">PR Gate Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(prReport, null, 2)}
          </pre>
        </section>
      )}

      {contractReport && (
        <section className="space-y-2 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
          <h3 className="font-medium">Change Contract Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(contractReport, null, 2)}
          </pre>
        </section>
      )}

      {publicDeployReport && (
        <section className="space-y-2 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
          <h3 className="font-medium">Public Deploy Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(publicDeployReport, null, 2)}
          </pre>
        </section>
      )}

      {traceabilityReport && (
        <section className="space-y-2 rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm">
          <h3 className="font-medium">Endpoint Traceability Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(traceabilityReport, null, 2)}
          </pre>
        </section>
      )}
      </div>
    </main>
  );
}
