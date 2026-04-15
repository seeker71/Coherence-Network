"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { endpointHref, isStaticPath, scoreClass } from "./lib";
import { useApiCoverage } from "./use-api-coverage";

export default function ApiCoveragePage() {
  const {
    loading,
    error,
    traceability,
    canonical,
    probes,
    probeSummary,
    topFailures,
    probeByPath,
    topTraceabilityGaps,
    allEndpoints,
    refresh,
  } = useApiCoverage();

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
                    <td className={`py-2 pr-4 ${row.web_link?.sensed ? "text-emerald-700" : "text-destructive"}`}>
                      {row.web_link?.sensed ? "linked" : "missing"}
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
