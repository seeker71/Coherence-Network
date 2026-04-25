/**
 * Focus command — persistent context management
 * 
 * Sets an 'active' idea or task that other commands can use as a default.
 * Supports both interactive (pick from list) and non-interactive modes.
 */

import inquirer from "inquirer";
import chalk from "chalk";
import { get, getApiBase } from "../api.mjs";
import { saveContext, getFocus } from "../config.mjs";

export async function runFocusCommand(args = []) {
  const isTTY = process.stdout.isTTY;
  const [targetId] = args;

  // Non-interactive: clear focus
  if (args.includes("--clear")) {
    saveContext({ focused_idea_id: null, focused_task_id: null });
    console.log(chalk.yellow("✓ Focus cleared"));
    return;
  }

  // Non-interactive: set specific ID
  if (targetId) {
    // Basic heuristic: tasks start with 'task_'
    if (targetId.startsWith("task_")) {
      saveContext({ focused_task_id: targetId });
      console.log(chalk.green(`✓ Focused on task: ${chalk.bold(targetId)}`));
    } else {
      saveContext({ focused_idea_id: targetId });
      console.log(chalk.green(`✓ Focused on idea: ${chalk.bold(targetId)}`));
    }
    return;
  }

  // Interactive mode (if TTY)
  if (isTTY) {
    await runInteractiveFocus();
  } else {
    // Show current focus if not TTY and no args
    const focus = getFocus();
    if (!focus.idea_id && !focus.task_id) {
      console.log("No active focus. Use 'coh focus <id>' to set one.");
    } else {
      if (focus.idea_id) console.log(`Active Idea: ${focus.idea_id}`);
      if (focus.task_id) console.log(`Active Task: ${focus.task_id}`);
    }
  }
}

async function runInteractiveFocus() {
  console.log(chalk.cyan("◉ Loading top ideas for you to focus on..."));
  
  const result = await get("/api/ideas", { limit: 20 });
  if (!result || !result.ideas) {
    console.log(chalk.red("✗ Failed to fetch ideas."));
    return;
  }

  const choices = result.ideas.map(i => ({
    name: `${i.name} ${chalk.dim(`(${i.id})`)} — ROI: ${chalk.yellow(i.roi_cc?.toFixed(1) || '0.0')}x`,
    value: i.id
  }));

  choices.push(new inquirer.Separator());
  choices.push({ name: chalk.dim("Clear Focus"), value: null });

  const { idea_id } = await inquirer.prompt([
    {
      type: "list",
      name: "idea_id",
      message: "Which idea would you like to focus on?",
      choices,
      pageSize: 15
    }
  ]);

  if (idea_id) {
    saveContext({ focused_idea_id: idea_id });
    console.log(chalk.green(`✓ Focus set to: ${chalk.bold(idea_id)}`));
  } else {
    saveContext({ focused_idea_id: null, focused_task_id: null });
    console.log(chalk.yellow("✓ Focus cleared"));
  }
}
