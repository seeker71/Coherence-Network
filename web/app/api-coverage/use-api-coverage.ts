import { useCallback, useEffect, useMemo, useState } from "react";
import { UI_RUNTIME_WINDOW } from "@/lib/egress";
import {
  API_BASE,
  buildProbeUrl,
  fetchJson,
  isStaticPath,
  SKIP_GET_PROBE,
} from "./lib";
import type {
  CanonicalRoutesResponse,
  ProbeResult,
  TraceabilityResponse,
} from "./types";

export function useApiCoverage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [traceability, setTraceability] = useState<TraceabilityResponse | null>(null);
  const [canonical, setCanonical] = useState<CanonicalRoutesResponse | null>(null);
  const [probes, setProbes] = useState<ProbeResult[]>([]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    const [traceRes, canonicalRes] = await Promise.all([
      fetchJson<TraceabilityResponse>(
        `${API_BASE}/api/inventory/endpoint-traceability?runtime_window_seconds=${UI_RUNTIME_WINDOW}`,
      ),
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
    () =>
      probes
        .filter((row) => row.status === "fail")
        .sort((a, b) => a.path.localeCompare(b.path))
        .slice(0, 20),
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

  return {
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
  };
}
