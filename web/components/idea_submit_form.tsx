"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export function IdeaSubmitForm() {
  const [idea, setIdea] = useState("");
  const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">("idle");
  const [createdId, setCreatedId] = useState<string | null>(null);
  const router = useRouter();

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
      const apiBase = process.env.NEXT_PUBLIC_API_BASE || "https://api.coherencycoin.com";
      const resp = await fetch(`${apiBase}/api/ideas`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "dev-key",
        },
        body: JSON.stringify({
          id: slug || `idea-${Date.now()}`,
          name: idea.slice(0, 120),
          description: idea,
          potential_value: 50,
          estimated_cost: 10,
          resistance_risk: 3,
          confidence: 0.6,
          manifestation_status: "none",
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        setCreatedId(data.id);
        setStatus("success");
        // Redirect to the idea page after a moment
        setTimeout(() => {
          router.push(`/ideas/${data.id}`);
        }, 2000);
      } else {
        setStatus("error");
      }
    } catch {
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className="space-y-4 text-center animate-fade-in-up">
        <div className="text-4xl">✨</div>
        <p className="text-lg">Your idea is alive.</p>
        <p className="text-muted-foreground text-sm">
          Taking you there now...
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <textarea
        value={idea}
        onChange={(e) => setIdea(e.target.value)}
        rows={3}
        placeholder="I think there should be a way to..."
        className="w-full rounded-2xl border border-border/40 bg-card/60 backdrop-blur-sm px-6 py-4 text-base md:text-lg placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 resize-none transition-all duration-300"
      />
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Button
          type="submit"
          disabled={!idea.trim() || status === "submitting"}
          className="rounded-full px-8 py-3 text-base"
        >
          {status === "submitting" ? "Sharing..." : "Share your idea"}
        </Button>
        <a
          href="/resonance"
          className="text-muted-foreground hover:text-foreground transition-colors duration-300 underline underline-offset-4 py-3 text-sm"
        >
          or see what others are working on
        </a>
      </div>
      {status === "error" && (
        <p className="text-sm text-red-400 text-center">
          Something went wrong. Try again?
        </p>
      )}
    </form>
  );
}
