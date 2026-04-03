/**
 * Guide commands: cc guide
 * A guided experience for new contributors.
 */

import { get, post } from "../api.mjs";
import { loadKeys, saveKeys } from "../config.mjs";
import { onboardingRegister } from "./onboarding.mjs";
import { credentialsAdd } from "./credentials.mjs";
import { shareIdea } from "./ideas.mjs";
import { listTasks, showTask } from "./tasks.mjs";

const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m", C = "\x1b[36m";

export async function guide(args) {
  const isNonInteractive = args.includes("--non-interactive");
  const step = args.find(a => !a.startsWith("-")) || "start";

  switch (step) {
    case "start":
      return welcome(isNonInteractive);
    case "register":
      return registerStep(args, isNonInteractive);
    case "credentials":
      return credentialsStep(args, isNonInteractive);
    case "ideate":
      return ideateStep(args, isNonInteractive);
    case "flow":
      return flowStep(args, isNonInteractive);
    default:
      console.log(`Unknown guide step: ${step}`);
      console.log("Steps: start, register, credentials, ideate, flow");
  }
}

async function welcome(nonInteractive) {
  console.log(`\n${B}${C}  WELCOME TO THE COHERENCE NETWORK${R}`);
  console.log(`  ${"─".repeat(50)}`);
  console.log(`  This guide will walk you through contributing to a public repo.`);
  console.log(`  Steps:`);
  console.log(`  1. ${B}Register${R} your contributor identity`);
  console.log(`  2. Setup ${B}Credentials${R} for your target repository`);
  console.log(`  3. ${B}Ideate${R} and share your contribution idea`);
  console.log(`  4. Track the ${B}Flow${R} from idea to merged PR`);
  console.log();
  if (!nonInteractive) {
    console.log(`  To start, run: ${G}cc guide register --handle <your-name>${R}`);
  } else {
    console.log(`  Non-interactive mode: Use the subcommands with required flags.`);
  }
  console.log();
}

async function registerStep(args, nonInteractive) {
  console.log(`\n${B}${C}  STEP 1: REGISTRATION${R}`);
  console.log(`  ${"─".repeat(50)}`);
  
  // Call onboardingRegister but we might need to capture its output or 
  // do it slightly differently to save keys locally.
  await onboardingRegister(args);
  
  console.log(`  Next, setup your repo credentials:`);
  console.log(`  ${G}cc guide credentials --contributor-id <id> --repo <url> --token <token>${R}`);
  console.log();
}

async function credentialsStep(args, nonInteractive) {
  console.log(`\n${B}${C}  STEP 2: REPO CREDENTIALS${R}`);
  console.log(`  ${"─".repeat(50)}`);
  
  await credentialsAdd(args);
  
  console.log(`  Next, share your first idea:`);
  console.log(`  ${G}cc guide ideate --name "My Feature" --desc "Description"${R}`);
  console.log();
}

async function ideateStep(args, nonInteractive) {
  console.log(`\n${B}${C}  STEP 3: IDEATION${R}`);
  console.log(`  ${"─".repeat(50)}`);
  
  // shareIdea is interactive by default, we might need a non-interactive way
  if (nonInteractive) {
    let name = null, desc = null;
    for (let i = 0; i < args.length; i++) {
        if (args[i] === "--name" && args[i+1]) name = args[++i];
        if (args[i] === "--desc" && args[i+1]) desc = args[++i];
    }
    if (!name) {
        console.log("Usage: cc guide ideate --name <n> --desc <d>");
        return;
    }
    const res = await post("/api/ideas", { 
        name, 
        description: desc, 
        work_type: "feature",
        potential_value: 10,
        estimated_cost: 5
    });
    if (res) {
        console.log(`  Idea created: ${B}${res.id}${R} - ${res.name}`);
    }
  } else {
    await shareIdea();
  }
  
  console.log(`  Next, watch the flow of your idea into tasks and PRs:`);
  console.log(`  ${G}cc guide flow --idea-id <id>${R}`);
  console.log();
}

async function flowStep(args, nonInteractive) {
  console.log(`\n${B}${C}  STEP 4: THE FLOW${R}`);
  console.log(`  ${"─".repeat(50)}`);
  
  let ideaId = null;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--idea-id" && args[i+1]) ideaId = args[++i];
  }
  
  if (!ideaId) {
    console.log("Usage: cc guide flow --idea-id <id>");
    return;
  }
  
  const res = await get(`/api/ideas/${ideaId}/tasks`);
  if (!res || !res.tasks) {
    console.log("  No tasks found for this idea yet.");
    return;
  }
  
  console.log(`  Tasks for idea ${B}${ideaId}${R}:`);
  for (const task of res.tasks) {
    const statusColor = task.status === "completed" ? G : (task.status === "running" ? Y : D);
    console.log(`  - [${statusColor}${task.status}${R}] ${task.id}: ${task.type}`);
    if (task.output && task.output.includes("Pull Request")) {
        console.log(`    ${B}PR Created:${R} ${task.output}`);
    }
  }
  
  console.log(`\n  ${G}Congratulations!${R} You've seen the end-to-end flow.`);
  console.log(`  In a real scenario, agents or other contributors would pick up these tasks.`);
  console.log();
}
