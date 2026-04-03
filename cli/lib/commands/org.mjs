/**
 * Org command — view agent hierarchy and roles
 * 
 * cc org                — Show your reporting lines
 * cc org <contributor>  — Show org for specific contributor
 */

import inquirer from "inquirer";
import chalk from "chalk";
import ora from "ora";
import { get } from "../api.mjs";
import { getContributorId } from "../config.mjs";

export async function runOrgCommand(args = []) {
  const isTTY = process.stdout.isTTY;
  const targetId = args[0] || getContributorId();

  if (!targetId) {
    console.log(chalk.yellow("⚠ No contributor ID provided and no local identity set."));
    return;
  }

  const spinner = ora(chalk.cyan(`Fetching organization for ${targetId}...`)).start();
  
  // Fetch 'manages' and 'delegates-to' edges
  const [incoming, outgoing] = await Promise.all([
    get(`/api/entities/contributor:${encodeURIComponent(targetId)}/edges`, { direction: 'incoming' }),
    get(`/api/entities/contributor:${encodeURIComponent(targetId)}/edges`, { direction: 'outgoing' })
  ]);

  spinner.stop();

  console.log(chalk.bold(`\nORGANIZATION: ${targetId}`));
  console.log(chalk.dim("─".repeat(50)));

  const managers = (incoming?.items || []).filter(e => e.type === 'manages');
  const reports = (outgoing?.items || []).filter(e => e.type === 'manages');
  const delegates = (outgoing?.items || []).filter(e => e.type === 'delegates-to');

  if (managers.length > 0) {
    console.log(chalk.cyan("Managers:"));
    managers.forEach(m => console.log(`  ↑ ${m.from_node?.name || m.from_id}`));
  }

  if (reports.length > 0) {
    console.log(chalk.magenta("\nDirect Reports:"));
    reports.forEach(r => console.log(`  ↓ ${r.to_node?.name || r.to_id}`));
  }

  if (delegates.length > 0) {
    console.log(chalk.yellow("\nDelegated To:"));
    delegates.forEach(d => console.log(`  → ${d.to_node?.name || d.to_id}`));
  }

  if (managers.length === 0 && reports.length === 0 && delegates.length === 0) {
    console.log(chalk.dim("  No reporting lines defined. This contributor is a liquid agent."));
  }
  console.log();
}
