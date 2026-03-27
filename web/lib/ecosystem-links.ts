export type EcosystemLinkType = "source" | "package" | "docs" | "runtime" | "tooling";
export type EcosystemLinkStatus = "available" | "unavailable";

export type EcosystemLink = {
  id: string;
  name: string;
  purpose: string;
  type: EcosystemLinkType;
  url: string | null;
  status: EcosystemLinkStatus;
};

type EcosystemLinkSeed = Omit<EcosystemLink, "status">;

const ECOSYSTEM_LINK_SEEDS: EcosystemLinkSeed[] = [
  {
    id: "github",
    name: "GitHub Repository",
    purpose: "Contribute code, review issues, and track project history.",
    type: "source",
    url: "https://github.com/seeker71/Coherence-Network",
  },
  {
    id: "npm",
    name: "npm Package",
    purpose: "Install and integrate the CLI package through npm.",
    type: "package",
    url: "https://www.npmjs.com/package/@coherence-network/cc",
  },
  {
    id: "cli-install",
    name: "CLI Installation",
    purpose: "Follow setup steps to run local and remote network commands.",
    type: "tooling",
    url: "https://github.com/seeker71/Coherence-Network#cli-quickstart",
  },
  {
    id: "api-docs",
    name: "API Docs",
    purpose: "Integrate services and inspect endpoint contracts.",
    type: "docs",
    url: "https://api.coherencycoin.com/docs",
  },
  {
    id: "openclaw",
    name: "OpenClaw",
    purpose: "Run agent execution workflows and model orchestration.",
    type: "runtime",
    url: "https://github.com/seeker71/Coherence-Network/tree/main/openclaw",
  },
];

function isValidHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function resolveEcosystemLink(seed: EcosystemLinkSeed): EcosystemLink {
  const trimmed = seed.url?.trim() ?? "";
  if (!trimmed || !isValidHttpUrl(trimmed)) {
    if (process.env.NODE_ENV === "development" && trimmed) {
      // Non-fatal warning for malformed URLs; row remains visible as unavailable.
      console.warn(`[ecosystem-links] Invalid URL for ${seed.id}: ${trimmed}`);
    }
    return {
      ...seed,
      url: null,
      status: "unavailable",
    };
  }

  return {
    ...seed,
    url: trimmed,
    status: "available",
  };
}

export const ECOSYSTEM_LINKS: EcosystemLink[] = ECOSYSTEM_LINK_SEEDS.map(resolveEcosystemLink);
