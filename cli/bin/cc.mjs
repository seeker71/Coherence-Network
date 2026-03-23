#!/usr/bin/env node

/**
 * cc — Coherence Network CLI
 *
 * Identity-first contributions, idea staking, and value traceability.
 * Zero dependencies. Node 18+ required.
 */

import { listIdeas, showIdea, shareIdea, stakeOnIdea, forkIdea } from "../lib/commands/ideas.mjs";
import { listSpecs, showSpec } from "../lib/commands/specs.mjs";
import { contribute } from "../lib/commands/contribute.mjs";
import { showStatus, showResonance } from "../lib/commands/status.mjs";
import { showIdentity, linkIdentity, unlinkIdentity, lookupIdentity, setupIdentity } from "../lib/commands/identity.mjs";

const [command, ...args] = process.argv.slice(2);

const COMMANDS = {
  ideas:      () => listIdeas(args),
  idea:       () => showIdea(args),
  share:      () => shareIdea(),
  stake:      () => stakeOnIdea(args),
  fork:       () => forkIdea(args),
  specs:      () => listSpecs(args),
  spec:       () => showSpec(args),
  contribute: () => contribute(),
  status:     () => showStatus(),
  resonance:  () => showResonance(),
  identity:   () => handleIdentity(args),
  help:       () => showHelp(),
};

async function handleIdentity(args) {
  const sub = args[0];
  const subArgs = args.slice(1);
  switch (sub) {
    case "link":   return linkIdentity(subArgs);
    case "unlink": return unlinkIdentity(subArgs);
    case "lookup": return lookupIdentity(subArgs);
    case "setup":  return setupIdentity();
    default:       return showIdentity();
  }
}

function showHelp() {
  console.log(`
\x1b[1mcc\x1b[0m — Coherence Network CLI

\x1b[1mUsage:\x1b[0m cc <command> [args]

\x1b[1mExplore:\x1b[0m
  ideas [limit]           Browse ideas by ROI
  idea <id>               View idea detail
  specs [limit]           List feature specs
  spec <id>               View spec detail
  resonance               What's alive right now
  status                  Network health + node info

\x1b[1mContribute:\x1b[0m
  share                   Submit a new idea
  stake <id> <cc>         Stake CC on an idea
  fork <id>               Fork an idea
  contribute              Record any contribution

\x1b[1mIdentity:\x1b[0m
  identity                Show your linked accounts
  identity setup          Guided onboarding
  identity link <p> <id>  Link a provider (github, discord, ethereum, ...)
  identity unlink <p>     Unlink a provider
  identity lookup <p> <id> Find contributor by identity

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
