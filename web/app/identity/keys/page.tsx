"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

/**
 * /identity/keys — mint, list, and revoke personal API keys.
 *
 * This is a power-user / operator surface. It deliberately does not try
 * to own "who is logged in" for the whole web app — there is no session
 * state yet and keys are paste-driven.
 *
 * Two panels:
 *
 * 1. Mint — form producing a `cc_*` key. Raw key displayed ONCE with
 *    copy-to-clipboard. After the page refreshes, the raw key is gone.
 *
 * 2. List / revoke — paste your active key, fetch `/api/auth/keys` with
 *    it, then revoke individual keys with a button. Active key is
 *    remembered in sessionStorage so it survives in-tab navigation but
 *    never touches localStorage or a server.
 */

type KeyListItem = {
  id: string;
  contributor_id: string;
  label: string | null;
  fingerprint: string;
  provider: string | null;
  scopes: string[];
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

type MintResponse = {
  api_key: string;
  contributor_id: string;
  created_at: string;
  scopes: string[];
  label: string | null;
};

const ACTIVE_KEY_STORAGE = "coherence.pulse.active_key";

export default function KeysPage() {
  const api = getApiBase();

  // --- Mint form state -------------------------------------------------
  const [contributorId, setContributorId] = useState("");
  const [label, setLabel] = useState("");
  const [minting, setMinting] = useState(false);
  const [mintError, setMintError] = useState<string | null>(null);
  const [mintedOnce, setMintedOnce] = useState<MintResponse | null>(null);

  // --- Active (listing) key state -------------------------------------
  const [activeKey, setActiveKey] = useState("");
  const [keys, setKeys] = useState<KeyListItem[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [listing, setListing] = useState(false);

  // Restore last active key from sessionStorage on mount.
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(ACTIVE_KEY_STORAGE) ?? "";
      if (stored) setActiveKey(stored);
    } catch {
      // sessionStorage may be unavailable (SSR, privacy mode) — fine.
    }
  }, []);

  const persistActiveKey = useCallback((value: string) => {
    setActiveKey(value);
    try {
      if (value) {
        sessionStorage.setItem(ACTIVE_KEY_STORAGE, value);
      } else {
        sessionStorage.removeItem(ACTIVE_KEY_STORAGE);
      }
    } catch {}
  }, []);

  // --- Mint -----------------------------------------------------------
  const mint = useCallback(async () => {
    if (!contributorId.trim()) {
      setMintError("Contributor id is required");
      return;
    }
    setMinting(true);
    setMintError(null);
    setMintedOnce(null);
    try {
      const res = await fetch(`${api}/api/auth/keys`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          contributor_id: contributorId.trim(),
          provider: "name",
          provider_id: contributorId.trim(),
          label: label.trim() || null,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status} ${res.statusText}: ${text || "mint failed"}`);
      }
      const body = (await res.json()) as MintResponse;
      setMintedOnce(body);
      // Optionally make this the active key so the user can immediately list.
      persistActiveKey(body.api_key);
      setKeys(null); // force a fresh fetch
    } catch (err) {
      setMintError(err instanceof Error ? err.message : String(err));
    } finally {
      setMinting(false);
    }
  }, [api, contributorId, label, persistActiveKey]);

  // --- List -----------------------------------------------------------
  const list = useCallback(async () => {
    if (!activeKey.trim()) {
      setListError("Paste a verified API key to list your keys.");
      return;
    }
    setListing(true);
    setListError(null);
    try {
      const res = await fetch(`${api}/api/auth/keys`, {
        headers: { Authorization: `Bearer ${activeKey.trim()}` },
        cache: "no-store",
      });
      if (res.status === 401) {
        throw new Error("Key was rejected. It may be revoked or not yet minted.");
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status} ${res.statusText}: ${text || "list failed"}`);
      }
      const body = (await res.json()) as { keys: KeyListItem[] };
      setKeys(body.keys);
    } catch (err) {
      setListError(err instanceof Error ? err.message : String(err));
      setKeys(null);
    } finally {
      setListing(false);
    }
  }, [api, activeKey]);

  // --- Revoke ---------------------------------------------------------
  const revoke = useCallback(
    async (keyId: string) => {
      if (!activeKey.trim()) return;
      if (!confirm("Revoke this key? This cannot be undone.")) return;
      try {
        const res = await fetch(`${api}/api/auth/keys/${keyId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${activeKey.trim()}` },
        });
        if (res.status !== 204 && !res.ok) {
          const text = await res.text();
          throw new Error(`${res.status} ${res.statusText}: ${text || "revoke failed"}`);
        }
        // Refresh the list.
        await list();
      } catch (err) {
        setListError(err instanceof Error ? err.message : String(err));
      }
    },
    [api, activeKey, list],
  );

  const copyToClipboard = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Best effort only.
    }
  }, []);

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-4xl mx-auto space-y-8">
      <header className="space-y-2">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <Link href="/identity" className="hover:underline">
            ← Identity
          </Link>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">API Keys</h1>
        <p className="max-w-2xl text-muted-foreground leading-relaxed">
          Personal keys the network uses to attribute your contributions —
          the other half of the nervous system alongside{" "}
          <Link href="/pulse" className="text-emerald-400 hover:underline">
            Pulse
          </Link>
          . A verified key tells the body <em>who is moving</em>. If you
          only want to claim attribution without proving it, send{" "}
          <code className="text-xs px-1.5 py-0.5 rounded bg-muted/60">
            X-Contributor-Id: your-handle
          </code>{" "}
          on any request — the server will mark it as{" "}
          <span className="text-amber-400">claimed</span> rather than{" "}
          <span className="text-emerald-400">verified</span>.
        </p>
      </header>

      {/* --- Mint panel --- */}
      <section className="rounded-2xl border border-border/40 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
        <h2 className="text-lg font-medium">Mint a new key</h2>
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] items-end">
          <label className="space-y-1">
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              Contributor ID
            </span>
            <input
              value={contributorId}
              onChange={(e) => setContributorId(e.target.value)}
              placeholder="alice"
              autoComplete="off"
              className="w-full rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm"
            />
          </label>
          <label className="space-y-1">
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              Label (optional)
            </span>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="laptop"
              autoComplete="off"
              className="w-full rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm"
            />
          </label>
          <button
            onClick={mint}
            disabled={minting}
            className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300 hover:bg-emerald-500/20 disabled:opacity-50"
          >
            {minting ? "Minting…" : "Mint"}
          </button>
        </div>
        {mintError && (
          <p className="text-sm text-rose-400 font-mono">{mintError}</p>
        )}

        {mintedOnce && (
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 space-y-2">
            <p className="text-xs uppercase tracking-wider text-amber-300">
              Save this now — this is the only time you will see it
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 font-mono text-xs bg-background/40 rounded-md px-3 py-2 break-all">
                {mintedOnce.api_key}
              </code>
              <button
                onClick={() => copyToClipboard(mintedOnce.api_key)}
                className="rounded-lg border border-border/40 px-3 py-2 text-xs hover:bg-accent/60"
              >
                Copy
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Contributor: {mintedOnce.contributor_id} · Scopes:{" "}
              {mintedOnce.scopes.join(", ")}
            </p>
          </div>
        )}
      </section>

      {/* --- List + revoke panel --- */}
      <section className="rounded-2xl border border-border/40 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-4">
        <div className="flex items-baseline justify-between flex-wrap gap-2">
          <h2 className="text-lg font-medium">Your active keys</h2>
          <p className="text-xs text-muted-foreground">
            Remembered in this tab only (sessionStorage)
          </p>
        </div>
        <div className="flex gap-2 items-end">
          <label className="flex-1 space-y-1">
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              Paste a verified key to list and revoke
            </span>
            <input
              type="password"
              value={activeKey}
              onChange={(e) => persistActiveKey(e.target.value)}
              placeholder="cc_alice_..."
              autoComplete="off"
              spellCheck={false}
              className="w-full rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm font-mono"
            />
          </label>
          <button
            onClick={list}
            disabled={listing || !activeKey.trim()}
            className="rounded-lg border border-blue-500/40 bg-blue-500/10 px-4 py-2 text-sm text-blue-300 hover:bg-blue-500/20 disabled:opacity-50"
          >
            {listing ? "Listing…" : "List"}
          </button>
        </div>
        {listError && <p className="text-sm text-rose-400 font-mono">{listError}</p>}

        {keys && (
          <div className="space-y-2">
            {keys.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No active keys for this contributor.
              </p>
            )}
            {keys.map((k) => (
              <div
                key={k.id}
                className="flex items-center gap-3 rounded-xl border border-border/30 bg-background/30 px-4 py-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">
                    {k.label || "(no label)"}
                  </p>
                  <p className="text-[11px] text-muted-foreground font-mono">
                    {k.fingerprint} · {k.contributor_id}
                    {k.provider && ` · ${k.provider}`}
                  </p>
                  <p className="text-[11px] text-muted-foreground">
                    Created {new Date(k.created_at).toLocaleString()}
                    {k.last_used_at &&
                      ` · Last used ${new Date(k.last_used_at).toLocaleString()}`}
                  </p>
                </div>
                <button
                  onClick={() => revoke(k.id)}
                  className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/20"
                >
                  Revoke
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* --- Footer nav --- */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Related
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/identity" className="text-purple-400 hover:underline">
            Identity providers
          </Link>
          <Link href="/pulse" className="text-emerald-400 hover:underline">
            Pulse
          </Link>
          <Link href="/vitality" className="text-blue-400 hover:underline">
            Vitality
          </Link>
        </div>
      </nav>
    </main>
  );
}
