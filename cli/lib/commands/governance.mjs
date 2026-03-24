/**
 * Governance commands: governance, governance vote, governance propose
 */

import { get, post } from "../api.mjs";

function truncate(str, len) {
  if (!str) return "";
  return str.length > len ? str.slice(0, len - 1) + "\u2026" : str;
}

export async function listChangeRequests() {
  const raw = await get("/api/governance/change-requests");
  const data = Array.isArray(raw) ? raw : raw?.change_requests || raw?.items;
  if (!data || !Array.isArray(data)) {
    console.log("Could not fetch change requests.");
    return;
  }
  if (data.length === 0) {
    console.log("No change requests found.");
    return;
  }

  console.log();
  console.log(`\x1b[1m  GOVERNANCE\x1b[0m (${data.length} change requests)`);
  console.log(`  ${"─".repeat(60)}`);
  for (const cr of data) {
    const status = cr.status || "?";
    const dot = status === "approved" ? "\x1b[32m●\x1b[0m" : status === "rejected" ? "\x1b[31m●\x1b[0m" : "\x1b[33m●\x1b[0m";
    const title = truncate(cr.title || cr.id, 45);
    console.log(`  ${dot} ${title.padEnd(47)} ${status}`);
  }
  console.log();
}

export async function showChangeRequest(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc governance <id>");
    return;
  }
  const data = await get(`/api/governance/change-requests/${encodeURIComponent(id)}`);
  if (!data) {
    console.log(`Change request '${id}' not found.`);
    return;
  }

  console.log();
  console.log(`\x1b[1m  ${data.title || data.id}\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  if (data.id) console.log(`  ID:          ${data.id}`);
  if (data.status) console.log(`  Status:      ${data.status}`);
  if (data.description) console.log(`  Description: ${truncate(data.description, 60)}`);
  if (data.votes_for != null) console.log(`  Votes For:   ${data.votes_for}`);
  if (data.votes_against != null) console.log(`  Against:     ${data.votes_against}`);
  if (data.created_at) console.log(`  Created:     ${data.created_at}`);
  console.log();
}

export async function vote(args) {
  const id = args[0];
  const choice = args[1];
  if (!id || !choice || !["yes", "no"].includes(choice)) {
    console.log("Usage: cc governance vote <id> <yes|no>");
    return;
  }
  const result = await post(`/api/governance/change-requests/${encodeURIComponent(id)}/votes`, {
    vote: choice,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Vote '${choice}' recorded on ${id}`);
  } else {
    console.log("Vote failed.");
  }
}

export async function propose(args) {
  const title = args[0];
  const desc = args.slice(1).join(" ");
  if (!title || !desc) {
    console.log("Usage: cc governance propose <title> <description>");
    return;
  }
  const result = await post("/api/governance/change-requests", { title, description: desc });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Proposal created: ${result.id || title}`);
  } else {
    console.log("Failed to create proposal.");
  }
}
