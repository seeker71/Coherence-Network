#!/usr/bin/env node

/**
 * cc — Coherence Network CLI
 *
 * Identity-first contributions, idea staking, and value traceability.
 * Zero dependencies. Node 18+ required.
 */

import { listIdeas, showIdea, shareIdea, stakeOnIdea, forkIdea, createIdea } from "../lib/commands/ideas.mjs";
import { listSpecs, showSpec } from "../lib/commands/specs.mjs";
import { contribute } from "../lib/commands/contribute.mjs";
import { showStatus, showResonance } from "../lib/commands/status.mjs";
import { showIdentity, linkIdentity, unlinkIdentity, lookupIdentity, setupIdentity, setIdentity } from "../lib/commands/identity.mjs";
import { listNodes, sendMessage, sendCommand, readMessages } from "../lib/commands/nodes.mjs";
import { listContributors, showContributor, showContributions } from "../lib/commands/contributors.mjs";
import { listAssets, showAsset, createAsset } from "../lib/commands/assets.mjs";
import { showNewsFeed, showTrending, showSources, addSource, showNewsResonance } from "../lib/commands/news.mjs";
import { showTreasury, showDeposits, makeDeposit } from "../lib/commands/treasury.mjs";
import { listLinks, showLink, showValuation, payoutPreview } from "../lib/commands/lineage.mjs";
import { listChangeRequests, showChangeRequest, vote, propose } from "../lib/commands/governance.mjs";
import { listServices, showService, showServicesHealth, showServicesDeps } from "../lib/commands/services.mjs";
import { showFrictionReport, listFrictionEvents, showFrictionCategories } from "../lib/commands/friction.mjs";
import { listProviders, showProviderStats } from "../lib/commands/providers.mjs";
import { showTraceability, showCoverage, traceIdea, traceSpec } from "../lib/commands/traceability.mjs";
import { showDiag, showDiagHealth, showDiagIssues, showDiagRunners, showDiagVisibility, showDiagLive } from "../lib/commands/diagnostics.mjs";
import { publishDiag, startDiagMode } from "../lib/commands/diag_publish.mjs";
import { deploy } from "../lib/commands/deploy.mjs";
import { listen } from "../lib/commands/listen.mjs";
import { update } from "../lib/commands/update.mjs";
import { listTasks, showTask, claimTask, claimNext, reportTask, seedTask, postProgress, streamStart, watchTask } from "../lib/commands/tasks.mjs";
import {
  showConfig as difConfig, setBaseUrl as difSetBaseUrl,
  whoami as difWhoami, verify as difVerify, smoke as difSmoke,
  keyList as difKeyList, keyCreate as difKeyCreate, keyRevoke as difKeyRevoke,
  keyRotate as difKeyRotate, keyUpdate as difKeyUpdate, keyUse as difKeyUse, keyShow as difKeyShow,
  showUsage as difUsage, showLimits as difLimits, showFunding as difFunding,
  showFeedback as difFeedback,
} from "../lib/commands/dif.mjs";

const [command, ...args] = process.argv.slice(2);

const COMMANDS = {
  ideas:         () => listIdeas(args),
  idea:          () => handleIdea(args),
  share:         () => shareIdea(),
  stake:         () => stakeOnIdea(args),
  fork:          () => forkIdea(args),
  specs:         () => listSpecs(args),
  spec:          () => showSpec(args),
  contribute:    () => contribute(args),
  status:        () => showStatus(),
  resonance:     () => showResonance(),
  identity:      () => handleIdentity(args),
  nodes:         () => listNodes(),
  msg:           () => sendMessage(args),
  cmd:           () => sendCommand(args),
  command:       () => sendCommand(args),
  messages:      () => readMessages(args),
  inbox:         () => readMessages(args),
  contributors:  () => listContributors(args),
  contributor:   () => handleContributor(args),
  assets:        () => listAssets(args),
  asset:         () => handleAsset(args),
  news:          () => handleNews(args),
  treasury:      () => handleTreasury(args),
  lineage:       () => handleLineage(args),
  governance:    () => handleGovernance(args),
  services:      () => handleServices(args),
  service:       () => showService(args),
  friction:      () => handleFriction(args),
  providers:     () => handleProviders(args),
  trace:         () => handleTrace(args),
  diag:          () => handleDiag(args),
  tasks:         () => listTasks(args),
  task:          () => handleTask(args),
  update:        () => update(args),
  deploy:        () => deploy(args),
  listen:        () => listen(args),
  dif:           () => handleDif(args),
  progress:      () => postProgress(args),
  stream:        () => streamStart(args),
  watch:         () => watchTask(args),
  help:          () => showHelp(),
};

async function handleIdea(args) {
  if (args[0] === "create") return createIdea(args.slice(1));
  return showIdea(args);
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

async function handleContributor(args) {
  if (args[1] === "contributions") return showContributions(args);
  return showContributor(args);
}

async function handleTask(args) {
  const sub = args[0];
  switch (sub) {
    case "next":    return claimNext();
    case "claim":   return claimTask(args.slice(1));
    case "report":  return reportTask(args.slice(1));
    case "seed":    return seedTask(args.slice(1));
    case "watch":   return watchTask(args.slice(1));
    default:        return showTask(args);
  }
}

async function handleAsset(args) {
  if (args[0] === "create") return createAsset(args.slice(1));
  return showAsset(args);
}

async function handleNews(args) {
  const sub = args[0];
  switch (sub) {
    case "trending":  return showTrending();
    case "sources":   return showSources();
    case "source":
      if (args[1] === "add") return addSource(args.slice(2));
      return showSources();
    case "resonance": return showNewsResonance(args.slice(1));
    default:          return showNewsFeed();
  }
}

async function handleTreasury(args) {
  const sub = args[0];
  switch (sub) {
    case "deposits": return showDeposits(args.slice(1));
    case "deposit":  return makeDeposit(args.slice(1));
    default:         return showTreasury();
  }
}

async function handleLineage(args) {
  if (!args[0]) return listLinks([]);
  if (args[1] === "valuation") return showValuation(args);
  if (args[1] === "payout") return payoutPreview([args[0], args[2]]);
  // If first arg is a number, treat as limit
  if (/^\d+$/.test(args[0])) return listLinks(args);
  return showLink(args);
}

async function handleGovernance(args) {
  const sub = args[0];
  switch (sub) {
    case "vote":    return vote(args.slice(1));
    case "propose": return propose(args.slice(1));
    case undefined: return listChangeRequests();
    default:        return showChangeRequest(args);
  }
}

async function handleServices(args) {
  const sub = args[0];
  switch (sub) {
    case "health": return showServicesHealth();
    case "deps":   return showServicesDeps();
    default:       return listServices();
  }
}

async function handleFriction(args) {
  const sub = args[0];
  switch (sub) {
    case "events":     return listFrictionEvents(args.slice(1));
    case "categories": return showFrictionCategories();
    default:           return showFrictionReport();
  }
}

async function handleProviders(args) {
  const sub = args[0];
  switch (sub) {
    case "stats": return showProviderStats();
    default:      return listProviders();
  }
}

async function handleDif(args) {
  const sub = args[0];
  const subArgs = args.slice(1);
  switch (sub) {
    case "config":
      if (subArgs[0] === "set-base-url") return difSetBaseUrl(subArgs.slice(1));
      return difConfig();
    case "key":
      switch (subArgs[0]) {
        case "list":   return difKeyList();
        case "create": return difKeyCreate(subArgs.slice(1));
        case "revoke": return difKeyRevoke(subArgs.slice(1));
        case "rotate": return difKeyRotate(subArgs.slice(1));
        case "update": return difKeyUpdate(subArgs.slice(1));
        case "use":    return difKeyUse(subArgs.slice(1));
        case "show":   return difKeyShow();
        default:       return difKeyList();
      }
    case "verify":  return difVerify(subArgs);
    case "smoke":   return difSmoke();
    case "whoami":  return difWhoami();
    case "usage":   return difUsage(subArgs);
    case "limits":  return difLimits();
    case "funding":  return difFunding();
    case "feedback": return difFeedback(subArgs);
    default:         return difConfig();
  }
}

async function handleTrace(args) {
  const sub = args[0];
  switch (sub) {
    case "coverage": return showCoverage();
    case "idea":     return traceIdea(args.slice(1));
    case "spec":     return traceSpec(args.slice(1));
    default:         return showTraceability();
  }
}

async function handleDiag(args) {
  const sub = args[0];
  switch (sub) {
    case "health":     return showDiagHealth();
    case "issues":     return showDiagIssues();
    case "runners":    return showDiagRunners();
    case "visibility": return showDiagVisibility();
    case "live":       return showDiagLive(args.slice(1));
    case "publish":    return publishDiag(args.slice(1));
    case "mode":       return startDiagMode(args.slice(1));
    default:           return showDiag();
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

\x1b[1mFederation:\x1b[0m
  nodes                   List federation nodes
  msg <node|all> <text>   Send message (accepts name, alias: mac/win)
  cmd <node|all> <cmd>    Send command: update, status, restart, pause
  inbox                   Read your messages
  listen                  Real-time event stream

\x1b[1mContributors:\x1b[0m
  contributors [limit]    List contributors
  contributor <id>        View contributor detail
  contributor <id> contributions  View contributions

\x1b[1mTasks (agent work protocol):\x1b[0m
  tasks [status] [limit]  List tasks (pending, running, completed)
  task <id>               View task detail
  task next               Claim highest-priority pending task
  task claim <id>         Claim a specific task
  task report <id> <completed|failed> [output]  Report result
  task seed <idea> [type] Create task from idea (spec|test|impl|review)

\x1b[1mAssets:\x1b[0m
  assets [limit]          List assets
  asset <id>              View asset detail
  asset create <type> <desc>  Create an asset

\x1b[1mNews:\x1b[0m
  news                    News feed
  news trending           Trending news
  news sources            List news sources
  news source add <url> <name>  Add a news source
  news resonance [contributor]  News resonance

\x1b[1mTreasury:\x1b[0m
  treasury                Treasury overview
  treasury deposits <id>  Deposits for contributor
  treasury deposit <amt> <asset>  Make a deposit

\x1b[1mLineage:\x1b[0m
  lineage [limit]         Value lineage links
  lineage <id>            View lineage link
  lineage <id> valuation  Link valuation
  lineage <id> payout <amt>  Payout preview

\x1b[1mGovernance:\x1b[0m
  governance              List change requests
  governance <id>         View change request
  governance vote <id> <yes|no>  Vote on change request
  governance propose <title> <desc>  Create proposal

\x1b[1mServices:\x1b[0m
  services                List services
  service <id>            View service detail
  services health         Services health check
  services deps           Service dependencies

\x1b[1mFriction:\x1b[0m
  friction                Friction report
  friction events [limit] Friction events
  friction categories     Friction categories

\x1b[1mProviders:\x1b[0m
  providers               List providers
  providers stats         Provider statistics

\x1b[1mTraceability:\x1b[0m
  trace                   Traceability overview
  trace coverage          Traceability coverage
  trace idea <id>         Trace an idea
  trace spec <id>         Trace a spec

\x1b[1mDiagnostics:\x1b[0m
  diag                    Agent effectiveness + pipeline
  diag health             Collective health
  diag issues             Fatal + monitor issues
  diag runners            Agent runners
  diag visibility         Agent visibility

\x1b[2mHub: https://api.coherencycoin.com\x1b[0m
\x1b[2mDocs: https://coherencycoin.com\x1b[0m
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
