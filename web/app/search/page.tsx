"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProjectSummary {
  name: string;
  ecosystem: string;
  description: string;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ProjectSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "error">(
    "idle"
  );
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await fetch(
        `${API_URL}/api/search?q=${encodeURIComponent(query.trim())}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setResults(json.results ?? []);
      setTotal(json.total ?? 0);
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
      <h1 className="text-2xl font-bold mb-4">Search projects</h1>
      <form onSubmit={handleSearch} className="flex gap-2 mb-6">
        <Input
          type="search"
          placeholder="e.g. react, lodash"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" disabled={status === "loading"}>
          Search
        </Button>
      </form>
      {status === "loading" && <p className="text-muted-foreground">Searching…</p>}
      {status === "error" && (
        <p className="text-destructive">
          API error: {error}. Is the API running?
        </p>
      )}
      {status === "ok" && (
        <section>
          <p className="text-sm text-muted-foreground mb-4">
            {total} result{total !== 1 ? "s" : ""}
          </p>
          <ul className="space-y-3">
            {results.map((r) => (
              <li key={`${r.ecosystem}/${r.name}`}>
                <Link
                  href={`/project/${r.ecosystem}/${r.name}`}
                  className="block p-3 rounded-md border border-border hover:bg-accent"
                >
                  <span className="font-medium">{r.name}</span>
                  <span className="text-muted-foreground text-sm ml-2">
                    {r.ecosystem}
                  </span>
                  {r.description && (
                    <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                      {r.description}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
