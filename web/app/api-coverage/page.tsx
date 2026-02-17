"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { getApiBase } from "@/lib/api";

type EndpointTraceabilityItem = {
  path: string;
  methods: string[];
  traceability?: {
    fully_traced?: boolean;
    gaps?: string[];
  };
  usage?: {
    event_count?: number;
  };
  web_link?: {
    tracked?: boolean;
    explicit_count?: number;
    catalog_route?: string;
    evidence?: Array<{
      source_file?: string;
      line?: number | null;
      web_route?: string | null;
      evidence_type?: string;
    }>;
  };
};

type TraceabilityResponse = {
  summary?: {
    total_endpoints?: number;
    fully_traced?: number;
    with_usage_events?: number;
    with_web_link?: number;
    with_explicit_web_link?: number;
    missing_web_link?: number;
    missing_idea?: number;
    missing_spec?: number;
    missing_process?: number;
    missing_validation?: number;
  };
  items?: EndpointTraceabilityItem[];
};

type CanonicalRoutesResponse = {
  api_routes?: Array<{
    path?: string;
    methods?: string[];
  }>;
};

type ProbeResult = {
  path: string;
  method: string;
  status: "pass" | "fail" | "skipped";
  httpStatus?: number;
  error?: string;
  durationMs?: number;
  url?: string;
};

type JsonResult<T> = {
  ok: boolean;
  status: number;
  data?: T;
  error?: string;
};

const API_BASE = getApiBase();

const REQUIRED_QUERY_OVERRIDES: Record<string, string> = {
  "/gates/pr-to-public": "branch=main",
};

const SKIP_GET_PROBE: Record<string, string> = {
  "/gates/merged-contract": "Requires a known merged commit SHA query parameter.",
};

async function fetchJson<T>(url: string): Promise<JsonResult<T>> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    const text = await res.text();
    let parsed: unknown = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }

    if (!res.ok) {
      const errMsg =
        (parsed && typeof parsed === "object" && "detail" in parsed && typeof parsed.detail === "string"
          ? parsed.detail
          : text.slice(0, 240)) || `HTTP ${res.status}`;
      return { ok: false, status: res.status, error: errMsg };
    }
    return { ok: true, status: res.status, data: parsed as T };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function isStaticPath(path: string): boolean {
  return !path.includes("{") && !path.includes("}");
}

function buildProbeUrl(path: string): string {
  const apiPath = `/api${path}`;
  const qs = REQUIRED_QUERY_OVERRIDES[path];
  if (!qs) return `${API_BASE}${apiPath}`;
  return `${API_BASE}${apiPath}?${qs}`;
}

function endpointHref(path: string): string {
  if (isStaticPath(path)) return `${API_BASE}${path}`;
  return `${API_BASE}/docs`;
}

function scoreClass(status: ProbeResult["status"]): string {
  if (status === "pass") return "text-emerald-700";
  if (status === "fail") return "text-destructive";
  return "text-muted-foreground";
}

export default function ApiCoveragePage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traceability, setTraceability] = useState<TraceabilityResponse | null>(null);
  const [canonical, setCanonical] = useState<CanonicalRoutesResponse | null>(null);
  const [probes, setProbes] = useState<ProbeResult[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [traceRes, canonicalRes] = await Promise.all([
      fetchJson<TraceabilityResponse>(`${API_BASE}/api/inventory/endpoint-traceability?runtime_window_seconds=86400`),
      fetchJson<CanonicalRoutesResponse>(`${API_BASE}/api/inventory/routes/canonical`),
    ]);

    if (!traceRes.ok) {
      setError(`Traceability load failed: ${traceRes.error ?? `HTTP ${traceRes.status}`}`);
      setLoading(false);
      return;
    }
    if (!canonicalRes.ok) {
      setError(`Canonical routes load failed: ${canonicalRes.error ?? `HTTP ${canonicalRes.status}`}`);
      setLoading(false);
      return;
    }

    const traceData = traceRes.data ?? {};
    const canonicalData = canonicalRes.data ?? {};
    setTraceability(traceData);
    setCanonical(canonicalData);

    const traceItems = traceData.items ?? [];
    const probeTargets = traceItems
      .filter((item) => item.methods.includes("GET"))
      .map((item) => item.path)
      .sort();

    const probeResults = await Promise.all(
      probeTargets.map(async (path): Promise<ProbeResult> => {
        if (!isStaticPath(path)) {
          return {
            path,
            method: "GET",
            status: "skipped",
            error: "Dynamic path requires concrete id.",
          };
        }
        if (SKIP_GET_PROBE[path]) {
          return {
            path,
            method: "GET",
            status: "skipped",
            error: SKIP_GET_PROBE[path],
          };
        }

        const url = buildProbeUrl(path);
        const startedAt = Date.now();
        const result = await fetchJson<unknown>(url);
        const durationMs = Date.now() - startedAt;
        if (!result.ok) {
          return {
            path,
            method: "GET",
            status: "fail",
            httpStatus: result.status,
            error: result.error,
            durationMs,
            url,
          };
        }
        return {
          path,
          method: "GET",
          status: "pass",
          httpStatus: result.status,
          durationMs,
          url,
        };
      }),
    );

    setProbes(probeResults);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const probeSummary = useMemo(() => {
    const pass = probes.filter((row) => row.status === "pass").length;
    const fail = probes.filter((row) => row.status === "fail").length;
    const skipped = probes.filter((row) => row.status === "skipped").length;
    return { pass, fail, skipped };
  }, [probes]);

  const topFailures = useMemo(
    () => probes.filter((row) => row.status === "fail").sort((a, b) => a.path.localeCompare(b.path)).slice(0, 20),
    [probes],
  );
  const probeByPath = useMemo(() => {
    const out = new Map<string, ProbeResult>();
    for (const probe of probes) out.set(probe.path, probe);
    return out;
  }, [probes]);

  const topTraceabilityGaps = useMemo(
    () =>
      (traceability?.items ?? [])
        .filter((row) => !row.traceability?.fully_traced)
        .sort((a, b) => {
          const aGap = a.traceability?.gaps?.length ?? 0;
          const bGap = b.traceability?.gaps?.length ?? 0;
          if (bGap !== aGap) return bGap - aGap;
          return a.path.localeCompare(b.path);
        })
        .slice(0, 25),
    [traceability],
  );
  const allEndpoints = useMemo(
    () => [...(traceability?.items ?? [])].sort((a, b) => a.path.localeCompare(b.path)),
    [traceability],
  );

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
      </div>

      <section className="space-y-2">
        <h1 className="text-2xl font-bold">API Coverage Verification</h1>
        <p className="text-muted-foreground">
          Live verification dashboard using real API responses. Includes endpoint traceability gaps and GET probe
          checks with explicit error handling.
        </p>
      </section>

      <section className="border border-border rounded-md p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Live Snapshot</h2>
          <Button onClick={() => void refresh()} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </Button>
        </div>
        {error && <p className="text-destructive text-sm">{error}</p>}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
          <div className="rounded border p-3">
            <p className="text-muted-foreground">Endpoints discovered</p>
            <p className="text-xl font-semibold">{traceability?.summary?.total_endpoints ?? 0}</p>
          </div>
          <div className="rounded border p-3">
            <p className="text-muted-foreground">Fully traced</p>
            <p className="text-xl font-semibold">{traceability?.summary?.fully_traced ?? 0}</p>
          </div>
          <div className="rounded border p-3">
            <p className="text-muted-foreground">GET probe pass/fail</p>
            <p className="text-xl font-semibold">
              {probeSummary.pass}/{probeSummary.fail}
            </p>
          </div>
          <div className="rounded border p-3">
            <p className="text-muted-foreground">Canonical API routes</p>
            <p className="text-xl font-semibold">{canonical?.api_routes?.length ?? 0}</p>
          </div>
          <div className="rounded border p-3">
            <p className="text-muted-foreground">Endpoints with web links</p>
            <p className="text-xl font-semibold">
              {(traceability?.summary?.with_web_link ?? 0)}/{traceability?.summary?.total_endpoints ?? 0}
            </p>
          </div>
        </div>
      </section>

      <section className="border border-border rounded-md p-4 space-y-3">
        <h2 className="text-lg font-semibold">Top Traceability Gaps</h2>
        <p className="text-sm text-muted-foreground">
          Missing idea/spec/process/validation links indicate APIs that are not fully verified end-to-end.
        </p>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-4">Path</th>
                <th className="py-2 pr-4">Methods</th>
                <th className="py-2 pr-4">Gaps</th>
                <th className="py-2 pr-4">Usage Events</th>
              </tr>
            </thead>
            <tbody>
              {topTraceabilityGaps.map((row) => (
                <tr key={row.path} className="border-t">
                  <td className="py-2 pr-4 font-mono">{row.path}</td>
                  <td className="py-2 pr-4">{(row.methods ?? []).join(", ") || "-"}</td>
                  <td className="py-2 pr-4">{(row.traceability?.gaps ?? []).join(", ") || "-"}</td>
                  <td className="py-2 pr-4">{row.usage?.event_count ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border border-border rounded-md p-4 space-y-3">
        <h2 className="text-lg font-semibold">GET Probe Results</h2>
        <p className="text-sm text-muted-foreground">
          Static GET endpoints are called directly against the API base and marked pass/fail/skipped.
        </p>
        <p className="text-sm text-muted-foreground">
          Pass: {probeSummary.pass} | Fail: {probeSummary.fail} | Skipped: {probeSummary.skipped}
        </p>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-4">Path</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">HTTP</th>
                <th className="py-2 pr-4">Duration</th>
                <th className="py-2 pr-4">Error / URL</th>
              </tr>
            </thead>
            <tbody>
              {probes.map((row) => (
                <tr key={`${row.path}-${row.status}`} className="border-t">
                  <td className="py-2 pr-4 font-mono">{row.path}</td>
                  <td className={`py-2 pr-4 font-medium ${scoreClass(row.status)}`}>{row.status}</td>
                  <td className="py-2 pr-4">{row.httpStatus ?? "-"}</td>
                  <td className="py-2 pr-4">{typeof row.durationMs === "number" ? `${row.durationMs}ms` : "-"}</td>
                  <td className="py-2 pr-4 text-xs">
                    {row.error ? row.error : row.url ? <span className="font-mono">{row.url}</span> : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {topFailures.length > 0 && (
        <section className="border border-destructive/40 rounded-md p-4 space-y-3">
          <h2 className="text-lg font-semibold text-destructive">Failing GET Probes</h2>
          <ul className="space-y-2 text-sm">
            {topFailures.map((row) => (
              <li key={`fail-${row.path}`} className="font-mono">
                {row.path} [{row.httpStatus ?? "ERR"}] {row.error}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="border border-border rounded-md p-4 space-y-3">
        <h2 className="text-lg font-semibold">All Endpoints</h2>
        <p className="text-sm text-muted-foreground">
          Full API list with current verification signal. Static GET endpoints include active probes; others use
          traceability and usage evidence.
        </p>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-4">Path</th>
                <th className="py-2 pr-4">Methods</th>
                <th className="py-2 pr-4">Traceability</th>
                <th className="py-2 pr-4">Web Link</th>
                <th className="py-2 pr-4">Verification</th>
                <th className="py-2 pr-4">Notes</th>
              </tr>
            </thead>
            <tbody>
              {allEndpoints.map((row) => {
                const hasGet = row.methods.includes("GET");
                const staticGet = hasGet && isStaticPath(row.path);
                const probe = probeByPath.get(row.path);
                const webEvidence = row.web_link?.evidence ?? [];
                const firstEvidence = webEvidence[0];
                return (
                  <tr key={`endpoint-${row.path}`} id={`endpoint-${encodeURIComponent(row.path)}`} className="border-t">
                    <td className="py-2 pr-4 font-mono">
                      <a href={endpointHref(row.path)} target="_blank" rel="noopener noreferrer" className="underline">
                        {row.path}
                      </a>
                    </td>
                    <td className="py-2 pr-4">{row.methods.join(", ")}</td>
                    <td className={`py-2 pr-4 ${row.traceability?.fully_traced ? "text-emerald-700" : "text-destructive"}`}>
                      {row.traceability?.fully_traced ? "fully_traced" : "gapped"}
                    </td>
                    <td className={`py-2 pr-4 ${row.web_link?.tracked ? "text-emerald-700" : "text-destructive"}`}>
                      {row.web_link?.tracked ? "linked" : "missing"}
                      {firstEvidence?.source_file ? (
                        <span className="block text-xs text-muted-foreground">
                          {firstEvidence.source_file}
                          {typeof firstEvidence.line === "number" ? `:${firstEvidence.line}` : ""}
                        </span>
                      ) : null}
                    </td>
                    <td className={`py-2 pr-4 ${probe ? scoreClass(probe.status) : "text-muted-foreground"}`}>
                      {probe ? probe.status : staticGet ? "pending" : "traceability-only"}
                    </td>
                    <td className="py-2 pr-4 text-xs">
                      {probe?.error ||
                        (probe?.httpStatus ? `HTTP ${probe.httpStatus}` : null) ||
                        (staticGet
                          ? "Active GET probe."
                          : hasGet
                            ? "GET has dynamic/path requirements."
                            : "Non-GET endpoint; validated by traceability usage/process signals.")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
