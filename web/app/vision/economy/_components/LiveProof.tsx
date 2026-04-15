"use client";

import { useEffect, useState } from "react";

type ChainEntry = { day: string; read_count: number; cc_total: string; merkle_hash: string };
type ProfileData = { entity_id: string; dimensions: number; magnitude: number; hash: string; top: { dimension: string; strength: number }[] };
type SnapshotVerify = { signature_valid: boolean; merkle_root: string; signed_by: string };

export function LiveProof() {
  const [publicKey, setPublicKey] = useState<string>("");
  const [chain, setChain] = useState<ChainEntry[]>([]);
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [snapshotVerify, setSnapshotVerify] = useState<SnapshotVerify | null>(null);
  const [loading, setLoading] = useState(true);
  const [conceptId] = useState("lc-pulse"); // Most-read concept for demo

  useEffect(() => {
    async function loadProof() {
      try {
        const [keyRes, chainRes, profileRes] = await Promise.all([
          fetch("/api/verification/public-key"),
          fetch(`/api/verification/chain/${conceptId}`),
          fetch(`/api/profile/${conceptId}`),
        ]);

        if (keyRes.ok) {
          const k = await keyRes.json();
          setPublicKey(k.public_key_hex || "");
        }
        if (chainRes.ok) {
          const c = await chainRes.json();
          setChain(Array.isArray(c) ? c.slice(-7) : []);
        }
        if (profileRes.ok) {
          setProfile(await profileRes.json());
        }

        // Try to verify latest snapshot
        const today = new Date();
        const week = `${today.getFullYear()}-W${String(Math.ceil(((today.getTime() - new Date(today.getFullYear(), 0, 1).getTime()) / 86400000 + new Date(today.getFullYear(), 0, 1).getDay() + 1) / 7)).padStart(2, "0")}`;
        const snapRes = await fetch(`/api/verification/snapshot/${week}/verify`);
        if (snapRes.ok) {
          setSnapshotVerify(await snapRes.json());
        }
      } catch {
        // API may not be running — that's fine for static render
      } finally {
        setLoading(false);
      }
    }
    loadProof();
  }, [conceptId]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-8 text-center">
        <div className="text-stone-500 text-sm">Loading live verification data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-light text-stone-300 pt-8 pb-2">Live Proof</h2>
      <p className="text-base text-stone-400 leading-relaxed">
        This is not a mockup. These are live API calls to the verification endpoints — no login, no API key.
        Every number below is recomputable by anyone from the public data.
      </p>

      {/* Verification Public Key */}
      <section className="rounded-2xl border border-amber-800/20 bg-amber-900/5 p-6 space-y-3">
        <h3 className="text-sm font-medium text-amber-400/70 uppercase tracking-wider">Ed25519 Verification Key</h3>
        <p className="text-xs text-stone-500">This key signs every weekly snapshot. Copy it and verify independently.</p>
        {publicKey ? (
          <code className="block text-xs text-amber-300/60 font-mono break-all bg-stone-900/50 p-3 rounded-xl">
            {publicKey}
          </code>
        ) : (
          <p className="text-xs text-stone-600 italic">Key not available (API may not be running)</p>
        )}
        <p className="text-xs text-stone-600">
          Endpoint: <code className="text-amber-400/40">GET /api/verification/public-key</code>
        </p>
      </section>

      {/* Hash Chain */}
      <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-3">
        <h3 className="text-sm font-medium text-stone-500 uppercase tracking-wider">Hash Chain: {conceptId}</h3>
        <p className="text-xs text-stone-500">
          Each day chains to the previous. Tamper with any entry and the chain breaks.
        </p>
        {chain.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-stone-400">
              <thead>
                <tr className="text-stone-600 border-b border-stone-800/30">
                  <th className="text-left py-2 pr-3">Day</th>
                  <th className="text-right pr-3">Reads</th>
                  <th className="text-right pr-3">CC</th>
                  <th className="text-left font-mono">Hash</th>
                </tr>
              </thead>
              <tbody>
                {chain.map((e, i) => (
                  <tr key={e.day} className="border-t border-stone-800/10">
                    <td className="py-2 pr-3">{e.day}</td>
                    <td className="text-right pr-3 text-stone-300">{e.read_count}</td>
                    <td className="text-right pr-3">{e.cc_total}</td>
                    <td className="font-mono text-amber-400/40">
                      {e.merkle_hash.slice(0, 12)}...
                      {i > 0 && <span className="text-stone-700 ml-1">←chain</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-stone-600 italic">No chain data yet (reads are being tracked)</p>
        )}
        <p className="text-xs text-stone-600">
          Endpoint: <code className="text-amber-400/40">GET /api/verification/chain/{conceptId}</code>
        </p>
      </section>

      {/* Snapshot Verification */}
      {snapshotVerify && (
        <section className={`rounded-2xl border p-6 space-y-3 ${
          snapshotVerify.signature_valid
            ? "border-emerald-800/20 bg-emerald-900/5"
            : "border-red-800/20 bg-red-900/5"
        }`}>
          <h3 className="text-sm font-medium uppercase tracking-wider text-emerald-400/70">
            Weekly Snapshot Signature: {snapshotVerify.signature_valid ? "VALID" : "INVALID"}
          </h3>
          <div className="text-xs text-stone-400 space-y-1">
            <div>Merkle root: <code className="text-amber-400/40 font-mono">{snapshotVerify.merkle_root?.slice(0, 24)}...</code></div>
            <div>Signed by: <code className="text-amber-400/40 font-mono">{snapshotVerify.signed_by?.slice(0, 24)}...</code></div>
          </div>
          <p className="text-xs text-stone-600">
            Endpoint: <code className="text-amber-400/40">GET /api/verification/snapshot/{"{"}<em>week</em>{"}"}/verify</code>
          </p>
        </section>
      )}

      {/* Frequency Profile */}
      {profile && (
        <section className="rounded-2xl border border-violet-800/20 bg-violet-900/5 p-6 space-y-3">
          <h3 className="text-sm font-medium text-violet-400/70 uppercase tracking-wider">
            Frequency Profile: {profile.entity_id}
          </h3>
          <div className="text-xs text-stone-400 space-y-1">
            <div>Dimensions: <span className="text-stone-300">{profile.dimensions}</span></div>
            <div>Magnitude: <span className="text-stone-300">{profile.magnitude}</span></div>
            <div>Hash: <code className="text-amber-400/40 font-mono">{profile.hash?.slice(0, 24)}...</code></div>
          </div>
          <div className="flex flex-wrap gap-2 pt-2">
            {profile.top?.slice(0, 8).map((d) => (
              <span key={d.dimension} className="text-xs px-2 py-1 rounded-full bg-violet-900/20 border border-violet-800/20 text-violet-300/70">
                {d.dimension.replace(/^_/, "").replace(":", " ")} <span className="text-violet-400/40">{d.strength}</span>
              </span>
            ))}
          </div>
          <p className="text-xs text-stone-600">
            Endpoint: <code className="text-amber-400/40">GET /api/profile/{profile.entity_id}</code>
          </p>
        </section>
      )}

      {/* How to verify yourself */}
      <section className="rounded-2xl border border-teal-800/20 bg-teal-900/5 p-6 space-y-4">
        <h3 className="text-sm font-medium text-teal-400/70 uppercase tracking-wider">Verify It Yourself</h3>
        <div className="space-y-3 text-sm text-stone-400">
          <div className="flex gap-3">
            <span className="text-teal-400/50 shrink-0">1.</span>
            <div>
              <strong className="text-stone-300">Get the public key</strong>
              <code className="block mt-1 text-xs text-amber-400/40 font-mono bg-stone-900/50 p-2 rounded-lg">
                curl https://api.coherencycoin.com/api/verification/public-key
              </code>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="text-teal-400/50 shrink-0">2.</span>
            <div>
              <strong className="text-stone-300">Fetch any asset's hash chain</strong>
              <code className="block mt-1 text-xs text-amber-400/40 font-mono bg-stone-900/50 p-2 rounded-lg">
                curl https://api.coherencycoin.com/api/verification/chain/lc-pulse
              </code>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="text-teal-400/50 shrink-0">3.</span>
            <div>
              <strong className="text-stone-300">Recompute and verify</strong>
              <code className="block mt-1 text-xs text-amber-400/40 font-mono bg-stone-900/50 p-2 rounded-lg">
                curl https://api.coherencycoin.com/api/verification/recompute/lc-pulse
              </code>
              <p className="text-xs text-stone-500 mt-1">Returns <code>{`{"valid": true}`}</code> — recomputed from raw data, not from stored hashes.</p>
            </div>
          </div>
          <div className="flex gap-3">
            <span className="text-teal-400/50 shrink-0">4.</span>
            <div>
              <strong className="text-stone-300">Verify the weekly snapshot signature</strong>
              <code className="block mt-1 text-xs text-amber-400/40 font-mono bg-stone-900/50 p-2 rounded-lg">
                curl https://api.coherencycoin.com/api/verification/snapshot/2026-W16/verify
              </code>
            </div>
          </div>
        </div>
        <p className="text-xs text-stone-500 pt-2 border-t border-stone-800/20">
          No API key. No login. No permission. The math is the proof.
        </p>
      </section>
    </div>
  );
}
