/**
 * Guides command — discover creators and thought leaders
 * 
 * cc guides             — Show top guides who package knowledge
 */

import chalk from "chalk";
import ora from "ora";
import { get } from "../api.mjs";

export async function runGuidesCommand(args = []) {
  const spinner = ora(chalk.cyan("Finding network guides...")).start();
  
  // Since we don't have a dedicated guides endpoint yet, we list top contributors
  // and highlight them as guides based on their contributions.
  const data = await get("/api/contributors", { limit: 50 });
  spinner.stop();

  if (!data || !data.items || data.items.length === 0) {
    console.log(chalk.yellow("No guides found on the network yet."));
    return;
  }

  console.log(chalk.bold("\nNETWORK GUIDES"));
  console.log(chalk.dim("─".repeat(50)));
  console.log(chalk.dim("People who package knowledge and solve real-world problems."));
  console.log();

  data.items.slice(0, 10).forEach(c => {
    // In a real implementation, we would sort by `blueprint_royalty` or CC balance
    console.log(`- ${chalk.cyan(c.name.padEnd(20))} ${chalk.dim(c.type || 'Human')}`);
  });
  
  console.log(chalk.dim("\nTip: Create blueprints and skills to become a guide and earn CC royalties."));
}
