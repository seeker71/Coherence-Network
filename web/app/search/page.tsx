import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/lib/api";

type ProjectSummary = {
  name: string;
  ecosystem: string;
  description: string;
};

type SearchResponse = {
  results: ProjectSummary[];
  total: number;
};

async function fetchSearch(q: string): Promise<SearchResponse> {
  const API_URL = getApiBase();
  const res = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(q)}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = (await res.json()) as Partial<SearchResponse>;
  return {
    results: Array.isArray(json.results) ? (json.results as ProjectSummary[]) : [],
    total: typeof json.total === "number" ? json.total : 0,
  };
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = searchParams ? await searchParams : undefined;
  const raw = sp?.q;
  const q = (typeof raw === "string" ? raw : Array.isArray(raw) ? raw[0] : "").trim();

  const data = q ? await fetchSearch(q) : { results: [], total: 0 };

  return (
    <main className="min-h-screen p-8 max-w-2xl mx-auto space-y-6">
      <div>
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
      </div>

      <header className="space-y-2">
        <h1 className="text-2xl font-bold">Search projects</h1>
        <p className="text-muted-foreground text-sm">
          Enter a package name (npm, PyPI). Results link to project pages.
        </p>
      </header>

      <form action="/search" method="GET" className="flex gap-2">
        <Input name="q" type="search" placeholder="e.g. react, lodash" defaultValue={q} className="flex-1" />
        <Button type="submit">Search</Button>
      </form>

      {q ? (
        <section className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {data.total} result{data.total !== 1 ? "s" : ""} for{" "}
            <code className="rounded bg-muted px-1 py-0.5">{q}</code>
          </p>
          {data.results.length === 0 ? (
            <p className="text-sm text-muted-foreground">No matches yet. Indexing/ingestion is still sparse.</p>
          ) : (
            <ul className="space-y-3">
              {data.results.map((r) => (
                <li key={`${r.ecosystem}/${r.name}`}>
                  <Link
                    href={`/project/${r.ecosystem}/${r.name}`}
                    className="block p-3 rounded-md border border-border hover:bg-accent"
                  >
                    <span className="font-medium">{r.name}</span>
                    <span className="text-muted-foreground text-sm ml-2">{r.ecosystem}</span>
                    {r.description ? (
                      <p className="text-sm text-muted-foreground mt-1 line-clamp-2">{r.description}</p>
                    ) : null}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <p className="text-sm text-muted-foreground">
          Tip: from the home page or header search box, you can jump here with{" "}
          <code className="rounded bg-muted px-1 py-0.5">/search?q=react</code>.
        </p>
      )}
    </main>
  );
}
