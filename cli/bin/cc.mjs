#!/usr/bin/env node

/**
 * cc — Coherence Network CLI
 *
 * Identity-first contributions, idea staking, and value traceability.
 * Zero dependencies. Node 18+ required.
 */

import { createRequire } from "node:module";
import { listIdeas, showIdea, shareIdea, stakeOnIdea, forkIdea, createIdea } from "../lib/commands/ideas.mjs";
import { listSpecs, showSpec } from "../lib/commands/specs.mjs";
import { contribute } from "../lib/commands/contribute.mjs";
import { showStatus, showResonance } from "../lib/commands/status.mjs";
import { showIdentity, linkIdentity, unlinkIdentity, lookupIdentity, setupIdentity, setIdentity } from "../lib/commands/identity.mjs";
import { listNodes, sendMessage, readMessages, sendCommand } from "../lib/commands/nodes.mjs";
import { listTasks, showTask, claimTask, claimNext, reportTask, seedTask } from "../lib/commands/tasks.mjs";

// Version check — non-blocking, runs in background
const require = createRequire(import.meta.url);
const pkg = require("../package.json");
const LOCAL_VERSION = pkg.version;

async function checkForUpdate() {
  try {
    const resp = await fetch("https://registry.npmjs.org/coherence-cli/latest", {
      signal: AbortSignal.timeout(3000),
    });
    if (!resp.ok) return;
    const data = await resp.json();
    const latest = data.version;
    if (latest && latest !== LOCAL_VERSION && latest > LOCAL_VERSION) {
      console.log(
        `\n\x1b[33m  Update available: ${LOCAL_VERSION} → ${latest}\x1b[0m` +
        `\n  Run: npm i -g coherence-cli@${latest}\n`,
      );
    }
  } catch {
    // Silent — don't block the CLI for a version check
  }
}

const updateCheck = checkForUpdate();

const [command, ...args] = process.argv.slice(2);

const COMMANDS = {
  ideas:      () => listIdeas(args),
  idea:       () => handleIdea(args),
  share:      () => shareIdea(),
  stake:      () => stakeOnIdea(args),
  fork:       () => forkIdea(args),
  specs:      () => listSpecs(args),
  spec:       () => showSpec(args),
  contribute: () => contribute(args),
  status:     () => showStatus(),
  resonance:  () => showResonance(),
  identity:   () => handleIdentity(args),
  nodes:      () => listNodes(),
  msg:        () => sendMessage(args),
  cmd:        () => sendCommand(args),
  messages:   () => readMessages(args),
  inbox:      () => readMessages(args),
  tasks:      () => listTasks(args),
  task:       () => handleTask(args),
  update:     () => selfUpdate(),
  version:    () => console.log(`cc v${LOCAL_VERSION}`),
  help:       () => showHelp(),
};

async function handleIdea(args) {
  if (args[0] === "create") return createIdea(args.slice(1));
  return showIdea(args);
}

async function handleTask(args) {
  const sub = args[0];
  switch (sub) {
    case "next":    return claimNext();
    case "claim":   return claimTask(args.slice(1));
    case "report":  return reportTask(args.slice(1));
    case "seed":    return seedTask(args.slice(1));
    default:        return showTask(args);
  }
}

async function handleIdentity(args) {
  const sub = args[0];
  const subArgs = args.slice(1);
  switch (sub) {
    case "link":   return linkIdentity(subArgs);
    case "unlink": return unlinkIdentity(subArgs);
    case "lookup": return lookupIdentity(subArgs);
    case "setup":  return setupIdentity();
    case "set":    return setIdentity(subArgs);
    default:       return showIdentity();
  }
}

async function selfUpdate() {
  const { execSync } = await import("node:child_process");
  console.log(`Current: v${LOCAL_VERSION}`);
  console.log("Checking npm for latest version...");
  try {
    const resp = await fetch("https://registry.npmjs.org/coherence-cli/latest", {
      signal: AbortSignal.timeout(5000),
    });
    const data = await resp.json();
    const latest = data.version;
    if (latest === LOCAL_VERSION) {
      console.log(`\x1b[32m✓\x1b[0m Already on latest version (${LOCAL_VERSION})`);
      return;
    }
    console.log(`Updating ${LOCAL_VERSION} → ${latest}...`);
    execSync(`npm i -g coherence-cli@${latest}`, { stdio: "inherit" });
    console.log(`\x1b[32m✓\x1b[0m Updated to v${latest}`);
  } catch (e) {
    console.error(`\x1b[31m✗\x1b[0m Update failed: ${e.message}`);
    console.log("  Manual: npm i -g coherence-cli@latest");
  }
}

function showHelp() {
  console.log(`
\x1b[1mcc\x1b[0m — Coherence Network CLI

\x1b[1mUsage:\x1b[0m cc <command> [args]

\x1b[1mExplore:\x1b[0m
  ideas [limit]           Browse ideas by ROI
  idea <id>               View idea detail
  idea create <id> <name> [--desc "..." --value N --cost N --parent <id>]
  specs [limit]           List feature specs
  spec <id>               View spec detail
  resonance               What's alive right now
  status                  Network health + node info

\x1b[1mContribute:\x1b[0m
  share                   Submit a new idea (interactive)
  contribute              Record contribution (interactive)
  contribute --type code --cc 5 --idea <id> --desc "what I did"
  stake <id> <cc>         Stake CC on an idea
  fork <id>               Fork an idea

\x1b[1mIdentity:\x1b[0m
  identity                Show your linked accounts
  identity setup          Guided onboarding
  identity set <id>       Set identity non-interactively
  identity link <p> <id>  Link a provider (github, discord, ethereum, ...)
  identity unlink <p>     Unlink a provider
  identity lookup <p> <id> Find contributor by identity

\x1b[1mTasks (agent-to-agent):\x1b[0m
  tasks [status] [limit]  List tasks (pending|running|completed)
  task <id>               View task detail
  task next               Claim next pending task (for AI agents)
  task claim <id>         Claim a specific task
  task report <id> <status> [output]  Report result (completed|failed)
  task seed <idea> [type] Create task from idea (spec|test|impl|review)

\x1b[1mFederation:\x1b[0m
  nodes                   List federation nodes
  msg <node|broadcast> <text>  Send message to a node
  cmd <node> <command>    Remote command (update|status|diagnose|restart|ping)
  inbox                   Read your messages

\x1b[1mSystem:\x1b[0m
  update                  Self-update to latest npm version
  version                 Show current version
  help                    Show this help

\x1b[1mProviders:\x1b[0m
  github, x, discord, telegram, mastodon, bluesky, linkedin, reddit,
  youtube, twitch, instagram, tiktok, gitlab, bitbucket, npm, crates,
  pypi, hackernews, stackoverflow, ethereum, bitcoin, solana, cosmos,
  nostr, ens, lens, email, google, apple, microsoft, orcid, did,
  keybase, pgp, fediverse, openclaw

\x1b[2mHub: https://api.coherencycoin.com\x1b[0m
`);
}

// Run
const handler = COMMANDS[command];
if (handler) {
  Promise.resolve(handler()).catch((err) => {
    console.error(err.message);
    process.exit(1);
  });
} else if (!command) {
  showHelp();
} else {
  console.log(`Unknown command: ${command}`);
  console.log("Run 'cc help' for available commands.");
  process.exit(1);
}
