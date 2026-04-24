/**
 * Interactive onboarding: coh setup
 *
 * Guides a new contributor through identity + API key setup.
 * Non-interactive mode: coh setup --name <name> --provider <p> --id <id>
 */

import { post } from "../api.mjs";
import { join } from "node:path";
import { homedir } from "node:os";
import { createInterface } from "node:readline";
import { loadKeys, saveKeys, saveConfig, CONFIG_DIR } from "../config.mjs";

const KEYS_FILE = join(CONFIG_DIR, "keys.json");

function ask(rl, question) {
  return new Promise((resolve) => rl.question(question, resolve));
}

export async function setup(args) {
  const force = args.includes("--force") || args.includes("--reset");

  // Check if already set up
  const keys = loadKeys();
  if (keys.api_key && keys.contributor_id && !force) {
    console.log(`\n\x1b[32m✓\x1b[0m Already set up as \x1b[1m${keys.contributor_id}\x1b[0m`);
    console.log(`  API key: ${keys.api_key.slice(0, 12)}...`);
    if (keys.provider) console.log(`  Provider: ${keys.provider}:${keys.provider_id}`);
    console.log(`\n  To reconfigure: coh setup --reset`);
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

  // One-shot onboard: create contributor + link identity + generate key
  const result = await post("/api/onboard", {
    name,
    provider,
    provider_id: providerId,
    display_name: name,
  });

  if (!result || !result.api_key) {
    console.log(`\x1b[31m✗\x1b[0m Setup failed: ${JSON.stringify(result)}`);
    return;
  }

  // Save API key to keys.json and contributor_id to config.json
  saveKeys({
    contributor_id: name,
    api_key: result.api_key,
    provider,
    provider_id: providerId,
    created_at: result.created_at,
    scopes: result.scopes,
  });
  saveConfig({ contributor_id: name });

  console.log(`
\x1b[32m✓\x1b[0m Setup complete!

  Contributor: \x1b[1m${name}\x1b[0m
  Identity:    ${provider}:${providerId}
  API key:     ${result.api_key.slice(0, 20)}...
  Saved to:    ${KEYS_FILE}

  You can now:
    coh ideas              Browse ideas
    coh share              Submit a new idea
    coh contribute         Record a contribution
    coh stake <id> <cc>    Invest in an idea
    coh status             Check network health
`);
}
