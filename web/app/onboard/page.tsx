"use client";
/**
 * Onboarding page — Trust-on-First-Use (TOFU) registration
 * Spec 168: identity-driven-onboarding
 *
 * Allows a new contributor to claim a handle and receive a session token
 * with zero friction. No OAuth, no email confirmation required in MVP.
 */
import { useState } from "react";

interface RegisterResult {
  contributor_id: string;
  session_token: string;
  trust_level: string;
  handle: string;
  created: boolean;
  roi_signals: {
    handle_registrations: number;
    verified_count: number;
    verified_ratio: number;
    avg_time_to_verify_days: number | null;
  };
}

export default function OnboardPage() {
  const [handle, setHandle] = useState("");
  const [hintGithub, setHintGithub] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RegisterResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const resp = await fetch("/api/onboarding/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          handle: handle.trim().toLowerCase(),
          hint_github: hintGithub.trim() || undefined,
        }),
      });

      if (resp.status === 409) {
        setError(`Handle "${handle}" is already taken. Please choose another.`);
        return;
      }

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const detail = data?.detail;
        if (Array.isArray(detail)) {
          setError(detail.map((d: { msg?: string }) => d.msg ?? String(d)).join("; "));
        } else {
          setError(String(detail ?? resp.statusText));
        }
        return;
      }

      const data: RegisterResult = await resp.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const copyToken = () => {
    if (result?.session_token) {
      navigator.clipboard.writeText(result.session_token).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold mb-2">Join Coherence Network</h1>
        <p className="text-muted-foreground mb-6">
          Claim your contributor handle instantly — no password, no OAuth required.
          You can upgrade your identity verification later.
        </p>

        {!result ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="handle" className="block text-sm font-medium mb-1">
                Handle <span className="text-red-500">*</span>
              </label>
              <input
                id="handle"
                type="text"
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                placeholder="your-handle"
                pattern="[a-z0-9_\-]{3,40}"
                title="3–40 characters: lowercase letters, numbers, _ or -"
                required
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-muted-foreground mt-1">
                3–40 chars, lowercase letters, numbers, _ or -
              </p>
            </div>

            <div>
              <label htmlFor="github" className="block text-sm font-medium mb-1">
                GitHub username <span className="text-muted-foreground">(optional hint)</span>
              </label>
              <input
                id="github"
                type="text"
                value={hintGithub}
                onChange={(e) => setHintGithub(e.target.value)}
                placeholder="octocat"
                className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !handle.trim()}
              className="w-full bg-blue-600 text-white rounded px-4 py-2 font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? "Registering…" : "Claim handle"}
            </button>
          </form>
        ) : (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded p-4">
              <h2 className="text-lg font-semibold text-green-800 mb-1">
                Welcome, {result.handle}!
              </h2>
              <p className="text-sm text-green-700">
                Your handle is registered. Save your session token below — it&apos;s your
                personal API key.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Session token (save this!)
              </label>
              <div className="flex gap-2">
                <code className="flex-1 bg-gray-100 rounded px-3 py-2 text-xs font-mono break-all">
                  {result.session_token}
                </code>
                <button
                  onClick={copyToken}
                  className="shrink-0 border rounded px-3 py-2 text-sm hover:bg-gray-50 transition-colors"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm">
              <p className="font-medium text-blue-800 mb-1">Trust level: {result.trust_level}</p>
              <p className="text-blue-700">
                Your identity is unverified (TOFU). You can upgrade later via GitHub OAuth
                or Ethereum signature for full verification.
              </p>
            </div>

            <div className="text-xs text-muted-foreground border-t pt-3 space-y-1">
              <p>Contributor ID: <code>{result.contributor_id}</code></p>
              <p>Network registrations: {result.roi_signals.handle_registrations}</p>
              <p>Verified ratio: {(result.roi_signals.verified_ratio * 100).toFixed(1)}%</p>
            </div>

            <a
              href="/contribute"
              className="block w-full text-center bg-gray-900 text-white rounded px-4 py-2 font-medium hover:bg-gray-700 transition-colors"
            >
              Start contributing →
            </a>
          </div>
        )}
      </div>
    </main>
  );
}
