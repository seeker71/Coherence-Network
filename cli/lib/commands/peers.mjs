/**
 * Peers command — discover other contributors
 * 
 * cc peers             — Interactive discovery (resonant + nearby)
 * cc peers --nearby    — Focus on geographic proximity
 * cc peers --resonance — Focus on interest matching
 */

import inquirer from "inquirer";
import chalk from "chalk";
import ora from "ora";
import { get } from "../api.mjs";
import { getContributorId } from "../config.mjs";

export async function runPeersCommand(args = []) {
  const contributorId = getContributorId();
  if (!contributorId) {
    console.log(chalk.yellow("⚠ You must set an identity first: cc identity link <provider> <handle>"));
    return;
  }

  const isTTY = process.stdout.isTTY;
  const nearbyOnly = args.includes("--nearby");
  const resonanceOnly = args.includes("--resonance");

  if (!isTTY) {
    return runNonInteractive(contributorId, nearbyOnly, resonanceOnly);
  }

  await runInteractive(contributorId, nearbyOnly, resonanceOnly);
}

async function runNonInteractive(cid, nearby, resonance) {
  const params = { contributor_id: cid, limit: 10 };
  
  if (!resonance) {
    const data = await get("/api/peers/nearby", params);
    if (data?.peers?.length) {
      console.log("\nNEARBY PEERS:");
      data.peers.forEach(p => console.log(`- ${p.name} (${p.city || 'Unknown'}) - ${p.distance_km?.toFixed(1)}km`));
    }
  }

  if (!nearby) {
    const data = await get("/api/peers/resonant", params);
    if (data?.peers?.length) {
      console.log("\nRESONANT PEERS:");
      data.peers.forEach(p => console.log(`- ${p.name} (Score: ${p.resonance_score})`));
    }
  }
}

async function runInteractive(cid, nearby, resonance) {
  const spinner = ora(chalk.cyan("Searching the network for peers...")).start();
  
  const [resonantData, nearbyData] = await Promise.all([
    resonance || !nearby ? get("/api/peers/resonant", { contributor_id: cid, limit: 20 }) : { peers: [] },
    nearby || !resonance ? get("/api/peers/nearby", { contributor_id: cid, limit: 20 }).catch(() => ({ peers: [] })) : { peers: [] }
  ]);

  spinner.stop();

  const choices = [];

  if (resonantData?.peers?.length) {
    choices.push(new inquirer.Separator(chalk.bold.cyan("--- RESONANT PEERS (Shared Interests) ---")));
    resonantData.peers.forEach(p => {
      const tags = p.shared_tags?.length ? chalk.dim(` [Shared: ${p.shared_tags.join(", ")}]`) : "";
      choices.push({
        name: `${p.name.padEnd(25)} ${chalk.yellow((p.resonance_score * 100).toFixed(0) + "% resonance")}${tags}`,
        value: { type: 'peer', id: p.contributor_id }
      });
    });
  }

  if (nearbyData?.peers?.length) {
    choices.push(new inquirer.Separator(chalk.bold.magenta("--- NEARBY PEERS (Proximity) ---")));
    nearbyData.peers.forEach(p => {
      choices.push({
        name: `${p.name.padEnd(25)} ${chalk.dim(p.city || 'Nearby')} — ${chalk.green(p.distance_km?.toFixed(1) + " km")}`,
        value: { type: 'peer', id: p.contributor_id }
      });
    });
  }

  if (choices.length === 0) {
    console.log(chalk.yellow("No peers found. Try expanding your interest tags or setting your location!"));
    return;
  }

  choices.push(new inquirer.Separator());
  choices.push({ name: chalk.dim("Exit"), value: null });

  const { selection } = await inquirer.prompt([
    {
      type: "list",
      name: "selection",
      message: "Contributor Discovery",
      choices,
      pageSize: 15
    }
  ]);

  if (selection && selection.type === 'peer') {
    // Forward to existing contributor detail command
    const { showContributor } = await import("./contributors.mjs");
    await showContributor([selection.id]);
  }
}
