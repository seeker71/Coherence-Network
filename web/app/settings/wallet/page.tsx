// web/app/settings/wallet/page.tsx
// Wallet settings — connect, verify, and view linked wallets.
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import WalletProvider from "@/components/wallet/WalletProvider";
import WalletConnect from "@/components/wallet/WalletConnect";
import { getApiBase } from "@/lib/api";

interface WalletRecord {
  id: string;
  contributor_id: string;
  address: string;
  chain: string;
  verified: boolean;
  verified_at: string | null;
  label: string | null;
  created_at: string | null;
}

function ConnectedWallets({ contributorId }: { contributorId: string }) {
  const [wallets, setWallets] = useState<WalletRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`${getApiBase()}/api/wallets/${encodeURIComponent(contributorId)}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: WalletRecord[] = await res.json();
        if (!cancelled) setWallets(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load wallets");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [contributorId]);

  if (loading) return <div className="text-sm text-stone-500">Loading wallets…</div>;
  if (error) return <div className="text-sm text-red-400">Could not load wallets: {error}</div>;
  if (wallets.length === 0) {
    return <div className="text-sm text-stone-500">No wallets linked yet.</div>;
  }

  return (
    <div className="flex flex-col gap-2">
      {wallets.map((w) => (
        <div
          key={w.id}
          className="flex items-center justify-between rounded-md border border-stone-800 bg-stone-950/40 px-4 py-3"
        >
          <div className="flex flex-col">
            <span className="font-mono text-xs text-stone-300">
              {w.address.slice(0, 6)}…{w.address.slice(-4)}
            </span>
            <span className="text-xs text-stone-500">
              {w.chain} · {w.verified ? "verified" : "unverified"}
              {w.label ? ` · ${w.label}` : ""}
            </span>
          </div>
          <span
            className={`inline-block h-2 w-2 rounded-full ${w.verified ? "bg-green-500" : "bg-stone-600"}`}
            aria-label={w.verified ? "verified" : "unverified"}
          />
        </div>
      ))}
    </div>
  );
}

export default function WalletSettingsPage() {
  const [contributorId, setContributorId] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setContributorId(localStorage.getItem("coherence_contributor_id"));
  }, []);

  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/" className="hover:text-amber-400/80 transition-colors">Home</Link>
        <span className="text-stone-700">/</span>
        <Link href="/settings" className="hover:text-amber-400/80 transition-colors">Settings</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Wallet</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-3">Wallet</h1>
      <p className="text-stone-400 mb-8 leading-relaxed">
        Bring your own self-custody wallet. The Network knows your address; the
        keys stay yours. Linkage enables attribution and identity — sending
        and receiving happen in your wallet, not through the platform.
      </p>

      {!mounted ? (
        <div className="text-sm text-stone-500">Loading…</div>
      ) : !contributorId ? (
        <div className="rounded-md border border-amber-900/40 bg-amber-950/20 p-6">
          <h2 className="text-lg font-light text-amber-300 mb-2">Set up your contributor first</h2>
          <p className="text-sm text-stone-400 mb-4">
            A wallet links to a contributor identity. Visit{" "}
            <Link href="/join" className="text-amber-400 hover:underline">
              /join
            </Link>{" "}
            to set up your handle, then return here to link a wallet.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-8">
          <section>
            <h2 className="text-lg font-light text-white mb-4">Connect a wallet</h2>
            <WalletProvider>
              <WalletConnect contributorId={contributorId} />
            </WalletProvider>
          </section>

          <section>
            <h2 className="text-lg font-light text-white mb-4">Linked wallets</h2>
            <ConnectedWallets contributorId={contributorId} />
          </section>
        </div>
      )}

      <section className="mt-12 rounded-md border border-stone-800 bg-stone-950/40 p-6">
        <h2 className="text-lg font-light text-white mb-3">What this enables</h2>
        <ul className="text-sm text-stone-400 space-y-2 leading-relaxed">
          <li>
            <span className="text-stone-200">Identity anchor</span> — your address
            becomes the contributor&apos;s on-chain handle. Attribution flows can
            target it.
          </li>
          <li>
            <span className="text-stone-200">Reverse lookup</span> — others
            sending to your address can find your contributor profile.
          </li>
          <li>
            <span className="text-stone-200">Ownership verified</span> — signing a
            message proves the address is yours, raising the trust level.
          </li>
        </ul>

        <h3 className="text-sm font-light text-stone-300 mt-6 mb-2">Sending and receiving</h3>
        <p className="text-sm text-stone-400 leading-relaxed">
          The platform does not custody your keys or intermediate transactions.
          To send or receive crypto, use your own wallet UI (MetaMask, Rainbow,
          Coinbase Wallet, etc.). The platform only knows your linked address;
          movement of value happens in your wallet, on the chain you choose.
          See{" "}
          <a
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/how-to-use-wallets.md"
            className="text-amber-400 hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            the wallet how-to
          </a>{" "}
          for the full flow.
        </p>
      </section>
    </main>
  );
}
