/**
 * Contribute command — record any contribution.
 *
 * Interactive:  cc contribute
 * Non-interactive (for agents):
 *   cc contribute --type code --cc 5 --idea <id> --desc "what I did"
 */

import { post } from "../api.mjs";
import { ensureIdentity } from "../identity.mjs";
import { getContributorId } from "../config.mjs";

function parseFlags(args) {
  const flags = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--type" && args[i + 1]) flags.type = args[++i];
    else if (args[i] === "--cc" && args[i + 1]) flags.cc = parseFloat(args[++i]);
    else if (args[i] === "--idea" && args[i + 1]) flags.idea = args[++i];
    else if (args[i] === "--desc" && args[i + 1]) flags.desc = args[++i];
  }
  return flags;
}

export async function contribute(args = []) {
  const flags = parseFlags(args);
  const hasFlags = flags.type || flags.cc || flags.idea || flags.desc;

  if (hasFlags) {
    // Non-interactive mode (for agents and scripts)
    const contributor = getContributorId() || "anonymous";
    const type = flags.type || "other";
    const amount = flags.cc || 1.0;
    const ideaId = flags.idea || undefined;
    const description = flags.desc || "";

    const result = await post("/api/contributions/record", {
      contributor_id: contributor,
      type,
      amount_cc: amount,
      idea_id: ideaId,
      metadata: { description },
    });

    if (result) {
      console.log(`\x1b[32m✓\x1b[0m ${type} ${amount} CC${ideaId ? ` → ${ideaId}` : ""}${description ? ` (${description})` : ""}`);
    } else {
      console.log("Failed to record contribution.");
      process.exit(1);
    }
    return;
  }

  // Interactive mode
  const contributor = await ensureIdentity();
  const { createInterface } = await import("node:readline/promises");
  const { stdin, stdout } = await import("node:process");
  const rl = createInterface({ input: stdin, output: stdout });

  console.log();
  console.log("Record a contribution — anything you did that created value.");
  console.log();

  const type = (await rl.question("Type (code/docs/review/design/community/other): > ")).trim() || "other";
  const amount = parseFloat((await rl.question("CC value (default 1): > ")).trim()) || 1.0;
  const ideaId = (await rl.question("Idea ID (optional, press enter to skip): > ")).trim() || undefined;
  const description = (await rl.question("Brief description: > ")).trim();

  rl.close();

  const result = await post("/api/contributions/record", {
    contributor_id: contributor,
    type,
    amount_cc: amount,
    idea_id: ideaId,
    metadata: { description },
  });

  if (result) {
    console.log(`\x1b[32m✓\x1b[0m Contribution recorded: ${type} (${amount} CC)`);
  } else {
    console.log("Failed to record contribution.");
  }
}
