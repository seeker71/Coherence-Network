/**
 * Contribute command — record any contribution.
 */

import { post } from "../api.mjs";
import { ensureIdentity } from "../identity.mjs";
import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";

export async function contribute() {
  const contributor = await ensureIdentity();
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
