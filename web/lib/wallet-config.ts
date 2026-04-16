import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import { mainnet, base, polygon } from "wagmi/chains";

export const chains = [mainnet, base, polygon] as const;

export const walletConfig = getDefaultConfig({
  appName: "Coherence Network",
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID ?? "COHERENCE_WALLETCONNECT_PROJECT_ID",
  chains: [mainnet, base, polygon],
  ssr: true,
});
