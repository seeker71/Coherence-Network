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
    <main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8">
      <div className="mx-auto w-full max-w-7xl space-y-4">
        <section className="space-y-1 px-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Assets In Motion</h1>
          <p className="max-w-3xl text-sm text-muted-foreground sm:text-base">
            Human interface for <code>GET /api/assets</code> with linked contribution pathways.
          </p>
          {selectedAssetId ? (
            <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              Filtered by asset <code>{selectedAssetId}</code>.
            </p>
          ) : null}
        </section>

        <section className="rounded-xl border border-border/70 bg-card/50 px-3 py-3">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { href: "/", label: "Home" },
              { href: "/portfolio", label: "Portfolio" },
              { href: "/contributors", label: "Contributors" },
              { href: "/contributions", label: "Contributions" },
              { href: "/tasks", label: "Tasks" },
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

        {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
        {status === "error" && <p className="text-destructive">Error: {error}</p>}

        {status === "ok" && (
        <section className="rounded-2xl border border-border/70 bg-card/60 p-4 shadow-sm space-y-3">
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
              <li key={a.id} className="rounded-lg border border-border/70 bg-background/45 p-2 flex justify-between gap-3">
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
      </div>
    </main>
  );
}

export default function AssetsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen px-4 pb-8 pt-6 sm:px-6 lg:px-8"><div className="mx-auto w-full max-w-7xl"><p className="text-muted-foreground">Loading assets…</p></div></main>}>
      <AssetsPageContent />
    </Suspense>
  );
}
