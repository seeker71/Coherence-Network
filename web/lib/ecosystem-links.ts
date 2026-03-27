/**
 * Canonical typed list of ecosystem destinations.
 * Static config — no backend endpoints required (R7).
 */

export type EcosystemLinkType = "source" | "package" | "docs" | "runtime" | "tooling";
export type EcosystemLinkStatus = "available" | "unavailable";

export interface EcosystemLink {
  id: string;
  name: string;
  purpose: string;
  type: EcosystemLinkType;
  url: string | null;
  status: EcosystemLinkStatus;
}

/** Contributor guidance per link category. */
export const CATEGORY_GUIDANCE: Record<EcosystemLinkType, string> = {
  source: "Contribute code, report issues, and review pull requests.",
  package: "Install and integrate the published package into your project.",
  docs: "Read API references and integration guides.",
  runtime: "Run agents and interact with the live network.",
  tooling: "Set up CLI tools for local development and automation.",
};

export const ECOSYSTEM_LINKS: EcosystemLink[] = [
  {
    id: "github",
    name: "GitHub",
    purpose: "Source code, issues, and pull requests",
    type: "source",
    url: "https://github.com/seeker71/Coherence-Network",
    status: "available",
  },
  {
    id: "npm",
    name: "npm",
    purpose: "Published packages for integration",
    type: "package",
    url: "https://www.npmjs.com/package/coherence-network",
    status: "available",
  },
  {
    id: "cli",
    name: "CLI",
    purpose: "Command-line tools for local development and automation",
    type: "tooling",
    url: "https://github.com/seeker71/Coherence-Network#cli",
    status: "available",
  },
  {
    id: "api-docs",
    name: "API Docs",
    purpose: "Interactive API reference and endpoint explorer",
    type: "docs",
    url: "/api/docs",
    status: "available",
  },
  {
    id: "openclaw",
    name: "OpenClaw",
    purpose: "Run agents and interact with the live Coherence runtime",
    type: "runtime",
    url: null,
    status: "unavailable",
  },
];
