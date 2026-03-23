/**
 * Identity-first onboarding — runs on first use if no contributor_id in config.
 */

import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";
import { getContributorId, saveConfig } from "./config.mjs";
import { post } from "./api.mjs";

const ONBOARD_PROVIDERS = ["github", "ethereum", "x", "email"];

async function prompt(rl, question) {
  const answer = await rl.question(question);
  return answer.trim();
}

/**
 * Ensure the user has a contributor identity.
 * If not, run guided onboarding. Returns the contributor_id.
 */
export async function ensureIdentity() {
  let id = getContributorId();
  if (id) return id;

  // Non-interactive environment — can't prompt
  if (!stdin.isTTY) {
    console.error("No contributor identity configured.");
    console.error("Set COHERENCE_CONTRIBUTOR or run: cc identity setup");
    process.exit(1);
  }

  const rl = createInterface({ input: stdin, output: stdout });

  console.log();
  console.log("\x1b[1mWelcome to the Coherence Network.\x1b[0m");
  console.log();

  const name = await prompt(rl, "What's your name? > ");
  if (!name) {
    console.log("A name is needed to attribute your contributions.");
    rl.close();
    process.exit(1);
  }

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

  for (const provider of ONBOARD_PROVIDERS) {
    const yn = await prompt(rl, `Link your ${provider}? (y/n) > `);
    if (yn.toLowerCase() === "y" || yn.toLowerCase() === "yes") {
      const value = await prompt(rl, `  ${provider} handle/address: > `);
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
          console.log(`  \x1b[33m!\x1b[0m Could not link (network issue). Try later: cc identity link ${provider} ${value}`);
        }
      }
    }
  }

  console.log();
  console.log(`Saved to ~/.coherence-network/config.json`);
  console.log(`Link more accounts anytime: cc identity link <provider> <id>`);
  console.log();

  rl.close();
  return id;
}
