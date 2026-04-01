"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function MyPortfolioPage() {
  const router = useRouter();
  const [contributorId, setContributorId] = useState("");

  function handleGo(e: React.FormEvent) {
    e.preventDefault();
    const id = contributorId.trim();
    if (!id) return;
    router.push(`/contributors/${encodeURIComponent(id)}/portfolio`);
  }

  return (
    <main className="min-h-screen px-4 md:px-8 py-10 max-w-2xl mx-auto space-y-8 flex flex-col items-center justify-center">
      <div className="w-full rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-8 space-y-6 text-center">
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground uppercase tracking-widest">My Garden</p>
          <h1 className="text-3xl md:text-4xl font-light tracking-tight">What have I grown?</h1>
          <p className="text-muted-foreground">
            Enter your contributor name to see your harvest, plants, seeds planted, and garden work.
          </p>
        </div>

        <form onSubmit={handleGo} className="flex gap-2 max-w-md mx-auto">
          <Input
            placeholder="Contributor name"
            value={contributorId}
            onChange={(e) => setContributorId(e.target.value)}
            className="flex-1"
            autoFocus
          />
          <Button type="submit" disabled={!contributorId.trim()}>
            View Garden
          </Button>
        </form>

        <p className="text-xs text-muted-foreground/60 pt-2">
          <a href="/invest" className="hover:text-foreground transition-colors underline">
            Visit the Garden of Ideas →
          </a>
        </p>
      </div>
    </main>
  );
}
