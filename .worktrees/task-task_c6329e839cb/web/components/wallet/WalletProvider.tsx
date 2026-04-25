"use client";

import { useState, useEffect, type ReactNode } from "react";
import { WagmiProvider } from "wagmi";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RainbowKitProvider } from "@rainbow-me/rainbowkit";

import { walletConfig } from "@/lib/wallet-config";

import "@rainbow-me/rainbowkit/styles.css";

const queryClient = new QueryClient();

/**
 * Wallet context provider — wraps the whole app so any page can access
 * wallet state. Children always render (SSR-safe); the RainbowKit overlay
 * activates after hydration.
 */
export default function WalletProvider({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Always render children so SSR works. Wallet UI components
  // use their own mounted checks internally.
  if (!mounted) {
    return <>{children}</>;
  }

  return (
    <WagmiProvider config={walletConfig}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider>
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
