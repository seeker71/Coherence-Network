/**
 * Credentials commands: coh credentials add, coh credentials list, coh credentials remove
 */

import { get, post, del } from "../api.mjs";

/** Add a new repository credential */
export async function credentialsAdd(args) {
  let contributorId = null;
  let repoUrl = null;
  let type = "github_token";
  let raw = null;
  let scopes = [];

  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--contributor-id" || args[i] === "-c") && args[i + 1]) contributorId = args[++i];
    else if ((args[i] === "--repo" || args[i] === "-r") && args[i + 1]) repoUrl = args[++i];
    else if ((args[i] === "--type" || args[i] === "-t") && args[i + 1]) type = args[++i];
    else if ((args[i] === "--token" || args[i] === "-k") && args[i + 1]) raw = args[++i];
    else if (args[i] === "--scopes" && args[i + 1]) scopes = args[++i].split(",");
  }

  if (!contributorId || !repoUrl || !raw) {
    console.log("Usage: coh credentials add --contributor-id <id> --repo <url> --token <token> [--type <type>] [--scopes s1,s2]");
    console.log("Example: coh credentials add -c cont_123 -r github.com/user/repo -k ghp_XYZ123");
    return;
  }

  const body = {
    contributor_id: contributorId,
    repo_url: repoUrl,
    credential_type: type,
    credential_raw: raw,
    scopes: scopes
  };

  const result = await post("/api/credentials", body);
  if (!result) return;

  // Save the raw token locally for the runner to use (R6 - Spec 169)
  const { loadKeys, saveKeys } = await import("../config.mjs");
  const keys = loadKeys();
  keys.repo_tokens = keys.repo_tokens || {};
  keys.repo_tokens[repoUrl] = raw;
  saveKeys(keys);

  console.log(`\x1b[1m  CREDENTIAL ADDED\x1b[0m`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  ID:             ${result.id}`);
  console.log(`  Contributor ID: ${result.contributor_id}`);
  console.log(`  Repo URL:       ${result.repo_url}`);
  console.log(`  Type:           ${result.credential_type}`);
  console.log(`  Status:         ${result.status}`);
  console.log(`  Created:        ${new Date(result.created_at).toLocaleString()}`);
  console.log(`  Note: Raw token is NOT stored in the database (only SHA-256 hash).`);
  console.log();
}

/** List credentials */
export async function credentialsList(args) {
  let contributorId = null;
  let repoUrl = null;

  for (let i = 0; i < args.length; i++) {
    if ((args[i] === "--contributor-id" || args[i] === "-c") && args[i + 1]) contributorId = args[++i];
    else if ((args[i] === "--repo" || args[i] === "-r") && args[i + 1]) repoUrl = args[++i];
  }

  const params = new URLSearchParams();
  if (contributorId) params.append("contributor_id", contributorId);
  if (repoUrl) params.append("repo_url", repoUrl);

  const url = `/api/credentials${params.toString() ? "?" + params.toString() : ""}`;
  const result = await get(url);
  if (!result || !result.credentials) return;

  if (result.credentials.length === 0) {
    console.log("No credentials found.");
    return;
  }

  console.log(`\x1b[1m  REPO CREDENTIALS\x1b[0m (${result.credentials.length})`);
  console.log(`  ${"ID".padEnd(16)} | ${"CONTRIBUTOR".padEnd(12)} | ${"REPO".padEnd(30)} | ${"TYPE".padEnd(15)} | ${"STATUS"}`);
  console.log(`  ${"─".repeat(85)}`);
  
  for (const cred of result.credentials) {
    console.log(`  ${cred.id.padEnd(16)} | ${cred.contributor_id.padEnd(12)} | ${cred.repo_url.padEnd(30)} | ${cred.credential_type.padEnd(15)} | ${cred.status}`);
  }
  console.log();
}

/** Remove a credential */
export async function credentialsRemove(args) {
  let id = null;
  if (args[0] && !args[0].startsWith("-")) id = args[0];

  if (!id) {
    console.log("Usage: coh credentials remove <id>");
    return;
  }

  const result = await del(`/api/credentials/${id}`);
  if (!result) return;

  console.log(`\x1b[1m  CREDENTIAL REMOVED\x1b[0m`);
  console.log(`  ID: ${id}`);
  console.log();
}
