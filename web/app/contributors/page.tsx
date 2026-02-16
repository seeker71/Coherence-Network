"use client";

import { Suspense, useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { getApiBase } from "@/lib/api";
import { useLiveRefresh } from "@/lib/live_refresh";

const API_URL = getApiBase();

type Contributor = {
  id: string;
  name: string;
  type: string;
  email: string;
  created_at: string;
};

function ContributorsPageContent() {
  const searchParams = useSearchParams();
  const [rows, setRows] = useState<Contributor[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const selectedContributorId = useMemo(
    () => (searchParams.get("contributor_id") || "").trim(),
    [searchParams]
  );

  const loadRows = useCallback(async () => {
    setStatus((prev) => (prev === "ok" ? "ok" : "loading"));
    setError(null);
    try {
      const res = await fetch(`${API_URL}/v1/contributors`, { cache: "no-store" });
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
    if (!selectedContributorId) return rows;
    return rows.filter((row) => row.id === selectedContributorId);
  }, [rows, selectedContributorId]);

  return (
    <main className="min-h-screen p-8 max-w-5xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Home
        </Link>
        <Link href="/portfolio" className="text-muted-foreground hover:text-foreground">
          Portfolio
        </Link>
        <Link href="/contributions" className="text-muted-foreground hover:text-foreground">
          Contributions
        </Link>
        <Link href="/assets" className="text-muted-foreground hover:text-foreground">
          Assets
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
      </div>
      <h1 className="text-2xl font-bold">Contributors</h1>
      <p className="text-muted-foreground">
        Human interface for `GET /v1/contributors`.
        {selectedContributorId ? (
          <>
            {" "}
            Filtered by contributor <code>{selectedContributorId}</code>.
          </>
        ) : null}
      </p>

      {status === "loading" && <p className="text-muted-foreground">Loading…</p>}
      {status === "error" && <p className="text-destructive">Error: {error}</p>}

      {status === "ok" && (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm text-muted-foreground">
            Total: {filteredRows.length}
            {selectedContributorId ? (
              <>
                {" "}
                | <Link href="/contributors" className="underline hover:text-foreground">Clear filter</Link>
              </>
            ) : null}
          </p>
          <ul className="space-y-2 text-sm">
            {filteredRows.slice(0, 100).map((c) => (
              <li key={c.id} className="rounded border p-2 flex justify-between gap-3">
                <span className="font-medium">
                  <Link href={`/contributors?contributor_id=${encodeURIComponent(c.id)}`} className="hover:underline">
                    {c.name}
                  </Link>
                </span>
                <span className="text-muted-foreground text-right">
                  {c.type} | {c.email} | {c.created_at}
                  <br />
                  <Link
                    href={`/contributions?contributor_id=${encodeURIComponent(c.id)}`}
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

export default function ContributorsPage() {
  return (
    <Suspense fallback={<main className="min-h-screen p-8 max-w-5xl mx-auto"><p className="text-muted-foreground">Loading contributors…</p></main>}>
      <ContributorsPageContent />
    </Suspense>
  );
}
