"use client";

import { useState } from "react";

type ChainEntry = { day: string; read_count: number; cc_total: string; merkle_hash: string; prev_hash: string };
type VerifyResult = { valid: boolean; entries: number; first_failure: any };
type SnapshotData = { week: string; merkle_root: string; total_reads: number; total_cc: string; assets_count: number; signature: string; signed_by: string; published_at: string; payload?: any };
type SnapshotVerify = { week: string; signature_valid: boolean; merkle_root: string; signed_by: string };

export function VerificationPanel() {
  const [assetId, setAssetId] = useState("");
  const [week, setWeek] = useState("");
  const [chain, setChain] = useState<ChainEntry[] | null>(null);
  const [verifyResult, setVerifyResult] = useState<VerifyResult | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [snapshotVerify, setSnapshotVerify] = useState<SnapshotVerify | null>(null);
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchChain = async () => {
    if (!assetId) return;
    setLoading(true);
    setChain(null); setVerifyResult(null);
    try {
      const r = await fetch(`/api/verification/chain/${assetId}`);
      setChain(await r.json());
    } catch { setChain([]); }
    setLoading(false);
  };

  const verifyChain = async () => {
    if (!assetId) return;
    setLoading(true);
    setVerifyResult(null);
    try {
      const r = await fetch(`/api/verification/recompute/${assetId}`);
      setVerifyResult(await r.json());
    } catch { setVerifyResult({ valid: false, entries: 0, first_failure: "fetch error" }); }
    setLoading(false);
  };

  const fetchSnapshot = async () => {
    setLoading(true);
    setSnapshot(null); setSnapshotVerify(null);
    const w = week || new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 4) + "-W" + String(Math.ceil((new Date().getDate()) / 7)).padStart(2, "0");
    try {
      const r = await fetch(`/api/verification/snapshot/${w}`);
      if (r.ok) setSnapshot(await r.json());
    } catch {}
    setLoading(false);
  };

  const verifySnapshot = async () => {
    if (!snapshot) return;
    setLoading(true);
    try {
      const r = await fetch(`/api/verification/snapshot/${snapshot.week}/verify`);
      setSnapshotVerify(await r.json());
    } catch {}
    setLoading(false);
  };

  const fetchPublicKey = async () => {
    try {
      const r = await fetch("/api/verification/public-key");
      const d = await r.json();
      setPublicKey(d.public_key_hex);
    } catch {}
  };

  return (
    <div className="space-y-8">
      {/* Public Key */}
      <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-3">
        <h2 className="text-lg font-light text-stone-300">Verification Public Key</h2>
        <p className="text-xs text-stone-500">Ed25519 key used to sign weekly snapshots. Use this to independently verify any snapshot.</p>
        {publicKey ? (
          <code className="block text-xs text-amber-300/70 font-mono break-all bg-stone-900/50 p-3 rounded-xl">{publicKey}</code>
        ) : (
          <button onClick={fetchPublicKey} className="text-xs text-amber-300/70 hover:text-amber-300 transition-colors">
            Load public key
          </button>
        )}
      </section>

      {/* Chain Verification */}
      <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
        <h2 className="text-lg font-light text-stone-300">Verify Asset Hash Chain</h2>
        <p className="text-xs text-stone-500">Enter any asset ID to fetch and verify its Merkle hash chain. No login required.</p>
        <div className="flex gap-2">
          <input
            value={assetId}
            onChange={(e) => setAssetId(e.target.value)}
            placeholder="asset ID (e.g. visual-lc-space-0)"
            className="flex-1 px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 focus:outline-none focus:border-amber-500/30"
          />
          <button onClick={fetchChain} disabled={loading || !assetId}
            className="px-4 py-2 rounded-xl bg-stone-800/50 border border-stone-700/30 text-stone-400 hover:text-stone-200 text-sm disabled:opacity-40">
            Fetch
          </button>
          <button onClick={verifyChain} disabled={loading || !assetId}
            className="px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 text-sm disabled:opacity-40">
            Verify
          </button>
        </div>

        {verifyResult && (
          <div className={`rounded-xl border p-4 text-sm ${verifyResult.valid
            ? "border-emerald-800/30 bg-emerald-900/10 text-emerald-300"
            : "border-red-800/30 bg-red-900/10 text-red-300"}`}>
            <span className="font-medium">{verifyResult.valid ? "VALID" : "INVALID"}</span>
            {" — "}{verifyResult.entries} entries verified
            {verifyResult.first_failure && (
              <pre className="mt-2 text-xs opacity-70">{JSON.stringify(verifyResult.first_failure, null, 2)}</pre>
            )}
          </div>
        )}

        {chain && chain.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-stone-400">
              <thead><tr className="text-stone-600">
                <th className="text-left py-1 pr-3">Day</th>
                <th className="text-right pr-3">Reads</th>
                <th className="text-right pr-3">CC</th>
                <th className="text-left font-mono">Hash (first 16)</th>
              </tr></thead>
              <tbody>
                {chain.slice(-20).map((e) => (
                  <tr key={e.day} className="border-t border-stone-800/20">
                    <td className="py-1 pr-3">{e.day}</td>
                    <td className="text-right pr-3">{e.read_count}</td>
                    <td className="text-right pr-3">{e.cc_total}</td>
                    <td className="font-mono text-amber-400/50">{e.merkle_hash.slice(0, 16)}...</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {chain && chain.length === 0 && (
          <p className="text-xs text-stone-600">No chain data found for this asset.</p>
        )}
      </section>

      {/* Snapshot Verification */}
      <section className="rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-4">
        <h2 className="text-lg font-light text-stone-300">Verify Weekly Snapshot</h2>
        <p className="text-xs text-stone-500">Fetch a weekly snapshot and verify its Ed25519 signature.</p>
        <div className="flex gap-2">
          <input
            value={week}
            onChange={(e) => setWeek(e.target.value)}
            placeholder="week (e.g. 2026-W16)"
            className="flex-1 px-3 py-2 bg-stone-900/50 border border-stone-800/40 rounded-xl text-sm text-stone-300 focus:outline-none focus:border-amber-500/30"
          />
          <button onClick={fetchSnapshot} disabled={loading}
            className="px-4 py-2 rounded-xl bg-stone-800/50 border border-stone-700/30 text-stone-400 hover:text-stone-200 text-sm disabled:opacity-40">
            Fetch
          </button>
        </div>

        {snapshot && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2 text-xs text-stone-400">
              <div>Week: <span className="text-stone-300">{snapshot.week}</span></div>
              <div>Assets: <span className="text-stone-300">{snapshot.assets_count}</span></div>
              <div>Total reads: <span className="text-stone-300">{snapshot.total_reads}</span></div>
              <div>Total CC: <span className="text-stone-300">{snapshot.total_cc}</span></div>
            </div>
            <div className="text-xs">
              <span className="text-stone-600">Merkle root: </span>
              <code className="text-amber-400/50 font-mono">{snapshot.merkle_root?.slice(0, 32)}...</code>
            </div>
            <button onClick={verifySnapshot}
              className="px-4 py-2 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 text-sm">
              Verify Signature
            </button>

            {snapshotVerify && (
              <div className={`rounded-xl border p-4 text-sm ${snapshotVerify.signature_valid
                ? "border-emerald-800/30 bg-emerald-900/10 text-emerald-300"
                : "border-red-800/30 bg-red-900/10 text-red-300"}`}>
                Signature: <span className="font-medium">{snapshotVerify.signature_valid ? "VALID" : "INVALID"}</span>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
