"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase, getApiKey, getContributorId, setContributorId } from "@/lib/api";

const API = getApiBase();

export default function MyPortfolioPage() {
  const router = useRouter();
  const [contributorId, setContributorIdState] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkAuth = useCallback(async () => {
    const key = getApiKey();
    const storedId = getContributorId();

    if (key) {
      try {
        const res = await fetch(`${API}/api/auth/whoami`, {
          headers: { "X-API-Key": key },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated && data.contributor_id) {
            setContributorId(data.contributor_id);
            router.replace(`/contributors/${encodeURIComponent(data.contributor_id)}/portfolio`);
            return;
          }
        }
      } catch (e) {
        console.error("Auth check failed:", e);
      }
    }

    if (storedId) {
      setContributorIdState(storedId);
    }
    setLoading(false);
  }, [router]);

  useEffect(() => {
    void checkAuth();
  }, [checkAuth]);

  function handleGo(e: React.FormEvent) {
    e.preventDefault();
    const id = contributorId.trim();
    if (!id) return;
    setContributorId(id);
    router.push(`/contributors/${encodeURIComponent(id)}/portfolio`);
  }

  if (loading) {
    return (
      <main className="min-h-screen px-4 md:px-8 py-10 max-w-2xl mx-auto flex items-center justify-center">
        <p className="text-muted-foreground animate-pulse">Checking credentials…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-2xl mx-auto space-y-8 flex flex-col items-center justify-center">
      <div className="w-full rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 space-y-6 text-center shadow-xl">
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground uppercase tracking-widest">My Portfolio</p>
          <h1 className="text-3xl md:text-4xl font-light tracking-tight">What have I built?</h1>
          <p className="text-muted-foreground max-w-md mx-auto">
            View your personal dashboard of identities, CC balance, ideas, stakes, and completed tasks.
          </p>
        </div>

        <form onSubmit={handleGo} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto w-full">
          <Input
            placeholder="Contributor ID or handle"
            value={contributorId}
            onChange={(e) => setContributorIdState(e.target.value)}
            className="flex-1 h-12"
            autoFocus
          />
          <Button type="submit" disabled={!contributorId.trim()} className="h-12 px-8">
            View Portfolio
          </Button>
        </form>

        <div className="pt-4 border-t border-border/10 flex flex-col gap-2 items-center">
          <p className="text-xs text-muted-foreground">Don't have a contributor identity yet?</p>
          <Button variant="outline" size="sm" onClick={() => router.push("/identity")}>
            Setup Identity
          </Button>
        </div>
      </div>
    </main>
  );
}
