/**
 * Identity-first onboarding — runs on first use if no contributor_id in config.
 *
 * Interactive:   asks for name + primary identity (e.g. github:seeker71)
 * Non-interactive: auto-generates from COHERENCE_CONTRIBUTOR_ID / COHERENCE_CONTRIBUTOR env, git config,
 *                  or hostname — then registers with the network.
 */

import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";
import { execSync } from "node:child_process";
import { hostname } from "node:os";
import { createHash } from "node:crypto";
import { getContributorId, saveConfig, loadKeys, saveKeys } from "./config.mjs";
import { post } from "./api.mjs";

const ONBOARD_PROVIDERS = ["github", "ethereum", "x", "discord", "email"];

async function prompt(rl, question) {
  const answer = await rl.question(question);
  return answer.trim();
}

/**
 * Try to detect identity from environment:
 *   1. COHERENCE_CONTRIBUTOR_ID env var
 *   2. COHERENCE_CONTRIBUTOR (legacy) env var
 *   3. git config user.name (most developers have this)
 *   4. hostname-based hash (last resort)
 */
function detectIdentity() {
  // 1–2. Explicit env vars (R3)
  if (process.env.COHERENCE_CONTRIBUTOR_ID?.trim()) {
    return { id: process.env.COHERENCE_CONTRIBUTOR_ID.trim(), source: "env" };
  }
  if (process.env.COHERENCE_CONTRIBUTOR?.trim()) {
    return { id: process.env.COHERENCE_CONTRIBUTOR.trim(), source: "env" };
  }

  // 3. Git config
  try {
    const gitUser = execSync("git config user.name", { encoding: "utf8", timeout: 3000 }).trim();
    if (gitUser) {
      return { id: gitUser, source: "git" };
    }
  } catch {}

  // 4. Hostname hash
  const hash = createHash("sha256").update(hostname()).digest("hex").slice(0, 8);
  return { id: `node-${hostname().split(".")[0].toLowerCase()}-${hash}`, source: "hostname" };
}

/**
 * Ensure the user has a contributor identity.
 * If not, run guided onboarding (interactive) or auto-detect (non-interactive).
 */
export async function ensureIdentity() {
  let id = getContributorId();
  if (id) return id;

  // Non-interactive environment — auto-detect and register silently
  if (!stdin.isTTY) {
    const detected = detectIdentity();
    saveConfig({ contributor_id: detected.id });

    // Register with the network
    await post("/api/identity/link", {
      contributor_id: detected.id,
      provider: "name",
      provider_id: detected.id,
      display_name: detected.id,
    });

    // Try to link git identity too
    try {
      const gitUser = execSync("git config user.name", { encoding: "utf8", timeout: 3000 }).trim();
      const gitEmail = execSync("git config user.email", { encoding: "utf8", timeout: 3000 }).trim();
      if (gitEmail) {
        await post("/api/identity/link", {
          contributor_id: detected.id,
          provider: "email",
          provider_id: gitEmail,
          display_name: gitUser || detected.id,
        });
      }
    } catch {}

    console.error(`Registered as: ${detected.id} (from ${detected.source})`);
    console.error(`Link identity: cc identity link github <handle>`);
    return detected.id;
  }

  // Interactive — guided onboarding
  const rl = createInterface({ input: stdin, output: stdout });

  console.log();
  console.log("\x1b[1mWelcome to the Coherence Network.\x1b[0m");
  console.log("Every contribution is traced, scored, and fairly attributed.");
  console.log();

  // Suggest detected identity
  const detected = detectIdentity();
  const name = await prompt(rl, `Your name [${detected.id}]: `) || detected.id;

  saveConfig({ contributor_id: name });
  id = name;

  // Link name identity
  await post("/api/identity/link", {
    contributor_id: name,
    provider: "name",
    provider_id: name,
    display_name: name,
  });

  console.log();
  console.log("Link an identity to get credit for your work.");
  console.log("Format: provider:handle (e.g. github:seeker71)");
  console.log();

  // Ask for primary identity
  const primary = await prompt(rl, "Primary identity (e.g. github:seeker71): ");
  if (primary && primary.includes(":")) {
    const [provider, handle] = primary.split(":", 2);
    if (provider && handle) {
      const result = await post("/api/identity/link", {
        contributor_id: name,
        provider: provider.toLowerCase(),
        provider_id: handle,
        display_name: handle,
      });
      if (result) {
        console.log(`  \x1b[32m✓\x1b[0m Linked ${provider}:${handle}`);
      } else {
        console.log(`  \x1b[33m!\x1b[0m Could not link. Try later: cc identity link ${provider} ${handle}`);
      }
    }
  }

  // Offer additional providers
  console.log();
  const more = await prompt(rl, "Link more accounts? (y/n): ");
  if (more.toLowerCase() === "y" || more.toLowerCase() === "yes") {
    for (const provider of ONBOARD_PROVIDERS) {
      const value = await prompt(rl, `  ${provider} handle (enter to skip): `);
      if (value) {
        const result = await post("/api/identity/link", {
          contributor_id: name,
          provider,
          provider_id: value,
          display_name: value,
        });
        if (result) {
          console.log(`  \x1b[32m✓\x1b[0m Linked ${provider}:${value}`);
        } else {
          console.log(`  \x1b[33m!\x1b[0m Could not link. Try later: cc identity link ${provider} ${value}`);
        }
      }
    }
  }

  // Generate personal API key if none exists yet
  const existingKeys = loadKeys();
  if (!existingKeys.api_key) {
    // Pick the first linked identity provider for keying
    let keyProvider = "name";
    let keyProviderId = name;
    if (primary && primary.includes(":")) {
      const [kp, ki] = primary.split(":", 2);
      if (kp && ki) { keyProvider = kp.toLowerCase(); keyProviderId = ki; }
    }
    const keyResult = await post("/api/auth/keys", {
      contributor_id: name,
      provider: keyProvider,
      provider_id: keyProviderId,
    });
    if (keyResult && keyResult.api_key) {
      saveKeys({
        contributor_id: name,
        api_key: keyResult.api_key,
        provider: keyProvider,
        provider_id: keyProviderId,
        created_at: keyResult.created_at,
        scopes: keyResult.scopes,
      });
      console.log(`\x1b[32m✓\x1b[0m API key generated and saved to ~/.coherence-network/keys.json`);
    } else {
      console.log(`\x1b[33m!\x1b[0m Could not generate API key now. Run: cc setup`);
    }
  }

  console.log();
  console.log(`\x1b[32m✓\x1b[0m Registered as: ${name}`);
  console.log(`Config saved to ~/.coherence-network/config.json`);
  console.log(`Link more anytime: cc identity link <provider> <handle>`);
  console.log();

  rl.close();
  return id;
}
