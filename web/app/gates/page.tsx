"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();

export default function GatesPage() {
  const [branch, setBranch] = useState("main");
  const [sha, setSha] = useState("");
  const [prReport, setPrReport] = useState<Record<string, unknown> | null>(null);
  const [contractReport, setContractReport] = useState<Record<string, unknown> | null>(null);
  const [publicDeployReport, setPublicDeployReport] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function runPrGate() {
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/gates/pr-to-public?branch=${encodeURIComponent(branch)}`
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
      const res = await fetch(`${API_URL}/api/gates/main-contract`);
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
        `${API_URL}/api/gates/merged-contract?sha=${encodeURIComponent(sha.trim())}`
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
      const res = await fetch(`${API_URL}/api/gates/public-deploy-contract`);
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setPublicDeployReport(json);
      setStatus("idle");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }

  return (
    <main className="min-h-screen p-8 max-w-4xl mx-auto space-y-6">
      <div>
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Gate Status</h1>
      <p className="text-muted-foreground">
        Human interface for release/public gate inspection. Machine clients should use the
        `/api/gates/*` endpoints directly.
      </p>

      <section className="space-y-3 border border-border rounded-md p-4">
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

      <section className="space-y-3 border border-border rounded-md p-4">
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

      <section className="space-y-3 border border-border rounded-md p-4">
        <h2 className="text-lg font-semibold">Public Deploy Contract</h2>
        <Button variant="outline" onClick={runPublicDeployContract} disabled={status === "loading"}>
          Check Public Deploy Contract
        </Button>
      </section>

      {status === "error" && error && (
        <p className="text-destructive">Error: {error}</p>
      )}

      {prReport && (
        <section className="space-y-2">
          <h3 className="font-medium">PR Gate Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(prReport, null, 2)}
          </pre>
        </section>
      )}

      {contractReport && (
        <section className="space-y-2">
          <h3 className="font-medium">Change Contract Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(contractReport, null, 2)}
          </pre>
        </section>
      )}

      {publicDeployReport && (
        <section className="space-y-2">
          <h3 className="font-medium">Public Deploy Report</h3>
          <pre className="text-xs bg-muted p-3 rounded-md overflow-auto">
            {JSON.stringify(publicDeployReport, null, 2)}
          </pre>
        </section>
      )}
    </main>
  );
}
