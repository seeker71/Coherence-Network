/**
 * Skills command — procedural memory from the Hermes Learning Loop
 * 
 * cc skills             — Interactive skills browser
 */

import inquirer from "inquirer";
import chalk from "chalk";
import ora from "ora";
import { get } from "../api.mjs";

export async function runSkillsCommand(args = []) {
  const isTTY = process.stdout.isTTY;

  const spinner = ora(chalk.cyan("Accessing procedural memory...")).start();
  const data = await get("/api/agent/skills", { limit: 100 });
  spinner.stop();

  if (!data || !data.skills || data.skills.length === 0) {
    console.log(chalk.yellow("No skills ingested yet. Procedural memory is empty."));
    return;
  }

  if (isTTY) {
    await interactiveSkills(data.skills);
  } else {
    console.log(chalk.bold("\nNETWORK SKILLS:"));
    data.skills.forEach(s => {
      console.log(`- ${chalk.cyan(s.id.padEnd(20))} ${s.name}`);
    });
  }
}

async function interactiveSkills(skills) {
  const choices = skills.map(s => ({
    name: `${s.name.padEnd(30)} ${chalk.dim(s.id)}`,
    value: s
  }));

  const { skill } = await inquirer.prompt([
    {
      type: "list",
      name: "skill",
      message: "Procedural Skills Library",
      choices,
      pageSize: 15
    }
  ]);

  if (skill) {
    console.log(chalk.bold(`\nSKILL: ${skill.name}`));
    console.log(chalk.dim("─".repeat(50)));
    console.log(skill.description); // Markdown Skill Document
    console.log(chalk.dim("─".repeat(50)));
    console.log();
  }
}
