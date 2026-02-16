"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

type Asset = {
  id: string;
  type: string;
  description: string;
  total_cost: string;
  created_at: string;
};

function AssetsPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Asset[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const selectedAssetId = useMemo(() => (searchParams.get("asset_id") || "").trim(), [searchParams]);

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/assets`, { cache: "no-store" });
      const json = await res.json();
      if (!res.ok) throw new Error(JSON.stringify(json));
      setRows(Array.isArray(json) ? json : []);
      setStatus("ok");
    } catch (e) {
      setStatus("error");
      setError(String(e));
    }
  }, []);

  useLiveRefresh(loadRows);

  const filteredRows = useMemo(() => {
    if (!selectedAssetId) return rows;
    return rows.filter((row) => row.id === selectedAssetId);
  }, [rows, selectedAssetId]);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/contributors" className="text-muted-foreground hover:text-foreground">
          Contributors
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Assets</h1>
      <p className="text-muted-foreground">
        Human interface for `GET /api/assets`.
        {selectedAssetId ? (
          <>
            {" "}
            Filtered by asset <code>{selectedAssetId}</code>.
          </>
        ) : null}
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">
            Total: {filteredRows.length}
            {selectedAssetId ? (
              <>
                {" "}
                | <Link href="/assets" className="underline hover:text-foreground">Clear filter</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((a) => (
              <li key={a.id} className="rounded border p-2 flex justify-between gap-3">
                <span className="font-medium">
                  <Link href={`/assets?asset_id=${encodeURIComponent(a.id)}`} className="hover:underline">
                    {a.id}
                  </Link>
                </span>
                <span className="text-muted-foreground text-right">
                  {a.type} | {a.description} | cost {a.total_cost} | {a.created_at}
                  <br />
                  <Link
                    href={`/contributions?asset_id=${encodeURIComponent(a.id)}`}
                    className="underline hover:text-foreground"
                  >
                    contributions
                  </Link>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

export default function AssetsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen p-8 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading assets…</p></main>}>
      <AssetsPageContent />
    </Suspense>
  );
}
