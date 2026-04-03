/**
 * Blueprints command — template-based roadmap seeding
 * 
 * cc blueprints          — List available blueprints
 * cc blueprint apply <id> — Apply a blueprint roadmap
 */

import inquirer from "inquirer";
import chalk from "chalk";
import ora from "ora";
import { get, post } from "../api.mjs";

export async function runBlueprintsCommand(args = []) {
  const isTTY = process.stdout.isTTY;
  const sub = args[0];

  if (sub === "apply") {
    return applyBlueprint(args[1], args[2]);
  }

  const spinner = ora(chalk.cyan("Fetching blueprints...")).start();
  const blueprints = await get("/api/blueprints");
  spinner.stop();

  if (!blueprints || blueprints.length === 0) {
    console.log(chalk.yellow("No blueprints available."));
    return;
  }

  if (isTTY && !sub) {
    await interactiveBlueprint(blueprints);
  } else {
    console.log(chalk.bold("\nAVAILABLE BLUEPRINTS:"));
    blueprints.forEach(b => {
      console.log(`- ${chalk.cyan(b.id.padEnd(15))} ${b.name} — ${chalk.dim(b.description)}`);
    });
    console.log(chalk.dim("\nUse 'cc blueprint apply <id>' to seed a roadmap."));
  }
}

async function applyBlueprint(id, prefix = "") {
  if (!id) {
    console.log("Usage: cc blueprint apply <id> [prefix]");
    return;
  }

  const spinner = ora(chalk.cyan(`Applying blueprint '${id}'...`)).start();
  const result = await post(`/api/blueprints/${id}/apply?prefix=${prefix}`);
  spinner.stop();

  if (result?.ideas_created) {
    console.log(chalk.green(`\n✓ Success! Blueprint '${id}' applied.`));
    console.log(`- ${result.ideas_created.length} Ideas created`);
    console.log(`- ${result.edges_created.length} Edges created`);
    console.log(chalk.dim("\nNew Ideas:"));
    result.ideas_created.forEach(iid => console.log(`  ○ ${iid}`));
  } else {
    console.log(chalk.red(`✗ Failed to apply blueprint '${id}'.`));
  }
}

async function interactiveBlueprint(blueprints) {
  const choices = blueprints.map(b => ({
    name: `${b.name.padEnd(25)} ${chalk.dim(b.description)}`,
    value: b.id
  }));

  const { selection } = await inquirer.prompt([
    {
      type: "list",
      name: "selection",
      message: "Select a project blueprint to view:",
      choices,
      pageSize: 15
    }
  ]);

  if (selection) {
    const { action } = await inquirer.prompt([
      {
        type: "list",
        name: "action",
        message: `What would you like to do with '${selection}'?`,
        choices: [
          { name: "Apply to network (Seed roadmap)", value: "apply" },
          { name: "Back to list", value: "back" },
          { name: "Exit", value: null }
        ]
      }
    ]);

    if (action === "apply") {
      const { prefix } = await inquirer.prompt([
        { type: "input", name: "prefix", message: "Optional ID prefix (e.g. 'my-app-'):" }
      ]);
      return applyBlueprint(selection, prefix);
    } else if (action === "back") {
      return interactiveBlueprint(blueprints);
    }
  }
}
