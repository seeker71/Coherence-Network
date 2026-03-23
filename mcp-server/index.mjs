#!/usr/bin/env node

/**
 * Coherence Network MCP Server
 *
 * Exposes the Coherence Network API as typed MCP tools that any
 * MCP-compatible AI agent (Claude, Cursor, Windsurf, etc.) can invoke.
 *
 * Usage:
 *   npx coherence-mcp-server
 *   COHERENCE_API_URL=http://localhost:8000 npx coherence-mcp-server
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const API_BASE = process.env.COHERENCE_API_URL || "https://api.coherencycoin.com";
const API_KEY = process.env.COHERENCE_API_KEY || "";

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function apiGet(path, params) {
  const url = new URL(path, API_BASE);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null) url.searchParams.set(k, String(v));
    }
  }
  const res = await fetch(url.toString(), {
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) return { error: `${res.status} ${res.statusText}` };
  return await res.json();
}

async function apiPost(path, body) {
  const headers = { "Content-Type": "application/json" };
  if (API_KEY) headers["X-API-Key"] = API_KEY;
  const res = await fetch(new URL(path, API_BASE).toString(), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(15_000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return { error: err.detail || `${res.status} ${res.statusText}` };
  }
  return await res.json();
}

// ---------------------------------------------------------------------------
// Tool definitions
// ---------------------------------------------------------------------------

const TOOLS = [
  // Ideas
  {
    name: "coherence_list_ideas",
    description: "Browse the idea portfolio ranked by ROI and free-energy score. Returns ideas with scores, manifestation status, and selection weights.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Max ideas to return (default 20)", default: 20 },
        search: { type: "string", description: "Search keyword to filter ideas" },
      },
    },
  },
  {
    name: "coherence_get_idea",
    description: "Get full details for a single idea including scores, open questions, value gap, and linked tasks.",
    inputSchema: {
      type: "object",
      properties: {
        idea_id: { type: "string", description: "The idea ID" },
      },
      required: ["idea_id"],
    },
  },
  {
    name: "coherence_idea_progress",
    description: "Get progress for an idea: stage, tasks by phase, CC staked/spent, contributors.",
    inputSchema: {
      type: "object",
      properties: { idea_id: { type: "string" } },
      required: ["idea_id"],
    },
  },
  {
    name: "coherence_select_idea",
    description: "Let the portfolio engine select the next highest-ROI idea to work on. Temperature controls exploration vs exploitation.",
    inputSchema: {
      type: "object",
      properties: {
        temperature: { type: "number", description: "0=deterministic (highest ROI), >1=explore (default 0.5)", default: 0.5 },
      },
    },
  },
  {
    name: "coherence_showcase",
    description: "List validated, shipped ideas that have proven their value.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "coherence_resonance",
    description: "Show which ideas are generating the most energy and activity right now.",
    inputSchema: { type: "object", properties: {} },
  },

  // Specs
  {
    name: "coherence_list_specs",
    description: "List feature specs with ROI metrics, value gaps, and implementation summaries.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", default: 20 },
        search: { type: "string", description: "Search keyword" },
      },
    },
  },
  {
    name: "coherence_get_spec",
    description: "Get full spec detail including implementation summary, pseudocode, and ROI.",
    inputSchema: {
      type: "object",
      properties: { spec_id: { type: "string" } },
      required: ["spec_id"],
    },
  },

  // Lineage
  {
    name: "coherence_list_lineage",
    description: "List value lineage chains connecting ideas to specs, implementations, and payouts.",
    inputSchema: {
      type: "object",
      properties: { limit: { type: "number", default: 20 } },
    },
  },
  {
    name: "coherence_lineage_valuation",
    description: "Get ROI valuation for a lineage chain — measured value, estimated cost, and ROI ratio.",
    inputSchema: {
      type: "object",
      properties: { lineage_id: { type: "string" } },
      required: ["lineage_id"],
    },
  },

  // Identity
  {
    name: "coherence_list_providers",
    description: "List all 37 supported identity providers grouped by category (Social, Dev, Crypto/Web3, Professional, Identity, Custom).",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "coherence_link_identity",
    description: "Link a provider identity (GitHub, Discord, Ethereum, etc.) to a contributor. No registration required.",
    inputSchema: {
      type: "object",
      properties: {
        contributor_id: { type: "string", description: "Contributor name" },
        provider: { type: "string", description: "Provider key (github, discord, ethereum, solana, ...)" },
        provider_id: { type: "string", description: "Handle, address, or username on that provider" },
      },
      required: ["contributor_id", "provider", "provider_id"],
    },
  },
  {
    name: "coherence_lookup_identity",
    description: "Find which contributor owns a specific provider identity. Reverse lookup.",
    inputSchema: {
      type: "object",
      properties: {
        provider: { type: "string" },
        provider_id: { type: "string" },
      },
      required: ["provider", "provider_id"],
    },
  },
  {
    name: "coherence_get_identities",
    description: "Get all linked identities for a contributor.",
    inputSchema: {
      type: "object",
      properties: { contributor_id: { type: "string" } },
      required: ["contributor_id"],
    },
  },

  // Contributions
  {
    name: "coherence_record_contribution",
    description: "Record a contribution. Identify by contributor_id OR by provider+provider_id (no registration needed).",
    inputSchema: {
      type: "object",
      properties: {
        contributor_id: { type: "string", description: "Contributor name (optional if provider+provider_id given)" },
        provider: { type: "string", description: "Identity provider (optional)" },
        provider_id: { type: "string", description: "Identity handle (optional)" },
        type: { type: "string", description: "Contribution type: code, docs, review, design, community, other" },
        amount_cc: { type: "number", description: "CC value (default 1)", default: 1 },
        idea_id: { type: "string", description: "Related idea ID (optional)" },
      },
      required: ["type"],
    },
  },
  {
    name: "coherence_contributor_ledger",
    description: "Get a contributor's CC balance and contribution history.",
    inputSchema: {
      type: "object",
      properties: { contributor_id: { type: "string" } },
      required: ["contributor_id"],
    },
  },

  // Status
  {
    name: "coherence_status",
    description: "Get network health: API status, uptime, federation nodes, idea count.",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "coherence_friction_report",
    description: "Get friction report — where the pipeline struggles.",
    inputSchema: {
      type: "object",
      properties: {
        window_days: { type: "number", default: 30 },
      },
    },
  },

  // Governance
  {
    name: "coherence_list_change_requests",
    description: "List governance change requests.",
    inputSchema: { type: "object", properties: {} },
  },

  // Federation
  {
    name: "coherence_list_federation_nodes",
    description: "List federated nodes and their capabilities.",
    inputSchema: { type: "object", properties: {} },
  },
];

// ---------------------------------------------------------------------------
// Tool handlers
// ---------------------------------------------------------------------------

async function handleTool(name, args) {
  switch (name) {
    // Ideas
    case "coherence_list_ideas":
      if (args.search) return apiGet("/api/ideas/cards", { search: args.search, limit: args.limit || 20 });
      return apiGet("/api/ideas", { limit: args.limit || 20 });
    case "coherence_get_idea":
      return apiGet(`/api/ideas/${args.idea_id}`);
    case "coherence_idea_progress":
      return apiGet(`/api/ideas/${args.idea_id}/progress`);
    case "coherence_select_idea":
      return apiPost("/api/ideas/select", { temperature: args.temperature ?? 0.5 });
    case "coherence_showcase":
      return apiGet("/api/ideas/showcase");
    case "coherence_resonance":
      return apiGet("/api/ideas/resonance");

    // Specs
    case "coherence_list_specs":
      if (args.search) return apiGet("/api/spec-registry/cards", { search: args.search, limit: args.limit || 20 });
      return apiGet("/api/spec-registry", { limit: args.limit || 20 });
    case "coherence_get_spec":
      return apiGet(`/api/spec-registry/${args.spec_id}`);

    // Lineage
    case "coherence_list_lineage":
      return apiGet("/api/value-lineage/links", { limit: args.limit || 20 });
    case "coherence_lineage_valuation":
      return apiGet(`/api/value-lineage/links/${args.lineage_id}/valuation`);

    // Identity
    case "coherence_list_providers":
      return apiGet("/api/identity/providers");
    case "coherence_link_identity":
      return apiPost("/api/identity/link", {
        contributor_id: args.contributor_id,
        provider: args.provider,
        provider_id: args.provider_id,
        display_name: args.provider_id,
      });
    case "coherence_lookup_identity":
      return apiGet(`/api/identity/lookup/${encodeURIComponent(args.provider)}/${encodeURIComponent(args.provider_id)}`);
    case "coherence_get_identities":
      return apiGet(`/api/identity/${encodeURIComponent(args.contributor_id)}`);

    // Contributions
    case "coherence_record_contribution":
      return apiPost("/api/contributions/record", {
        contributor_id: args.contributor_id || undefined,
        provider: args.provider || undefined,
        provider_id: args.provider_id || undefined,
        type: args.type,
        amount_cc: args.amount_cc ?? 1,
        idea_id: args.idea_id || undefined,
      });
    case "coherence_contributor_ledger":
      return apiGet(`/api/contributions/ledger/${encodeURIComponent(args.contributor_id)}`);

    // Status
    case "coherence_status": {
      const [health, count, nodes] = await Promise.all([
        apiGet("/api/health"),
        apiGet("/api/ideas/count"),
        apiGet("/api/federation/nodes"),
      ]);
      return { health, ideas: count, federation_nodes: Array.isArray(nodes) ? nodes.length : 0 };
    }
    case "coherence_friction_report":
      return apiGet("/api/friction/report", { window_days: args.window_days || 30 });

    // Governance
    case "coherence_list_change_requests":
      return apiGet("/api/governance/change-requests");

    // Federation
    case "coherence_list_federation_nodes": {
      const [nodes, caps] = await Promise.all([
        apiGet("/api/federation/nodes"),
        apiGet("/api/federation/nodes/capabilities"),
      ]);
      return { nodes, capabilities: caps };
    }

    default:
      return { error: `Unknown tool: ${name}` };
  }
}

// ---------------------------------------------------------------------------
// MCP server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "coherence-network", version: "0.1.0" },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    const result = await handleTool(name, args || {});
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

// Start
const transport = new StdioServerTransport();
await server.connect(transport);
