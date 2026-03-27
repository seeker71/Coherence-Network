/**
 * Identity commands: show, link, unlink, lookup, setup
 */

import { get, post, del } from "../api.mjs";
import { getContributorId } from "../config.mjs";
import { ensureIdentity } from "../identity.mjs";

export async function showIdentity() {
  const id = getContributorId();
  if (!id) {
    console.log("No identity configured. Run: cc identity setup");
    console.log("Or set env var: COHERENCE_CONTRIBUTOR_ID=<contributor_id>");
    return;
  }
  const data = await get(`/api/identity/${encodeURIComponent(id)}`);

  console.log();
  console.log(`\x1b[1m  ${id}\x1b[0m`);
  console.log(`  ${"─".repeat(40)}`);

  if (!data || !Array.isArray(data) || data.length === 0) {
    console.log("  No linked accounts.");
  } else {
    for (const rec of data) {
      const dot = rec.verified ? "\x1b[32m●\x1b[0m" : "\x1b[33m○\x1b[0m";
      console.log(`  ${dot} ${rec.provider.padEnd(14)} ${rec.provider_id}`);
    }
  }
  console.log();
  console.log("  Link more: cc identity link <provider> <id>");
  console.log();
}

export async function linkIdentity(args) {
  const [provider, ...rest] = args;
  const providerId = rest.join(" ");
  if (!provider || !providerId) {
    console.log("Usage: cc identity link <provider> <id>");
    console.log("Providers: github, x, discord, telegram, ethereum, bitcoin, solana, email, gitlab, linkedin, ...");
    return;
  }
  const contributor = await ensureIdentity();
  const result = await post("/api/identity/link", {
    contributor_id: contributor,
    provider,
    provider_id: providerId,
    display_name: providerId,
  });
  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Linked ${provider}:${providerId}`);
  } else {
    console.log("Link failed.");
  }
}

export async function unlinkIdentity(args) {
  const provider = args[0];
  if (!provider) {
    console.log("Usage: cc identity unlink <provider>");
    return;
  }
  const contributor = getContributorId();
  if (!contributor) {
    console.log("No identity configured.");
    return;
  }
  const ok = await del(`/api/identity/${encodeURIComponent(contributor)}/${provider}`);
  if (ok) {
    console.log(`\x1b[32m✓\x1b[0m Unlinked ${provider}`);
  } else {
    console.log("Unlink failed or not found.");
  }
}

export async function lookupIdentity(args) {
  const [provider, providerId] = args;
  if (!provider || !providerId) {
    console.log("Usage: cc identity lookup <provider> <id>");
    return;
  }
  const data = await get(`/api/identity/lookup/${encodeURIComponent(provider)}/${encodeURIComponent(providerId)}`);
  if (data) {
    console.log(`\x1b[32m✓\x1b[0m ${provider}:${providerId} → contributor: ${data.contributor_id}`);
  } else {
    console.log(`No contributor found for ${provider}:${providerId}`);
  }
}

export async function setIdentity(args) {
  const id = args[0];
  if (!id) {
    console.log("Usage: cc identity set <contributor_id>");
    console.log("Sets the contributor identity non-interactively (for agents and scripts).");
    console.log("Alternative: export COHERENCE_CONTRIBUTOR_ID=<contributor_id>");
    return;
  }
  const { saveConfig } = await import("../config.mjs");
  saveConfig({ contributor_id: id });
  console.log(`\x1b[32m✓\x1b[0m Identity set to: ${id}`);
}

export async function setupIdentity() {
  // Force re-run onboarding
  await ensureIdentity();
}
