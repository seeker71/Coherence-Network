"use client";

import { useState } from "react";
import { getApiBase } from "@/lib/api";

const API = getApiBase();

type RegisterResponse = {
  contributor_id: string;
  session_token: string;
  trust_level: "tofu" | "verified";
  handle: string;
  created: boolean;
  roi_signals: {
    handle_registrations: number;
    verified_count: number;
    verified_ratio: number;
    avg_time_to_verify_days: number | null;
    spec_ref: string;
  };
};

export default function OnboardingPage() {
  const [handle, setHandle] = useState("");
  const [email, setEmail] = useState("");
  const [hintGithub, setHintGithub] = useState("");
  const [hintWallet, setHintWallet] = useState("");
  const [session, setSession] = useState<RegisterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const payload: Record<string, string> = { handle };
      if (email) payload.email = email;
      if (hintGithub) payload.hint_github = hintGithub;
      if (hintWallet) payload.hint_wallet = hintWallet;
      const resp = await fetch(API + "/api/onboarding/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (resp.status === 409) { setError("Handle taken. Try another."); return; }
      if (!resp.ok) {
        const b = await resp.json().catch(() => ({}));
        setError(b?.detail ?? "Registration failed (" + resp.status + ")");
        return;
      }
      setSession(await resp.json());
    } catch (err) {
      setError("Network error: " + err);
    } finally {
      setBusy(false);
    }
  }

  if (!session) {
    return (
      <main className="max-w-md mx-auto mt-16 px-4">
        <h1 className="text-2xl font-bold mb-2">Join Coherence Network</h1>
        <p className="text-sm text-muted-foreground mb-6">
          Claim your handle instantly -- no password or verification required.
          Verify identity later via GitHub or wallet (Spec 169).
        </p>
        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="handle">
              Handle <span className="text-red-500">*</span>
            </label>
            <input id="handle" type="text" value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="your-handle" required
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none"
            />
            <p className="text-xs text-muted-foreground mt-1">3-40 chars, a-z 0-9 _ -</p>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="email">
              Email <span className="text-muted-foreground">(optional)</span>
            </label>
            <input id="email" type="email" value={email}
              onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com"
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              GitHub username <span className="text-muted-foreground">(optional)</span>
            </label>
            <input type="text" value={hintGithub}
              onChange={(e) => setHintGithub(e.target.value)} placeholder="octocat"
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">
              Wallet address <span className="text-muted-foreground">(optional)</span>
            </label>
            <input type="text" value={hintWallet}
              onChange={(e) => setHintWallet(e.target.value)} placeholder="0x..."
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none"
            />
          </div>
          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}
          <button type="submit" disabled={busy || !handle.trim()}
            className="w-full bg-primary text-primary-foreground rounded px-4 py-2 text-sm font-medium disabled:opacity-50">
            {busy ? "Registering..." : "Claim Handle"}
          </button>
        </form>
        <p className="text-xs text-muted-foreground mt-6">
          Trust-on-First-Use (TOFU) -- Spec 168 ·{" "}
          <a href="/contribute" className="underline">Contribute</a>
        </p>
      </main>
    );
  }

  return (
    <main className="max-w-md mx-auto mt-16 px-4 space-y-6">
      <div className="border rounded-lg p-4 bg-green-50 border-green-200">
        <h2 className="text-lg font-bold text-green-800 mb-1">Welcome, {session.handle}!</h2>
        <p className="text-sm text-green-700 mb-3">
          {session.created ? "Handle registered." : "Session reissued."}
        </p>
        <dl className="text-xs space-y-1">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Contributor ID</dt>
            <dd className="font-mono truncate max-w-[220px]">{session.contributor_id}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Trust level</dt>
            <dd><span className="px-1.5 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">{session.trust_level}</span></dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Token</dt>
            <dd className="font-mono text-muted-foreground">{session.session_token.slice(0, 12)}...</dd>
          </div>
        </dl>
      </div>
      <div className="border rounded p-3 text-xs text-muted-foreground">
        {session.roi_signals.handle_registrations} registered · {(session.roi_signals.verified_ratio * 100).toFixed(0)}% verified
      </div>
      <p className="text-xs text-muted-foreground">
        Verify via <a href="/identity" className="underline">Identity settings</a>. OAuth: Spec 169.
      </p>
      <div className="text-xs flex gap-4 text-muted-foreground">
        <a href="/contribute" className="underline">Contribute</a>
        <a href="/contributors" className="underline">Contributors</a>
        <a href="/identity" className="underline">Identity</a>
      </div>
    </main>
  );
}
