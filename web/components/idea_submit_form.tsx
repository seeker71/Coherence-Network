"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function IdeaSubmitForm() {
  const [idea, setIdea] = useState("");
  const [contributorName, setContributorName] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [createdId, setCreatedId] = useState<string | null>(null);

  // Load saved contributor name from localStorage
  useEffect(() => {
    try {
      const saved = localStorage.getItem("coherence_contributor_id");
      if (saved) setContributorName(saved);
    } catch {
      // localStorage not available
    }
  }, []);

  // Persist contributor name when it changes
  useEffect(() => {
    try {
      if (contributorName.trim()) {
        localStorage.setItem("coherence_contributor_id", contributorName.trim());
      }
    } catch {
      // localStorage not available
    }
  }, [contributorName]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!idea.trim()) return;

    setStatus("submitting");

    // Generate a slug from the idea text
    const slug = idea
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-")
      .slice(0, 60);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const body: Record<string, unknown> = {
        id: slug || `idea-${Date.now()}`,
        name: idea.slice(0, 120),
        description: idea,
        potential_value: 50,
        estimated_cost: 10,
        resistance_risk: 3,
        confidence: 0.6,
        manifestation_status: "none",
      };
      if (contributorName.trim()) {
        body.contributor_id = contributorName.trim();
      }
      const resp = await fetch(`${apiBase}/api/ideas`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (resp.ok) {
        const data = await resp.json();
        setCreatedId(data.id);
        setIdea("");
        setStatus("success");
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  }

  if (status === "success" && createdId) {
    return (
      <div className="space-y-4 text-center animate-fade-in-up">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30">
          <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <p className="text-lg font-medium">Your idea is live!</p>
        <Link
          href={`/ideas/${encodeURIComponent(createdId)}`}
          className="inline-flex items-center gap-1 text-primary hover:text-foreground transition-colors underline underline-offset-4"
        >
          View it &rarr;
        </Link>
        <div>
          <button
            type="button"
            onClick={() => {
              setStatus("idle");
              setCreatedId(null);
            }}
            className="text-sm text-muted-foreground/60 hover:text-foreground transition-colors underline underline-offset-4"
          >
            Share another idea
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <textarea
        value={idea}
        onChange={(e) => {
          setIdea(e.target.value);
          if (status === "error") setStatus("idle");
        }}
        rows={3}
        placeholder="I think there should be a way to..."
        className="w-full rounded-2xl border border-border/40 bg-card/60 backdrop-blur-sm px-6 py-4 text-base md:text-lg placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 resize-none transition-all duration-300"
      />
      <input
        type="text"
        value={contributorName}
        onChange={(e) => setContributorName(e.target.value)}
        placeholder="Your name (optional)"
        className="w-full max-w-xs mx-auto block rounded-full border border-border/30 bg-card/40 px-4 py-2 text-sm text-muted-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/20 transition-all duration-300"
      />
      <div className="flex flex-col sm:flex-row gap-3 justify-center items-center">
        <Button
          type="submit"
          disabled={!idea.trim() || status === "submitting"}
          className="w-full sm:w-auto rounded-full px-8 py-3 text-base min-h-[44px]"
        >
          {status === "submitting" ? (
            <span className="inline-flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Sharing...
            </span>
          ) : "Share your idea"}
        </Button>
        <a
          href="/resonance"
          className="text-muted-foreground hover:text-foreground transition-colors duration-300 underline underline-offset-4 py-3 text-sm"
        >
          or see what others are working on
        </a>
      </div>
      {status === "error" && (
        <div className="flex items-center justify-center gap-2 text-sm text-amber-600 dark:text-amber-400 text-center">
          <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>Something went wrong. Try again?</span>
        </div>
      )}
    </form>
  );
}
