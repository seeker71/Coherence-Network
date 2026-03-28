#!/usr/bin/env node

/**
 * cc — Coherence Network CLI
 *
 * Identity-first contributions, idea staking, and value traceability.
 * Zero dependencies. Node 18+ required.
 */

import {
  listIdeas, showIdea, shareIdea, stakeOnIdea, forkIdea, createIdea,
  triageIdeas, setIdeaWorkType, linkIdea, showIdeaChildren, showIdeaDeps,
  showIdeaTags, showIdeaHealth, showIdeaShowcase, showIdeaResonance,
  showIdeasProgress, showIdeasCount,
  archiveIdea, retireIdea, showStaleIdeas,
} from "../lib/commands/ideas.mjs";
import { listSpecs, showSpec } from "../lib/commands/specs.mjs";
import { contribute } from "../lib/commands/contribute.mjs";
import { ontology } from "../lib/commands/ontology.mjs";
import { showStatus, showResonance } from "../lib/commands/status.mjs";
import { showIdentity, linkIdentity, unlinkIdentity, lookupIdentity, setupIdentity, setIdentity } from "../lib/commands/identity.mjs";
import { setup } from "../lib/commands/setup.mjs";
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
import { showMetaSummary, showMetaEndpoints, showMetaModules } from "../lib/commands/meta.mjs";
import { deploy } from "../lib/commands/deploy.mjs";
import { listen } from "../lib/commands/listen.mjs";
import { update } from "../lib/commands/update.mjs";
import { listTasks, showTask, claimTask, claimNext, reportTask, seedTask, postProgress, streamStart, watchTask } from "../lib/commands/tasks.mjs";
import { showPortfolio } from "../lib/commands/portfolio.mjs";
import { listEntityEdges, listEdgeTypes, createEdge, deleteEdge } from "../lib/commands/edges.mjs";
import { showNearby, handleLocation } from "../lib/commands/geolocation.mjs";
import {
  showConfig as difConfig, setBaseUrl as difSetBaseUrl,
  whoami as difWhoami, verify as difVerify, smoke as difSmoke,
  keyList as difKeyList, keyCreate as difKeyCreate, keyRevoke as difKeyRevoke,
  keyRotate as difKeyRotate, keyUpdate as difKeyUpdate, keyUse as difKeyUse, keyShow as difKeyShow,
  keyEnsure as difKeyEnsure, keyStatus as difKeyStatus,
  showUsage as difUsage, showLimits as difLimits, showFunding as difFunding,
  showFeedback as difFeedback,
} from "../lib/commands/dif.mjs";
import { basename } from 'path';

// Deprecation warning when invoked as `cc` (shadows /usr/bin/cc on macOS/Linux)
const _invokedAs = basename(process.argv[1] || '');
if (_invokedAs === 'cc') {
  process.stderr.write(
    '\x1b[33m[coherence-cli] Warning: `cc` shadows the system C compiler.\n' +
    'Use `coh` instead — it\'s the same CLI without the conflict.\n\x1b[0m'
  );
}

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
  ontology:      () => ontology(args),
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
  edges:         () => listEntityEdges(args),
  edg:           () => listEntityEdges(args),
  edge:          () => handleEdge(args),
  update:        () => update(args),
  deploy:        () => deploy(args),
  listen:        () => listen(args),
  dif:           () => handleDif(args),
  setup:         () => setup(args),
  whoami:        () => showWhoami(),
  login:         () => handleLogin(args),
  logout:        () => handleLogout(args),
  auth:          () => handleAuth(args),
  // ─── New commands: inventory, runtime, federation ────────────────────
  inventory:     () => handleInventory(args),
  pipeline:      () => handlePipeline(args),
  runtime:       () => handleRuntime(args),
  federation:    () => handleFederation(args),
  // ─── Value lineage shortcuts ──────────────────────────────────────────
  link:          () => handleLink(args),
  progress:      () => postProgress(args),
  stream:        () => streamStart(args),
  watch:         () => watchTask(args),
  meta:          () => handleMeta(args),
  nearby:        () => showNearby(args),
  location:      () => handleLocation(args),
  portfolio:     () => showPortfolio(),
  help:          () => showHelp(),
};

async function handleMeta(args) {
  const sub = args[0];
  switch (sub) {
    case "endpoints": return showMetaEndpoints(args.slice(1));
    case "modules":   return showMetaModules(args.slice(1));
    default:          return showMetaSummary();
  }
}

async function handleIdea(args) {
  const sub = args[0];
  switch (sub) {
    case "create":   return createIdea(args.slice(1));
    case "triage":   return triageIdeas(args.slice(1));
    case "tags":     return showIdeaTags();
    case "health":   return showIdeaHealth();
    case "showcase": return showIdeaShowcase();
    case "resonance":return showIdeaResonance();
    case "progress": return showIdeasProgress();
    case "count":    return showIdeasCount();
    case "stale":    return showStaleIdeas(args.slice(1));
    default:         return showIdea(args);  // routes sub-subcommands internally
  }
}

async function handleEdge(args) {
  const sub = args[0];
  const subArgs = args.slice(1);
  switch (sub) {
    case "create": return createEdge(subArgs);
    case "delete": return deleteEdge(subArgs);
    case "types":  return listEdgeTypes();
    default:
      console.log("Usage: cc edge <create|delete|types>");
      console.log("  cc edge create <from-id> <type> <to-id>");
      console.log("  cc edge delete <edge-id>");
      console.log("  cc edge types");
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
    case "stake":    return stakeDeposit(args.slice(1));
    default:         return showTreasury();
  }
}

async function handleLineage(args) {
  if (!args[0]) return listLinks([]);
  if (args[0] === "create") return createLink(args.slice(1));
  if (args[0] === "usage")  return addUsageEvent(args.slice(1));
  if (args[0] === "e2e")    return runMinimumE2EFlow();
  if (args[1] === "valuation") return showValuation(args);
  if (args[1] === "payout") return payoutPreview([args[0], args[2]]);
  if (args[1] === "usage")  return addUsageEvent([args[0], ...args.slice(2)]);
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

async function showWhoami() {
  const { get } = await import("../lib/api.mjs");
  const { loadKeys } = await import("../lib/config.mjs");
  const keys = loadKeys();
  const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", Y = "\x1b[33m";
  console.log(`\n${B}  WHOAMI${R}`);
  console.log(`  ${"─".repeat(40)}`);
  if (keys.contributor_id) {
    console.log(`  Contributor: ${B}${keys.contributor_id}${R}`);
    if (keys.provider) console.log(`  Identity:    ${keys.provider}:${keys.provider_id}`);
    if (keys.api_key) console.log(`  API key:     ${keys.api_key.slice(0, 16)}...`);
    const data = await get("/api/auth/whoami");
    if (data?.authenticated) {
      console.log(`  Network:     ${G}authenticated${R}`);
      if (data.scopes) console.log(`  Scopes:      ${D}${data.scopes.join(", ")}${R}`);
    } else {
      console.log(`  Network:     ${Y}key not recognized by server${R}`);
    }
  } else {
    console.log(`  ${Y}Not set up yet.${R} Run: cc setup`);
  }
  console.log();
}

async function handleLogin(args) {
  const provider = (args[0] || "merly").toLowerCase();
  if (provider !== "merly") {
    console.log(`Unknown login provider: ${provider}. Supported: merly`);
    return;
  }
  const { loginDeviceFlow } = await import("../lib/merly_auth.mjs");
  await loginDeviceFlow();
}

async function handleLogout(args) {
  const provider = (args[0] || "merly").toLowerCase();
  if (provider !== "merly") {
    console.log(`Unknown provider: ${provider}. Supported: merly`);
    return;
  }
  const { clearMerlySession } = await import("../lib/merly_auth.mjs");
  clearMerlySession();
  console.log("  \x1b[32m✓\x1b[0m Logged out of Merly");
}

async function handleAuth(args) {
  const sub = (args[0] || "status").toLowerCase();
  const jsonMode = args.includes("--json");

  if (sub === "status") {
    const { getMerlySession, isLoggedIn, getIdentity } = await import("../lib/merly_auth.mjs");
    const { getDifKey } = await import("../lib/dif.mjs");

    const session = getMerlySession();
    const loggedIn = isLoggedIn();
    const key = getDifKey();

    if (jsonMode) {
      const result = {
        merly: {
          authenticated: loggedIn,
          access_token: loggedIn ? "present" : null,
          identity: session?.identity || null,
          logged_in_at: session?.logged_in_at || null,
          expires_at: session?.expires_at ? new Date(session.expires_at).toISOString() : null,
        },
        dif: {
          key_configured: !!key.api_key,
          key_id: key.key_id || null,
          source: key.source || null,
        },
      };
      console.log(JSON.stringify(result, null, 2));
    } else {
      const B = "\x1b[1m", D = "\x1b[2m", R = "\x1b[0m", G = "\x1b[32m", RED = "\x1b[31m";
      console.log(`\n${B}  AUTH STATUS${R}`);
      console.log(`  ${"─".repeat(50)}`);
      console.log(`  Merly:     ${loggedIn ? G + "logged in" + R : RED + "not logged in" + R}`);
      if (session?.identity) {
        const id = session.identity;
        console.log(`  Identity:  ${id.display_name || id.email || id.contributor_id || "?"}`);
      }
      console.log(`  DIF key:   ${key.api_key ? G + "configured" + R : D + "not set" + R}`);
      if (key.api_key) {
        console.log(`  Key ID:    ${key.key_id || "?"}`);
      }
      console.log();
    }
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
        case "ensure": return difKeyEnsure();
        case "status": return difKeyStatus();
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
  portfolio               Ideas by category — gap, streak, effort, new experiences
  ideas [limit]           Browse ideas by ROI
  ideas --type <type>     Filter by work_type (feature|bug-fix|enhancement|exploration|research|prototype|mvp)
  ideas --status <s>      Filter by status (none|partial|validated)
  ideas --parent <id>     Filter by parent idea
  idea triage             Ranked ready-to-work list (by free-energy score)
  idea <id>               View idea detail (work_type, parent, children, phase)
  idea create <id> <name> [--desc "..." --value N --cost N --parent <id>]
  idea <id> type <t>      Set work type
  idea <id> link <r> <t>  Link ideas: blocks|enables|supersedes|depends-on|related-to
  idea <id> deps              Show dependency edges (blocks/enables/supersedes)
  idea <id> deps --type blocks  Filter by relation type
  idea <id> children      List child ideas
  idea <id> tasks         Show tasks for an idea
  idea <id> stage <s>     Set stage
  idea <id> question <q>  Add open question
  idea <id> answer <a>    Answer open question
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
  setup                   Interactive onboarding — creates contributor + API key
  setup --reset           Re-run setup (replace existing key)
  whoami                  Show authenticated contributor + key status
  identity                Show your linked accounts
  identity set <contributor_id>  Set identity non-interactively
  identity link <p> <id>  Link a provider (github, discord, ethereum, ...)
  identity unlink <p>     Unlink a provider
  identity lookup <p> <id> Find contributor by identity
  COHERENCE_CONTRIBUTOR_ID overrides config.json for per-process agent identity

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
  treasury deposit <amt> <asset> [contributor]  Make a deposit
  treasury stake <deposit-id> <idea-id> [amt]   Stake deposit on idea

\x1b[1mLineage:\x1b[0m
  lineage [limit]         Value lineage links
  lineage <id>            View lineage link
  lineage <id> valuation  Link valuation
  lineage <id> payout <amt>  Payout preview
  lineage create <idea> <spec> [contributor] [weight]  Create link
  lineage <id> usage <event-type> [amount]  Record usage event
  lineage e2e             Run minimum E2E value flow
  link create|usage|e2e   Shorthand aliases

\x1b[1mEdge Navigation:\x1b[0m
  edges <id>              List all edges for an entity (alias: edg)
  edg <id>                Shorthand alias for cc edges
  edges <id> --type <t>  Filter edges by relationship type
  edge types              Print all 46 canonical edge types
  edge create <from> <type> <to>  Create a typed edge
  edge delete <edge-id>   Delete an edge

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

\x1b[1mAuth:\x1b[0m
  login merly             Log into Merly (browser OAuth)
  logout merly            Clear Merly session
  auth status [--json]    Show auth + DIF key status

\x1b[1mDIF:\x1b[0m
  dif verify --language <lang> --code <code> | --file <path>
  dif key ensure          Bootstrap DIF key from Merly
  dif key status          Show DIF key + Merly auth status
  dif key list            List DIF API keys
  dif key create [name]   Create DIF key manually
  dif whoami              DIF identity check
  dif config              Show DIF configuration
  dif smoke               Run DIF smoke test

\x1b[1mDiagnostics:\x1b[0m
  diag                    Agent effectiveness + pipeline
  diag health             Collective health
  diag issues             Fatal + monitor issues
  diag runners            Agent runners
  diag visibility         Agent visibility

\x1b[1mInventory / Pipeline:\x1b[0m
  inventory               Pipeline pulse + flow overview
  inventory pulse         Live pipeline health
  inventory flow          Full pipeline flow details
  inventory completeness  Process completeness by stage
  inventory gaps          Traceability gaps
  inventory routes        Canonical route manifest
  inventory endpoints     Endpoint traceability (S/T/I coverage)
  inventory evidence      Route and commit evidence
  inventory assets        Asset modularity report
  inventory lineage       System lineage summary
  inventory fix-hollow    Fix hollow completions
  pipeline pulse          Alias: pipeline pulse
  pipeline fix-hollow     Alias: fix hollow completions

\x1b[1mRuntime Monitoring:\x1b[0m
  runtime                 Change token + overview
  runtime events [N]      List runtime events
  runtime event <type> [data]  Post runtime event
  runtime ideas           Runtime summary by idea
  runtime endpoints       Endpoints coverage summary
  runtime web             Web view performance
  runtime attention       Endpoints needing attention
  runtime exerciser       Run endpoint exerciser
  runtime usage           Usage verification
  runtime mvp             MVP acceptance summary
  runtime mvp judge       MVP acceptance judge
  runtime mvp baselines   Local baselines
  runtime token           Current change token

\x1b[1mFederation (extended):\x1b[0m
  federation              List federation nodes
  federation nodes        List registered nodes
  federation instances    List federated instances
  federation instance <id>  Show instance detail
  federation register <url> [caps...]  Register a new node
  federation heartbeat <id>  Send heartbeat for node
  federation capabilities  Fleet capability summary
  federation stats        Aggregated node stats
  federation sync         Trigger federation sync
  federation sync history Sync history
  federation aggregates   Federated aggregations
  federation msg <id> <text>  Send message to a node
  federation msgs <id>    Read messages from a node
  federation broadcast <text>  Broadcast to all nodes

\x1b[1mIdea (extended):\x1b[0m
  idea tags               List all tags in the catalog
  idea tag <id> <tag...>  Set tags on an idea
  idea health             Governance health
  idea showcase           Showcase ideas
  idea resonance          Ideas resonance overview
  idea progress           Progress dashboard
  idea count              Total idea count
  idea <id> activity      Activity for an idea
  idea <id> tasks         Tasks for an idea
  idea <id> advance       Advance idea to next stage
  idea <id> stage <s>     Set idea stage explicitly
  idea <id> question <q>  Add question to idea
  idea <id> answer <a>    Answer an open question
  idea <id> resonance     Concept resonance for idea

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
