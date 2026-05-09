"use client";

import { useState, useEffect, type ReactNode } from "react";
import { WagmiProvider } from "wagmi";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RainbowKitProvider } from "@rainbow-me/rainbowkit";

import { walletConfig } from "@/lib/wallet-config";

import "@rainbow-me/rainbowkit/styles.css";

const queryClient = new QueryClient();

/**
 * Wallet context provider — wraps wagmi/RainbowKit around children that
 * call wallet hooks. Renders nothing until mounted so wagmi hooks like
 * useConfig never fire without WagmiProvider in the tree (SSR-safe).
 * Wrap only the subtrees that need wallet state, not the whole app.
 */
export default function WalletProvider({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return null;
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
