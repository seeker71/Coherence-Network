/**
 * Interactive onboarding: cc setup
 *
 * Guides a new contributor through identity + API key setup.
 * Non-interactive mode: cc setup --name <name> --provider <p> --id <id>
 */

import { get, post } from "../api.mjs";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";

const CONFIG_DIR = join(homedir(), ".coherence-network");
const KEYS_FILE = join(CONFIG_DIR, "keys.json");

function ask(rl, question) {
  return new Promise((resolve) => rl.question(question, resolve));
}

function loadKeys() {
  try {
    return JSON.parse(readFileSync(KEYS_FILE, "utf-8"));
  } catch {
    return {};
  }
}

function saveKeys(keys) {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(KEYS_FILE, JSON.stringify(keys, null, 2), { mode: 0o600 });
}

export async function setup(args) {
  // Check if already set up
  const keys = loadKeys();
  if (keys.api_key && keys.contributor_id) {
    console.log(`\n\x1b[32m✓\x1b[0m Already set up as \x1b[1m${keys.contributor_id}\x1b[0m`);
    console.log(`  API key: ${keys.api_key.slice(0, 12)}...`);
    console.log(`  Provider: ${keys.provider}:${keys.provider_id}`);
    console.log(`\n  To reconfigure: rm ${KEYS_FILE} && cc setup`);
    return;
  }

  // Non-interactive mode
  const nameIdx = args.indexOf("--name");
  const providerIdx = args.indexOf("--provider");
  const idIdx = args.indexOf("--id");

  if (nameIdx >= 0 && providerIdx >= 0 && idIdx >= 0) {
    const name = args[nameIdx + 1];
    const provider = args[providerIdx + 1];
    const providerId = args[idIdx + 1];
    return await completeSetup(name, provider, providerId);
  }

  // Interactive mode
  const rl = createInterface({ input: process.stdin, output: process.stdout });

  console.log(`
\x1b[1mCoherence Network — Contributor Setup\x1b[0m

This will create your contributor identity and generate a personal API key.
Everything you create, contribute, and invest will be attributed to you.
`);

  const name = await ask(rl, "  Your name (will be your contributor ID): ");
  if (!name.trim()) {
    console.log("\x1b[31m✗\x1b[0m Name is required");
    rl.close();
    return;
  }

  console.log(`
  Link an identity so others can find and verify you.
  Providers: github, email, ethereum, discord, x, linkedin, telegram, ...
`);

  const provider = await ask(rl, "  Provider (e.g. github): ");
  const providerId = await ask(rl, `  Your ${provider || "provider"} handle/address: `);

  rl.close();

  if (!provider.trim() || !providerId.trim()) {
    console.log("\x1b[31m✗\x1b[0m Provider and handle are required");
    return;
  }

  await completeSetup(name.trim(), provider.trim().toLowerCase(), providerId.trim());
}

async function completeSetup(name, provider, providerId) {
  console.log(`\n  Setting up \x1b[1m${name}\x1b[0m with ${provider}:${providerId}...`);

  // Generate API key
  const result = await post("/api/auth/keys", {
    contributor_id: name,
    provider,
    provider_id: providerId,
  });

  if (!result || !result.api_key) {
    console.log(`\x1b[31m✗\x1b[0m Setup failed: ${JSON.stringify(result)}`);
    return;
  }

  // Save to config
  const keys = {
    contributor_id: name,
    api_key: result.api_key,
    provider,
    provider_id: providerId,
    created_at: result.created_at,
    scopes: result.scopes,
  };
  saveKeys(keys);

  console.log(`
\x1b[32m✓\x1b[0m Setup complete!

  Contributor: \x1b[1m${name}\x1b[0m
  Identity:    ${provider}:${providerId}
  API key:     ${result.api_key.slice(0, 20)}...
  Saved to:    ${KEYS_FILE}

  You can now:
    cc ideas              Browse ideas
    cc share              Submit a new idea
    cc contribute         Record a contribution
    cc stake <id> <cc>    Invest in an idea
    cc status             Check network health
`);
}
