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

type UpgradeResponse = {
  contributor_id: string;
  trust_level: "tofu" | "verified";
  provider: string;
  provider_id: string;
  roi_signals: Record<string, unknown>;
};

export default function OnboardingPage() {
  const [handle, setHandle] = useState("");
  const [email, setEmail] = useState("");
  const [hintGithub, setHintGithub] = useState("");
  const [hintWallet, setHintWallet] = useState("");

  const [session, setSession] = useState<RegisterResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Upgrade state
  const [upgradeProvider, setUpgradeProvider] = useState("github");
  const [upgradeProviderId, setUpgradeProviderId] = useState("");
  const [upgradeResult, setUpgradeResult] = useState<UpgradeResponse | null>(null);
  const [upgradeError, setUpgradeError] = useState<string | null>(null);
  const [upgradeBusy, setUpgradeBusy] = useState(false);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const payload: Record<string, string> = { handle };
      if (email) payload.email = email;
      if (hintGithub) payload.hint_github = hintGithub;
      if (hintWallet) payload.hint_wallet = hintWallet;

      const resp = await fetch(`${API}/api/onboarding/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (resp.status === 409) {
        setError("That handle is already taken. Try another.");
        return;
      }
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setError(body?.detail ?? `Registration failed (${resp.status})`);
        return;
      }

      const data: RegisterResponse = await resp.json();
      setSession(data);
    } catch (err) {
      setError(`Network error: ${err}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleUpgrade(e: React.FormEvent) {
    e.preventDefault();
    if (!session) return;
    setUpgradeError(null);
    setUpgradeBusy(true);
    try {
      const resp = await fetch(`${API}/api/onboarding/upgrade`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contributor_id: session.contributor_id,
          provider: upgradeProvider,
          provider_id: upgradeProviderId,
        }),
      });

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setUpgradeError(body?.detail ?? `Upgrade failed (${resp.status})`);
        return;
      }

      const data: UpgradeResponse = await resp.json();
      setUpgradeResult(data);
      // Reflect updated trust level in session
      setSession((prev) => prev ? { ...prev, trust_level: data.trust_level } : prev);
    } catch (err) {
      setUpgradeError(`Network error: ${err}`);
    } finally {
      setUpgradeBusy(false);
    }
  }

  // ---- Pre-registration form ----
  if (!session) {
    return (
      <main className="max-w-md mx-auto mt-16 px-4">
        <h1 className="text-2xl font-bold mb-2">Join Coherence Network</h1>
        <p className="text-sm text-muted-foreground mb-6">
          Claim your handle instantly — no password or email verification required.
          You can verify your identity via GitHub or wallet later.
        </p>

        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="handle">
              Handle <span className="text-red-500">*</span>
            </label>
            <input
              id="handle"
              type="text"
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
              placeholder="your-handle"
              minLength={3}
              maxLength={40}
              required
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <p className="text-xs text-muted-foreground mt-1">
              3–40 chars, lowercase letters, numbers, _ or -
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="email">
              Email <span className="text-muted-foreground">(optional)</span>
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="hint_github">
              GitHub username <span className="text-muted-foreground">(optional hint)</span>
            </label>
            <input
              id="hint_github"
              type="text"
              value={hintGithub}
              onChange={(e) => setHintGithub(e.target.value)}
              placeholder="octocat"
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" htmlFor="hint_wallet">
              Wallet address <span className="text-muted-foreground">(optional hint)</span>
            </label>
            <input
              id="hint_wallet"
              type="text"
              value={hintWallet}
              onChange={(e) => setHintWallet(e.target.value)}
              placeholder="0x..."
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !handle.trim()}
            className="w-full bg-primary text-primary-foreground rounded px-4 py-2 text-sm font-medium disabled:opacity-50"
          >
            {busy ? "Registering…" : "Claim Handle"}
          </button>
        </form>

        <p className="text-xs text-muted-foreground mt-6">
          Trust-on-First-Use (TOFU) — no verification needed to start.
          Spec 168 · <a href="/contribute" className="underline">Contribute</a>
        </p>
      </main>
    );
  }

  // ---- Post-registration: session card + upgrade form ----
  return (
    <main className="max-w-md mx-auto mt-16 px-4 space-y-6">
      <div className="border rounded-lg p-4 bg-green-50 border-green-200">
        <h2 className="text-lg font-bold text-green-800 mb-1">
          Welcome, {session.handle}!
        </h2>
        <p className="text-sm text-green-700 mb-3">
          {session.created
            ? "Your handle has been registered."
            : "Session reissued for your handle."}
        </p>
        <dl className="text-xs space-y-1">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Contributor ID</dt>
            <dd className="font-mono truncate max-w-[220px]">{session.contributor_id}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Trust level</dt>
            <dd>
              <span
                className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                  session.trust_level === "verified"
                    ? "bg-green-100 text-green-800"
                    : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {session.trust_level}
              </span>
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Session token</dt>
            <dd className="font-mono truncate max-w-[220px] text-muted-foreground">
              {session.session_token.slice(0, 12)}…
            </dd>
          </div>
        </dl>
      </div>

      {/* ROI signals */}
      <div className="border rounded p-3 text-xs text-muted-foreground">
        <span className="font-medium">Network stats</span> ·{" "}
        {session.roi_signals.handle_registrations} registered ·{" "}
        {(session.roi_signals.verified_ratio * 100).toFixed(0)}% verified
        {session.roi_signals.avg_time_to_verify_days != null &&
          ` · avg ${session.roi_signals.avg_time_to_verify_days}d to verify`}
      </div>

      {/* Upgrade form */}
      {session.trust_level === "tofu" && !upgradeResult && (
        <div className="border rounded-lg p-4">
          <h3 className="font-semibold text-sm mb-1">Verify your identity</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Optional: link a GitHub username or Ethereum address to upgrade to{" "}
            <strong>verified</strong> status.
          </p>

          <form onSubmit={handleUpgrade} className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1">Provider</label>
              <select
                value={upgradeProvider}
                onChange={(e) => setUpgradeProvider(e.target.value)}
                className="w-full border rounded px-2 py-1.5 text-xs"
              >
                <option value="github">GitHub</option>
                <option value="ethereum">Ethereum wallet</option>
                <option value="email">Email</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">
                {upgradeProvider === "github"
                  ? "GitHub username"
                  : upgradeProvider === "ethereum"
                  ? "Wallet address"
                  : "Email address"}
              </label>
              <input
                type="text"
                value={upgradeProviderId}
                onChange={(e) => setUpgradeProviderId(e.target.value)}
                required
                className="w-full border rounded px-2 py-1.5 text-xs"
              />
            </div>

            {upgradeError && (
              <p className="text-xs text-red-600">{upgradeError}</p>
            )}

            <button
              type="submit"
              disabled={upgradeBusy || !upgradeProviderId.trim()}
              className="w-full bg-primary text-primary-foreground rounded px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            >
              {upgradeBusy ? "Upgrading…" : "Upgrade to Verified"}
            </button>
          </form>

          <p className="text-xs text-muted-foreground mt-2">
            Note: Full OAuth redirect flow planned for Spec 169. This records
            your claimed identity with verified status immediately.
          </p>
        </div>
      )}

      {upgradeResult && (
        <div className="border rounded-lg p-3 bg-blue-50 border-blue-200 text-sm">
          <span className="font-semibold text-blue-800">Identity verified</span> via{" "}
          {upgradeResult.provider}: {upgradeResult.provider_id}
        </div>
      )}

      <div className="text-xs text-muted-foreground flex gap-4">
        <a href="/contribute" className="underline">Contribute</a>
        <a href="/contributors" className="underline">Contributors</a>
        <a href="/identity" className="underline">Identity settings</a>
      </div>
    </main>
  );
}
