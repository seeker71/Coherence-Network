/**
 * Ontology command — accessible ontology for non-technical contributors.
 *
 * Usage:
 *   cc ontology contribute --text "Water seeks balance" --domains ecology,physics
 *   cc ontology list [--domain ecology] [--status placed]
 *   cc ontology garden
 *   cc ontology stats
 *   cc ontology get <id>
 */

import { get, post, patch, del } from "../api.mjs";
import { getContributorId } from "../config.mjs";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseFlags(args) {
  const flags = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--text" && args[i + 1]) flags.text = args[++i];
    else if (args[i] === "--title" && args[i + 1]) flags.title = args[++i];
    else if (args[i] === "--domains" && args[i + 1]) {
      flags.domains = args[++i].split(",").map((d) => d.trim());
    } else if (args[i] === "--domain" && args[i + 1]) flags.domain = args[++i];
    else if (args[i] === "--status" && args[i + 1]) flags.status = args[++i];
    else if (args[i] === "--contributor" && args[i + 1]) flags.contributor = args[++i];
    else if (args[i] === "--limit" && args[i + 1]) flags.limit = parseInt(args[++i], 10);
    else if (args[i] === "--json") flags.json = true;
    else if (!args[i].startsWith("--")) flags._positional = args[i];
  }
  return flags;
}

function statusColour(status) {
  if (status === "placed") return "\x1b[32m";   // green
  if (status === "pending") return "\x1b[33m";  // yellow
  return "\x1b[90m";                            // grey for orphan
}

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const DIM = "\x1b[2m";
const GREEN = "\x1b[32m";
const CYAN = "\x1b[36m";

// ---------------------------------------------------------------------------
// Sub-commands
// ---------------------------------------------------------------------------

async function contribute(flags) {
  const contributorId = flags.contributor || getContributorId() || "anonymous";

  if (!flags.text) {
    console.error("Error: --text <description> is required");
    process.exit(1);
  }

  const payload = {
    plain_text: flags.text,
    contributor_id: contributorId,
    domains: flags.domains || [],
    view_preference: "garden",
  };
  if (flags.title) payload.title = flags.title;

  const result = await post("/api/ontology/contribute", payload);
  if (!result) {
    console.error("Failed to submit concept.");
    process.exit(1);
  }

  if (flags.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  const sc = statusColour(result.status);
  console.log();
  console.log(`${GREEN}✓${RESET} Concept submitted`);
  console.log(`  ${BOLD}${result.title}${RESET}`);
  console.log(`  ID: ${DIM}${result.id}${RESET}`);
  console.log(`  Status: ${sc}${result.status}${RESET}`);
  if (result.core_concept_match) {
    console.log(`  Matched core concept: ${CYAN}${result.core_concept_match}${RESET}`);
  }
  if (result.inferred_relationships.length > 0) {
    console.log(`  Inferred ${result.inferred_relationships.length} relationship(s):`);
    for (const rel of result.inferred_relationships.slice(0, 3)) {
      console.log(`    ${DIM}→ ${rel.concept_name} (${rel.relationship_type}, ${Math.round(rel.confidence * 100)}% conf)${RESET}`);
    }
  }
  console.log();
}

async function list(flags) {
  const params = new URLSearchParams();
  if (flags.domain) params.set("domain", flags.domain);
  if (flags.status) params.set("status", flags.status);
  if (flags.contributor) params.set("contributor_id", flags.contributor);
  if (flags.limit) params.set("limit", flags.limit);

  const result = await get(`/api/ontology/contributions?${params}`);
  if (!result) {
    console.error("Failed to fetch contributions.");
    process.exit(1);
  }

  if (flags.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  console.log();
  console.log(`${BOLD}Ontology Contributions${RESET} ${DIM}(${result.total} total)${RESET}`);
  console.log();
  for (const item of result.items) {
    const sc = statusColour(item.status);
    const domains = item.domains.length > 0 ? ` [${item.domains.join(", ")}]` : "";
    console.log(
      `  ${sc}●${RESET} ${BOLD}${item.title}${RESET}${DIM}${domains}${RESET}`
    );
    console.log(`    ${DIM}${item.id} · by ${item.contributor_id} · ${item.status}${RESET}`);
  }
  console.log();
}

async function garden(flags) {
  const result = await get("/api/ontology/garden");
  if (!result) {
    console.error("Failed to fetch garden view.");
    process.exit(1);
  }

  if (flags.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  console.log();
  console.log(`${BOLD}Ontology Garden${RESET} ${DIM}— ${result.total} concepts in ${result.domain_count} domains${RESET}`);
  console.log(`  Contributors: ${result.contributor_count}  Placement rate: ${Math.round(result.placement_rate * 100)}%`);
  console.log();

  for (const cluster of result.clusters) {
    console.log(`  ${CYAN}${cluster.name}${RESET} ${DIM}(${cluster.size})${RESET}`);
    for (const m of cluster.members.slice(0, 5)) {
      const sc = statusColour(m.status);
      console.log(`    ${sc}▸${RESET} ${m.title}`);
    }
    if (cluster.members.length > 5) {
      console.log(`    ${DIM}…and ${cluster.members.length - 5} more${RESET}`);
    }
  }
  console.log();
}

async function stats(flags) {
  const result = await get("/api/ontology/stats");
  if (!result) {
    console.error("Failed to fetch stats.");
    process.exit(1);
  }

  if (flags.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  const pct = Math.round(result.placement_rate * 100);
  console.log();
  console.log(`${BOLD}Accessible Ontology Stats${RESET}`);
  console.log(`  Total contributions:   ${result.total_contributions}`);
  console.log(`  Placed in graph:       ${GREEN}${result.placed_count}${RESET}`);
  console.log(`  Pending placement:     ${result.pending_count}`);
  console.log(`  Orphan (new space):    ${result.orphan_count}`);
  console.log(`  Placement rate:        ${pct}%`);
  console.log(`  Inferred edges:        ${result.inferred_edges_count}`);
  if (result.top_domains.length > 0) {
    console.log(`  Top domains:           ${result.top_domains.map((d) => `${d.domain}(${d.count})`).join(", ")}`);
  }
  if (result.recent_contributors.length > 0) {
    console.log(`  Recent contributors:   ${result.recent_contributors.join(", ")}`);
  }
  console.log();
}

async function getOne(id, flags) {
  const result = await get(`/api/ontology/contributions/${encodeURIComponent(id)}`);
  if (!result) {
    console.error(`Concept '${id}' not found.`);
    process.exit(1);
  }

  if (flags.json) {
    console.log(JSON.stringify(result, null, 2));
    return;
  }

  const sc = statusColour(result.status);
  console.log();
  console.log(`${BOLD}${result.title}${RESET}`);
  console.log(`  ID:          ${result.id}`);
  console.log(`  Status:      ${sc}${result.status}${RESET}`);
  console.log(`  Contributor: ${result.contributor_id}`);
  console.log(`  Domains:     ${result.domains.join(", ") || "(none)"}`);
  console.log(`  Description: ${result.plain_text}`);
  if (result.core_concept_match) {
    console.log(`  Core match:  ${CYAN}${result.core_concept_match}${RESET}`);
  }
  if (result.inferred_relationships.length > 0) {
    console.log(`  Inferred relationships:`);
    for (const rel of result.inferred_relationships) {
      console.log(
        `    → ${rel.concept_name} (${rel.relationship_type}, ${Math.round(rel.confidence * 100)}% confidence)`
      );
    }
  }
  console.log();
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

export async function ontology(args = []) {
  const sub = args[0];
  const rest = args.slice(1);
  const flags = parseFlags(rest);

  switch (sub) {
    case "contribute":
      return contribute(flags);
    case "list":
      return list(flags);
    case "garden":
      return garden(flags);
    case "stats":
      return stats(flags);
    case "get":
      if (!flags._positional) {
        console.error("Usage: cc ontology get <id>");
        process.exit(1);
      }
      return getOne(flags._positional, flags);
    default:
      console.log();
      console.log(`${BOLD}cc ontology${RESET} — accessible ontology for everyone`);
      console.log();
      console.log("  contribute --text <description> [--domains d1,d2] [--title title]");
      console.log("  list       [--domain d] [--status placed|pending|orphan]");
      console.log("  garden     Show clustered garden view");
      console.log("  stats      Show contribution statistics");
      console.log("  get <id>   Show a single concept");
      console.log();
      console.log("  Add --json to any command for machine-readable output.");
      console.log();
  }
}
