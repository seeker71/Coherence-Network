"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";

type Props = {
  initialName: string;
};

type Status = "idle" | "saving" | "saved" | "error";

export function WelcomeForm({ initialName }: Props) {
  const router = useRouter();
  const [name, setName] = useState(initialName);
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) {
      setStatus("error");
      setMessage("Please choose a name.");
      return;
    }

    setStatus("saving");
    setMessage("");

    try {
      const response = await fetch("/session/welcome", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: trimmed }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { contributor_id?: string };
      const contributorId = String(payload.contributor_id || trimmed);
      setStatus("saved");
      setMessage(`Welcome, ${contributorId}.`);
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(String(error));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <label className="block space-y-2">
        <span className="text-sm font-medium">What would you like to be called here?</span>
        <input
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={80}
          autoFocus
          disabled={status === "saving"}
          className="w-full rounded border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder="a name you respond to"
        />
      </label>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={status === "saving" || !name.trim()}>
          {status === "saving" ? "Welcoming..." : "Be welcomed"}
        </Button>
        {status === "saved" && message ? <span className="text-sm text-green-700">{message}</span> : null}
        {status === "error" && message ? <span className="text-sm text-destructive">{message}</span> : null}
      </div>
    </form>
  );
}
