"use client";

import { useCallback, useState } from "react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount, useSignMessage } from "wagmi";

import { getApiBase } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface WalletConnectProps {
  contributorId?: string;
}

function getContributorId(prop?: string): string | null {
  if (prop) return prop;
  if (typeof window === "undefined") return null;
  return localStorage.getItem("coherence_contributor_id");
}

export default function WalletConnect({ contributorId }: WalletConnectProps) {
  const { address, chain, isConnected } = useAccount();
  const { signMessageAsync } = useSignMessage();
  const [registering, setRegistering] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const registerWallet = useCallback(async () => {
    if (!address || !chain) return;
    const cid = getContributorId(contributorId);
    if (!cid) {
      setError("Contributor ID is required. Set it in your profile first.");
      return;
    }
    setRegistering(true);
    setError(null);
    try {
      const res = await fetch(`${getApiBase()}/api/wallets/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contributor_id: cid,
          address,
          chain: chain.name,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        setError(`Registration returned ${res.status}: ${body}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register wallet");
    } finally {
      setRegistering(false);
    }
  }, [address, chain, contributorId]);

  const verifyWallet = useCallback(async () => {
    if (!address) return;
    setVerifying(true);
    setError(null);
    try {
      const message = `Verify wallet ownership for Coherence Network.\nAddress: ${address}\nTimestamp: ${new Date().toISOString()}`;
      const signature = await signMessageAsync({ message });
      const cid = getContributorId(contributorId);
      const res = await fetch(`${getApiBase()}/api/wallets/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contributor_id: cid, address, message, signature }),
      });
      if (!res.ok) {
        const body = await res.text();
        setError(`Verification returned ${res.status}: ${body}`);
      } else {
        setVerified(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setVerifying(false);
    }
  }, [address, signMessageAsync]);

  return (
    <div className="flex flex-col gap-4">
      <ConnectButton />

      {isConnected && address && (
        <div className="flex flex-col gap-3 rounded-xl border border-border/50 bg-card p-4">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
            <span className="font-mono text-xs">
              {address.slice(0, 6)}...{address.slice(-4)}
            </span>
            {chain && (
              <span className="ml-auto rounded-md bg-muted px-2 py-0.5 text-xs">
                {chain.name}
              </span>
            )}
          </div>

          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={registerWallet}
              disabled={registering}
            >
              {registering ? "Registering..." : "Register Wallet"}
            </Button>

            <Button
              size="sm"
              variant={verified ? "secondary" : "default"}
              onClick={verifyWallet}
              disabled={verifying || verified}
            >
              {verified
                ? "Verified"
                : verifying
                  ? "Signing..."
                  : "Verify Ownership"}
            </Button>
          </div>

          {error && (
            <p className="text-xs text-destructive">{error}</p>
          )}
        </div>
      )}
    </div>
  );
}
