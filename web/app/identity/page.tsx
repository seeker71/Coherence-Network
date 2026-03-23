"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

type Identity = {
  id: string;
  contributor_id: string;
  provider: string;
  provider_id: string;
  display_name: string | null;
  avatar_url: string | null;
  verified: boolean;
  linked_at: string | null;
  metadata_json: string;
};

const PROVIDERS = [
  {
    key: "github",
    label: "GitHub",
    placeholder: "your-username",
    description: "Developer identity on GitHub",
    canOAuth: true,
  },
  {
    key: "ethereum",
    label: "Ethereum",
    placeholder: "0x...",
    description: "Ethereum wallet address",
    canVerify: true,
  },
  {
    key: "bitcoin",
    label: "Bitcoin",
    placeholder: "bc1... or 1... or 3...",
    description: "Bitcoin address for receiving value",
  },
  {
    key: "x",
    label: "X / Twitter",
    placeholder: "@handle",
    description: "Your X handle",
  },
  {
    key: "email",
    label: "Email",
    placeholder: "you@example.com",
    description: "Contact email",
  },
] as const;

function StatusDot({ verified, linked }: { verified: boolean; linked: boolean }) {
  if (!linked) {
    return (
      <span className="inline-flex h-2.5 w-2.5 rounded-full bg-muted-foreground/30" title="Not linked" />
    );
  }
  if (verified) {
    return (
      <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" title="Verified" />
    );
  }
  return (
    <span className="inline-flex h-2.5 w-2.5 rounded-full bg-amber-400" title="Linked (unverified)" />
  );
}

export default function IdentityPage() {
  const [name, setName] = useState("");
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ text: string; type: "ok" | "error" } | null>(null);

  // Load name from localStorage
  useEffect(() => {
    const stored = localStorage.getItem("coherence_contributor_id") || "";
    setName(stored);
    if (stored) {
      loadIdentities(stored);
    }
  }, []);

  const loadIdentities = useCallback(async (contributorId: string) => {
    if (!contributorId) return;
    try {
      const res = await fetch(`${API}/api/identity/${encodeURIComponent(contributorId)}`);
      if (res.ok) {
        const data = await res.json();
        setIdentities(data);
      }
    } catch {
      // Silently fail — identities are optional
    }
  }, []);

  const saveName = useCallback(() => {
    if (!name.trim()) return;
    localStorage.setItem("coherence_contributor_id", name.trim());
    setMessage({ text: "Name saved.", type: "ok" });
    loadIdentities(name.trim());
    setTimeout(() => setMessage(null), 2000);
  }, [name, loadIdentities]);

  const linkProvider = useCallback(
    async (provider: string) => {
      const value = inputs[provider]?.trim();
      if (!value || !name.trim()) return;
      setBusy(provider);
      setMessage(null);
      try {
        const res = await fetch(`${API}/api/identity/link`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contributor_id: name.trim(),
            provider,
            provider_id: value,
            display_name: value,
          }),
        });
        if (res.ok) {
          setMessage({ text: `${provider} linked.`, type: "ok" });
          setInputs((prev) => ({ ...prev, [provider]: "" }));
          await loadIdentities(name.trim());
        } else {
          const err = await res.json().catch(() => ({}));
          setMessage({ text: err.detail || "Link failed.", type: "error" });
        }
      } catch {
        setMessage({ text: "Network error.", type: "error" });
      }
      setBusy(null);
      setTimeout(() => setMessage(null), 3000);
    },
    [inputs, name, loadIdentities],
  );

  const unlinkProvider = useCallback(
    async (provider: string) => {
      if (!name.trim()) return;
      setBusy(provider);
      try {
        const res = await fetch(
          `${API}/api/identity/${encodeURIComponent(name.trim())}/${provider}`,
          { method: "DELETE" },
        );
        if (res.ok) {
          setMessage({ text: `${provider} unlinked.`, type: "ok" });
          await loadIdentities(name.trim());
        }
      } catch {
        setMessage({ text: "Network error.", type: "error" });
      }
      setBusy(null);
      setTimeout(() => setMessage(null), 3000);
    },
    [name, loadIdentities],
  );

  const startGitHubOAuth = useCallback(async () => {
    if (!name.trim()) return;
    setBusy("github-oauth");
    try {
      const res = await fetch(
        `${API}/api/identity/verify/github?contributor_id=${encodeURIComponent(name.trim())}`,
        { method: "POST" },
      );
      const data = await res.json();
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
        return;
      }
      if (data.status === "oauth_not_configured") {
        setMessage({
          text: "GitHub OAuth not configured. Use manual entry below.",
          type: "ok",
        });
      }
    } catch {
      setMessage({ text: "Could not start GitHub OAuth.", type: "error" });
    }
    setBusy(null);
    setTimeout(() => setMessage(null), 4000);
  }, [name]);

  const getLinked = (provider: string): Identity | undefined =>
    identities.find((i) => i.provider === provider);

  return (
    <main className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight mb-2">Your Identity</h1>
        <p className="text-muted-foreground max-w-2xl leading-relaxed">
          Link your accounts to get credit for your contributions across platforms.
          Nothing here is required &mdash; use whatever feels natural.
        </p>
      </header>

      {message && (
        <div
          className={`rounded-xl border px-4 py-3 text-sm ${
            message.type === "ok"
              ? "border-emerald-500/30 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300"
              : "border-red-500/30 bg-red-500/5 text-red-700 dark:text-red-300"
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Your Name */}
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 md:p-6 space-y-4">
        <h2 className="text-lg font-semibold">Your name</h2>
        <p className="text-sm text-muted-foreground">
          This is your contributor identity on the Coherence Network. All linked
          accounts will be associated with this name.
        </p>
        <div className="flex gap-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="your-name"
            className="flex-1 rounded-xl border border-border/50 bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <button
            onClick={saveName}
            disabled={!name.trim()}
            className="rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40 transition-colors"
          >
            Save
          </button>
        </div>
      </section>

      {/* Link Accounts */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Link accounts</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {PROVIDERS.map((p) => {
            const linked = getLinked(p.key);
            return (
              <div
                key={p.key}
                className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-5 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusDot verified={linked?.verified ?? false} linked={!!linked} />
                    <h3 className="font-medium">{p.label}</h3>
                  </div>
                  {linked && (
                    <button
                      onClick={() => unlinkProvider(p.key)}
                      disabled={busy === p.key}
                      className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Unlink
                    </button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">{p.description}</p>
                {linked ? (
                  <div className="rounded-xl bg-muted/30 px-3 py-2 text-sm">
                    <span className="font-mono text-foreground/80">{linked.provider_id}</span>
                    {linked.verified && (
                      <span className="ml-2 inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-600 dark:text-emerald-400">
                        verified
                      </span>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2">
                    {p.key === "github" && (
                      <button
                        onClick={startGitHubOAuth}
                        disabled={!name.trim() || busy === "github-oauth"}
                        className="w-full rounded-xl border border-border/50 bg-muted/20 px-4 py-2 text-sm hover:bg-muted/40 disabled:opacity-40 transition-colors"
                      >
                        {busy === "github-oauth" ? "Redirecting..." : "Connect with GitHub"}
                      </button>
                    )}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={inputs[p.key] || ""}
                        onChange={(e) =>
                          setInputs((prev) => ({ ...prev, [p.key]: e.target.value }))
                        }
                        placeholder={p.placeholder}
                        className="flex-1 rounded-xl border border-border/50 bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                      <button
                        onClick={() => linkProvider(p.key)}
                        disabled={!name.trim() || !inputs[p.key]?.trim() || busy === p.key}
                        className="rounded-xl bg-primary/80 px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary disabled:opacity-40 transition-colors"
                      >
                        {busy === p.key ? "..." : "Link"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* Legend */}
      <footer className="flex items-center gap-6 text-xs text-muted-foreground/60 pt-4">
        <span className="flex items-center gap-1.5">
          <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" /> Verified
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-flex h-2 w-2 rounded-full bg-amber-400" /> Linked
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-flex h-2 w-2 rounded-full bg-muted-foreground/30" /> Not linked
        </span>
      </footer>
    </main>
  );
}
