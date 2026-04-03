/**
 * Collaboration command — work together on ideas
 * 
 * cc collab             — Interactive collab dashboard for focused idea
 * cc collab broadcast   — Signal interest in the focused idea
 * cc collab list        — List active collaborators for focused idea
 */

import inquirer from "inquirer";
import chalk from "chalk";
import ora from "ora";
import { get, post } from "../api.mjs";
import { getFocus, getContributorId } from "../config.mjs";

export async function runCollabCommand(args = []) {
  const focus = getFocus();
  const contributorId = getContributorId();

  if (!focus.idea_id) {
    console.log(chalk.yellow("⚠ No focused idea. Use 'cc focus' to pick one first."));
    return;
  }

  const sub = args[0];
  switch (sub) {
    case "broadcast": return broadcastCollab(focus.idea_id, contributorId);
    case "list":      return listCollaborators(focus.idea_id);
    default:          return interactiveCollab(focus.idea_id, contributorId);
  }
}

async function broadcastCollab(ideaId, cid) {
  const spinner = ora(chalk.cyan(`Broadcasting collaboration signal for ${ideaId}...`)).start();
  
  // Implemented via a 'collab-signal' edge in the graph
  const result = await post("/api/edges", {
    from_id: `contributor:${cid}`,
    to_id: ideaId,
    type: "signals-interest-in",
    strength: 1.0,
    created_by: "cc-cli"
  });

  spinner.stop();
  if (result) {
    console.log(chalk.green(`✓ Signal broadcasted! You are now listed as interested in ${chalk.bold(ideaId)}.`));
  } else {
    console.log(chalk.red("✗ Failed to broadcast signal."));
  }
}

async function listCollaborators(ideaId) {
  const spinner = ora(chalk.cyan("Fetching active collaborators...")).start();
  
  // Fetch stakers and task claimants
  const [ideaData, tasksData] = await Promise.all([
    get(`/api/ideas/${encodeURIComponent(ideaId)}`),
    get(`/api/agent/tasks`, { idea_id: ideaId, limit: 100 })
  ]);

  spinner.stop();

  console.log(chalk.bold(`\nCOLLABORATORS for ${ideaId}`));
  console.log(chalk.dim("─".repeat(50)));

  const collaborators = new Set();
  
  // From stakers
  if (ideaData?.stakers) {
    ideaData.stakers.forEach(s => collaborators.add({ id: s.contributor_id, role: 'Staker' }));
  }

  // From tasks
  const tasks = tasksData?.tasks || [];
  tasks.forEach(t => {
    if (t.worker_id && t.worker_id !== 'mcp-agent') {
      collaborators.add({ id: t.worker_id, role: t.status === 'completed' ? 'Contributor' : 'Working' });
    }
  });

  if (collaborators.size === 0) {
    console.log(chalk.dim("  No active collaborators yet. Be the first!"));
  } else {
    collaborators.forEach(c => {
      console.log(`  ${chalk.cyan(c.id.padEnd(20))} ${chalk.dim(`[${c.role}]`)}`);
    });
  }
  console.log();
}

async function interactiveCollab(ideaId, cid) {
  console.log(chalk.bold(`\n协作 COLLABORATION: ${ideaId}`));
  
  const { action } = await inquirer.prompt([
    {
      type: "list",
      name: "action",
      message: "What would you like to do?",
      choices: [
        { name: "List current collaborators", value: "list" },
        { name: "Broadcast my interest (Find peers)", value: "broadcast" },
        { name: "Seed a task for others to claim", value: "seed" },
        { name: "View resonance with my beliefs", value: "resonance" },
        new inquirer.Separator(),
        { name: "Exit", value: null }
      ]
    }
  ]);

  switch (action) {
    case "list":      return listCollaborators(ideaId);
    case "broadcast": return broadcastCollab(ideaId, cid);
    case "seed":      
      const { seedTask } = await import("./tasks.mjs");
      return seedTask([ideaId]);
    case "resonance":
      const result = await get(`/api/contributors/${encodeURIComponent(cid)}/beliefs/resonance`, { idea_id: ideaId });
      console.log(chalk.cyan("\nRESONANCE BREAKDOWN:"));
      console.log(`- Overall: ${chalk.bold((result.resonance_score * 100).toFixed(1))}%`);
      console.log(`- Concept Overlap: ${result.breakdown.concept_overlap}`);
      console.log(`- Worldview Align: ${result.breakdown.worldview_alignment}`);
      console.log();
      break;
  }
}
