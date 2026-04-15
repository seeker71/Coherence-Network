"use client";

import { useState } from "react";
import Link from "next/link";

type KeypairData = { public_key_hex: string; private_key_hex: string; fingerprint: string; algorithm: string };

export function ContributorSetup() {
  const [step, setStep] = useState(1);
  const [mode, setMode] = useState<"generate" | "bring" | "wallet" | null>(null);
  const [contributorId, setContributorId] = useState("");
  const [keypair, setKeypair] = useState<KeypairData | null>(null);
  const [ownPublicKey, setOwnPublicKey] = useState("");
  const [registered, setRegistered] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [privateSaved, setPrivateSaved] = useState(false);

  const generateKeypair = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/contributors/generate-keypair", { method: "POST" });
      if (!r.ok) throw new Error("Failed to generate keypair");
      const data = await r.json();
      setKeypair(data);
      setStep(2);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error generating keypair");
    } finally {
      setLoading(false);
    }
  };

  const registerKey = async () => {
    if (!contributorId.trim() || !keypair) return;
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(`/api/contributors/${contributorId.trim()}/register-key`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ public_key_hex: keypair.public_key_hex }),
      });
      if (!r.ok) throw new Error("Failed to register");
      const data = await r.json();
      if (data.registered) {
        setRegistered(true);
        // Store contributor ID in localStorage for read sensing
        localStorage.setItem("coherence_contributor_id", contributorId.trim());
        localStorage.setItem("coherence_public_key", keypair.public_key_hex);
        localStorage.setItem("coherence_fingerprint", keypair.fingerprint);
        setStep(4);
      } else {
        throw new Error(data.error || "Registration failed");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error registering");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Step 1: Generate Identity */}
      <section className={`rounded-2xl border p-6 space-y-4 transition-all ${
        step === 1 ? "border-amber-500/30 bg-amber-900/5" : step > 1 ? "border-emerald-800/20 bg-emerald-900/5 opacity-70" : "border-stone-800/40 bg-stone-900/30 opacity-50"
      }`}>
        <div className="flex items-center gap-3">
          <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            step > 1 ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
          }`}>{step > 1 ? "\u2713" : "1"}</span>
          <h2 className="text-lg font-light text-stone-300">Generate Your Identity</h2>
        </div>

        {step === 1 && (
          <>
            <p className="text-sm text-stone-400 leading-relaxed">
              Your identity is an Ed25519 cryptographic keypair. The public key is your address in the network.
              The private key stays with you — it proves you are who you say you are.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => { setMode("generate"); generateKeypair(); }}
                disabled={loading}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40"
              >
                {loading ? "Generating..." : "Generate Keypair"}
              </button>
              <button
                onClick={() => { setMode("bring"); setStep(2); }}
                className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm"
              >
                I have my own key
              </button>
              <button
                onClick={() => { setMode("wallet"); setStep(2); }}
                className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm"
              >
                Use my wallet
              </button>
            </div>
            <p className="text-xs text-stone-600">
              Bring your own Ed25519 key, or connect your existing EVM wallet (MetaMask, Rainbow, etc.)
              for on-chain CC sensing. Your keys never leave your control.
            </p>
          </>
        )}
        {step > 1 && keypair && (
          <p className="text-xs text-emerald-400/60">Keypair generated: {keypair.fingerprint}</p>
        )}
      </section>

      {/* Step 2: Save Private Key */}
      {step >= 2 && (
        <section className={`rounded-2xl border p-6 space-y-4 transition-all ${
          step === 2 ? "border-amber-500/30 bg-amber-900/5" : step > 2 ? "border-emerald-800/20 bg-emerald-900/5 opacity-70" : "border-stone-800/40"
        }`}>
          <div className="flex items-center gap-3">
            <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step > 2 ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
            }`}>{step > 2 ? "\u2713" : "2"}</span>
            <h2 className="text-lg font-light text-stone-300">Save Your Private Key</h2>
          </div>

          {step === 2 && mode === "generate" && keypair && (
            <>
              <div className="rounded-xl border border-red-800/20 bg-red-900/5 p-4 space-y-2">
                <p className="text-xs text-red-300/80 font-medium">This is shown once. Save it now.</p>
                <code className="block text-xs text-stone-300 font-mono break-all bg-stone-900/50 p-3 rounded-lg select-all">
                  {keypair.private_key_hex}
                </code>
              </div>
              <div className="space-y-2">
                <p className="text-xs text-stone-500">Your public key (this is shared):</p>
                <code className="block text-xs text-amber-400/50 font-mono break-all bg-stone-900/30 p-2 rounded-lg">
                  {keypair.public_key_hex}
                </code>
              </div>
              <label className="flex items-center gap-2 text-sm text-stone-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={privateSaved}
                  onChange={(e) => setPrivateSaved(e.target.checked)}
                  className="rounded border-stone-700"
                />
                I have saved my private key somewhere safe
              </label>
              <button
                onClick={() => setStep(3)}
                disabled={!privateSaved}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </>
          )}
          {step === 2 && mode === "wallet" && (
            <>
              <p className="text-sm text-stone-400">
                Connect your EVM wallet. Your wallet address becomes your contributor identity.
                CC earned on-chain settles directly to this address. Full self-custody — we never hold your keys.
              </p>
              <input
                value={ownPublicKey}
                onChange={(e) => setOwnPublicKey(e.target.value.replace(/\s/g, ""))}
                placeholder="0x... (your wallet address)"
                className="w-full px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 font-mono focus:outline-none focus:border-amber-500/30"
              />
              <div className="text-xs text-stone-600 space-y-1">
                <p>Paste your wallet address, or connect via WalletConnect (coming soon).</p>
                <p>This address will be used for Story Protocol IP registration, x402 micropayments, and USDC settlement.</p>
              </div>
              <button
                onClick={() => {
                  const addr = ownPublicKey.startsWith("0x") ? ownPublicKey : `0x${ownPublicKey}`;
                  setKeypair({ public_key_hex: addr, private_key_hex: "", fingerprint: addr.slice(2, 10), algorithm: "EVM-wallet" });
                  setStep(3);
                }}
                disabled={ownPublicKey.length < 10}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Use this wallet
              </button>
            </>
          )}
          {step === 2 && mode === "bring" && (
            <>
              <p className="text-sm text-stone-400">
                Paste your Ed25519 public key (hex encoded, 64 characters).
                Your private key never touches this server.
              </p>
              <input
                value={ownPublicKey}
                onChange={(e) => setOwnPublicKey(e.target.value.replace(/\s/g, ""))}
                placeholder="Ed25519 public key (64 hex characters)"
                className="w-full px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 font-mono focus:outline-none focus:border-amber-500/30"
              />
              <button
                onClick={() => {
                  setKeypair({ public_key_hex: ownPublicKey, private_key_hex: "", fingerprint: ownPublicKey.slice(0, 16), algorithm: "Ed25519-external" });
                  setStep(3);
                }}
                disabled={ownPublicKey.length < 32}
                className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Use this key
              </button>
            </>
          )}
        </section>
      )}

      {/* Step 3: Choose Name */}
      {step >= 3 && (
        <section className={`rounded-2xl border p-6 space-y-4 transition-all ${
          step === 3 ? "border-amber-500/30 bg-amber-900/5" : step > 3 ? "border-emerald-800/20 bg-emerald-900/5 opacity-70" : "border-stone-800/40"
        }`}>
          <div className="flex items-center gap-3">
            <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step > 3 ? "bg-emerald-500/20 text-emerald-300" : "bg-amber-500/20 text-amber-300"
            }`}>{step > 3 ? "\u2713" : "3"}</span>
            <h2 className="text-lg font-light text-stone-300">Choose Your Contributor Name</h2>
          </div>

          {step === 3 && (
            <>
              <p className="text-sm text-stone-400">This is how you appear in the network. Lowercase, hyphens allowed.</p>
              <div className="flex gap-2">
                <input
                  value={contributorId}
                  onChange={(e) => setContributorId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))}
                  placeholder="your-name"
                  className="flex-1 px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 focus:outline-none focus:border-amber-500/30"
                />
                <button
                  onClick={registerKey}
                  disabled={loading || !contributorId.trim()}
                  className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium disabled:opacity-40"
                >
                  {loading ? "Registering..." : "Register"}
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {/* Step 4: Done */}
      {step >= 4 && registered && (
        <section className="rounded-2xl border border-emerald-800/20 bg-emerald-900/5 p-6 space-y-4">
          <div className="flex items-center gap-3">
            <span className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium bg-emerald-500/20 text-emerald-300">{"\u2713"}</span>
            <h2 className="text-lg font-light text-emerald-300">You Are In The Network</h2>
          </div>

          <div className="space-y-2 text-sm text-stone-400">
            <div>Contributor: <span className="text-stone-300 font-medium">{contributorId}</span></div>
            <div>Fingerprint: <span className="text-amber-400/60 font-mono">{keypair?.fingerprint}</span></div>
            <div>Public key: <span className="text-amber-400/40 font-mono text-xs">{keypair?.public_key_hex.slice(0, 24)}...</span></div>
          </div>

          <div className="space-y-3 pt-4 border-t border-stone-800/20">
            <p className="text-sm text-stone-300 font-medium">What happens now:</p>
            <div className="space-y-2 text-sm text-stone-400">
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>Your reads on this site are now sensed with your contributor ID — building your frequency profile</span>
              </div>
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>NFT assets will suggest you identify yourself for sensing — because every sensed view flows CC to the creator</span>
              </div>
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>When you contribute (an article, a blueprint, a hosted node), you start generating CC</span>
              </div>
              <div className="flex gap-2">
                <span className="text-amber-400/50 shrink-0">{"\u2726"}</span>
                <span>Your reading history shapes where your CC flows — to the creators who resonated with you</span>
              </div>
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <Link href="/vision/economy"
              className="px-5 py-2.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all text-sm font-medium">
              Explore the Economy
            </Link>
            <Link href="/vision"
              className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm">
              Browse Concepts
            </Link>
            <Link href="/verify"
              className="px-5 py-2.5 rounded-xl border border-stone-800/40 text-stone-500 hover:text-stone-300 transition-all text-sm">
              Verify the Math
            </Link>
          </div>

          <p className="text-xs text-stone-600 pt-2">
            Your public key is verifiable at: <code className="text-amber-400/40">/api/contributors/{contributorId}/public-key</code>
          </p>
        </section>
      )}

      {error && (
        <div className="rounded-xl border border-red-800/30 bg-red-900/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}
    </div>
  );
}
