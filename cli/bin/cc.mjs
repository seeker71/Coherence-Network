#!/usr/bin/env node

/**
 * cc — Coherence Network CLI
 *
 * Identity-first contributions, idea staking, and value traceability.
 * Zero dependencies. Node 18+ required.
 */

import { appendFileSync } from "node:fs";
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
import { handleRest } from "../lib/commands/rest.mjs";
import { showTraceability, showCoverage, traceIdea, traceSpec } from "../lib/commands/traceability.mjs";
import { showDiag, showDiagHealth, showDiagIssues, showDiagRunners, showDiagVisibility, showDiagLive } from "../lib/commands/diagnostics.mjs";
import { publishDiag, startDiagMode } from "../lib/commands/diag_publish.mjs";
import { handleOps } from "../lib/commands/ops.mjs";
import { handleConfig } from "../lib/commands/config_editor.mjs";
import { showMetaSummary, showMetaEndpoints, showMetaModules } from "../lib/commands/meta.mjs";
import { deploy } from "../lib/commands/deploy.mjs";
import { listen } from "../lib/commands/listen.mjs";
import { update } from "../lib/commands/update.mjs";
import { handleAgent } from "../lib/commands/agent.mjs";
import {
  listTasks,
  showTask,
  claimTask,
  claimNext,
  reportTask,
  seedTask,
  showTaskCount,
  showTaskEvents,
  postProgress,
  streamStart,
  watchTask,
} from "../lib/commands/tasks.mjs";
import { showPortfolio } from "../lib/commands/portfolio.mjs";
import { listEntityEdges, listEdgeTypes, createEdge, deleteEdge } from "../lib/commands/edges.mjs";
import { listConcepts, showConcept, linkConcepts } from "../lib/commands/concepts.mjs";
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
import { marketplacePublish, marketplaceBrowse, marketplaceFork } from "../lib/commands/marketplace.mjs";
import { listGraphNodes, createGraphNode, listGraphEdges, createGraphEdge, getGraphNeighbors } from "../lib/commands/graph.mjs";
import { onboardingRegister, onboardingSession, onboardingUpgrade } from "../lib/commands/onboarding.mjs";
import { credentialsAdd, credentialsList, credentialsRemove } from "../lib/commands/credentials.mjs";
import { guide } from "../lib/commands/guide.mjs";
import { runFocusCommand } from "../lib/commands/focus.mjs";
import { runPeersCommand } from "../lib/commands/peers.mjs";
import { runCollabCommand } from "../lib/commands/collab.mjs";
import { runOrgCommand } from "../lib/commands/org.mjs";
import { runBlueprintsCommand } from "../lib/commands/blueprints.mjs";
import { runSkillsCommand } from "../lib/commands/skills.mjs";
import { runGuidesCommand } from "../lib/commands/guides.mjs";
import { debugCommand } from "../lib/commands/debug.mjs";
import { modelsCommand, usageCommand } from "../lib/commands/models.mjs";
import { handleWorkspace } from "../lib/commands/workspaces.mjs";
import {
  setActiveWorkspaceOverride,
  setApiUrlOverride,
  setApiKeyOverride,
  setTimeoutOverride,
} from "../lib/config.mjs";
import { basename } from 'path';

// Deprecation warning when invoked as `cc` (shadows /usr/bin/cc on macOS/Linux)
const _invokedAs = basename(process.argv[1] || '');
if (_invokedAs === 'cc') {
  process.stderr.write(
    '\x1b[33m[coherence-cli] Warning: `cc` shadows the system C compiler.\n' +
    'Use `coh` instead — it\'s the same CLI without the conflict.\n\x1b[0m'
  );
}

// Extract global flags before dispatching. Each flag sets an in-process
// override; per-invocation env vars (COHERENCE_API_URL, COHERENCE_API_KEY,
// COHERENCE_TIMEOUT_MS) are honored by the resolvers in config.mjs when no
// override is set. The persistent workspace default lives in config.json
// under the `workspace` key (set via `cc workspace use <id>`).
//
//   --workspace <id>    Scope commands to a specific workspace for this run.
//   --api-url <url>     Override the API origin (alternative: COHERENCE_API_URL).
//   --api-key <key>     Override the API key (alternative: COHERENCE_API_KEY).
//   --timeout <ms>      Override the request timeout (alternative: COHERENCE_TIMEOUT_MS).
function _extractGlobalFlags(argv) {
  const out = [];
  const TAKES_VALUE = new Set(["--workspace", "--api-url", "--api-key", "--timeout"]);
  const APPLY = {
    "--workspace": setActiveWorkspaceOverride,
    "--api-url": setApiUrlOverride,
    "--api-key": setApiKeyOverride,
    "--timeout": setTimeoutOverride,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (TAKES_VALUE.has(a) && i + 1 < argv.length) {
      APPLY[a](argv[++i]);
      continue;
    }
    // --flag=value form
    let matched = false;
    for (const flag of TAKES_VALUE) {
      const prefix = `${flag}=`;
      if (a.startsWith(prefix)) {
        APPLY[flag](a.slice(prefix.length));
        matched = true;
        break;
      }
    }
    if (matched) continue;
    out.push(a);
  }
  return out;
}
const _rawArgv = process.argv.slice(2);
const _filtered = _extractGlobalFlags(_rawArgv);
const [command, ...args] = _filtered;

function debugPytest(message) {
  if (!process.env.PYTEST_CURRENT_TEST) return;
  try {
    appendFileSync("/tmp/coherence-cc-pytest.log", `${new Date().toISOString()} ${message}\n`);
  } catch {}
}

debugPytest(`argv=${JSON.stringify(process.argv.slice(1))}`);

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
   friction:      () => handleFriction(args),
   providers:     () => handleProviders(args),
   rest:          () => handleRest(args),
   trace:         () => handleTrace(args),   diag:          () => handleDiag(args),
   dif:           () => handleDif(args),
   marketplace:   () => handleMarketplace(args),
   graph:         () => handleGraph(args),
   onboarding:    () => handleOnboarding(args),
   credentials:   () => handleCredentials(args),
   guide:         () => guide(args),
  focus:         () => runFocusCommand(args),
  f:             () => runFocusCommand(args),
  peers:         () => runPeersCommand(args),
  collab:        () => runCollabCommand(args),
  org:           () => runOrgCommand(args),
  blueprints:    () => runBlueprintsCommand(args),
  blueprint:     () => runBlueprintsCommand(args),
  skills:        () => runSkillsCommand(args),
  guides:        () => runGuidesCommand(args),
   setup:         () => setup(args),
  whoami:        () => showWhoami(),
  tasks:         () => listTasks(args),
  task:          () => handleTask(args),
  login:         () => handleLogin(args),
  logout:        () => handleLogout(args),
  auth:          () => handleAuth(args),
  ops:           () => handleOps(args),
  config:        () => handleConfig(args),
  progress:      () => postProgress(args),
  stream:        () => streamStart(args),
  watch:         () => watchTask(args),
  live:          () => watchTask(args),
  debug:         () => debugCommand(args),
  models:        () => modelsCommand(args),
  usage:         () => usageCommand(args),
  agent:         () => handleAgent(args),
  meta:          () => handleMeta(args),
  concepts:      () => listConcepts(args),
  concept:       () => handleConcept(args),
  nearby:        () => showNearby(args),
  location:      () => handleLocation(args),
  portfolio:     () => showPortfolio(),
  workspace:     () => handleWorkspace(args),
  workspaces:    () => handleWorkspace(["list", ...args]),
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

async function handleConcept(args) {
  if (args[0] === "link") return linkConcepts(args.slice(1));
  return showConcept(args);
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
    case "count":   return showTaskCount();
    case "events":  return showTaskEvents(args.slice(1));
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

async function handleMarketplace(args) {
   const sub = args[0];
   switch (sub) {
      case "publish": return marketplacePublish(args.slice(1));
      case "browse":  return marketplaceBrowse(args.slice(1));
      case "fork":    return marketplaceFork(args.slice(1));
      default:
         console.log("Usage: cc marketplace <publish|browse|fork>");
         console.log("  cc marketplace publish --idea-id <id> --tags <tags> --author <name>");
         console.log("  cc marketplace browse --page <n> --sort <recent|popular|value>");
         console.log("  cc marketplace fork --listing-id <id> --forker-id <id>");
   }
}

async function handleGraph(args) {
   const sub = args[0];
   switch (sub) {
      case "nodes":   return listGraphNodes(args.slice(1));
      case "edges":   return listGraphEdges(args.slice(1));
      case "neighbors": return getGraphNeighbors(args.slice(1));
      default:
         console.log("Usage: cc graph <nodes|edges|neighbors>");
         console.log("  cc graph nodes list|create");
         console.log("  cc graph edges list|create|neighbors");
         console.log("  cc graph neighbors --node-id <id>");
   }
}

async function handleOnboarding(args) {
   const sub = args[0];
   switch (sub) {
      case "register": return onboardingRegister(args.slice(1));
      case "session":  return onboardingSession(args.slice(1));
      case "upgrade":  return onboardingUpgrade(args.slice(1));
      default:
         console.log("Usage: cc onboarding <register|session|upgrade>");
  }
}

async function handleCredentials(args) {
  const sub = args[0];
  switch (sub) {
    case "add":    return credentialsAdd(args.slice(1));
    case "list":   return credentialsList(args.slice(1));
    case "remove": return credentialsRemove(args.slice(1));
    default:
      console.log("Usage: cc credentials <add|list|remove>");
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

import { getHubUrl } from "../lib/config.mjs";

function showHelp() {
  const hubUrl = getHubUrl();
  console.log(`
\x1b[1mcc\x1b[0m — Coherence Network CLI

\x1b[1mUsage:\x1b[0m cc <command> [args]

\x1b[1mExplore:\x1b[0m
  focus                   Interactive idea picker to set active focus
  focus <id>              Set active focus non-interactively
  peers                   Discover contributors by resonance or proximity
  peers --nearby          Focus on geographic proximity
  peers --resonance       Focus on shared interests
  skills                  Browse the network's procedural memory library
  guides                  Discover top creators and thought leaders
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
  blueprints              List project roadmap templates
  blueprint apply <id>    Seed a full roadmap from a template
  contribute              Record contribution (interactive)
  contribute --type code --cc 5 --idea <id> --desc "what I did"
  collab                  Interactive collaboration dashboard for focused idea
  collab broadcast        Signal interest in focused idea to others
  collab list             List active collaborators for focused idea
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
  org                     Show agent hierarchy and reporting lines
  credentials             Manage repo-specific tokens (add, list, remove)
  guide                   Guided experience for new contributors

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
  ops [--snapshot|--json] Operator diagnostics snapshot
  ops                     Interactive diagnostics console
  ops --watch 5           Refresh operator snapshot every 5 seconds
  ops events <task_id>    Show stored task activity events
  ops events <task_id> --follow  Stream live task events
  ops runner <target> <pause|resume|restart|status>  Dispatch runner command
  tasks [status] [limit]  List tasks (pending, running, completed)
  task <id>               View task detail
  task next               Claim highest-priority pending task
  task claim <id>         Claim a specific task
  task report <id> <completed|failed> [output]  Report result
  task seed <idea> [type] Create task from idea (spec|test|impl|review)
  task count              JSON task counts (/api/agent/tasks/count)
  task events <id> [N]    Paginated activity events for a task

\x1b[1mConfig:\x1b[0m
  config show             Show remote allowlisted config
  config set <path> <value>   Update remote allowlisted config
  config unset <path>         Clear remote allowlisted config field
  config edit             Guided remote config editor
  config show --local     Show ~/.coherence-network/config.json
  config set <path> <value> --local  Update local config file

\x1b[1mUniversal API (full coverage):\x1b[0m
  rest coverage           Canonical route count + proof JSON
  rest GET /api/...       Raw authenticated GET (any path)
  rest POST /api/... --body '{"k":"v"}'   Raw POST/PATCH/PUT/DELETE
  rest ... -q limit=10 -H "X-Custom: 1"   Query + extra headers

\x1b[1mAgent pipeline:\x1b[0m
  agent                   Status report (default)
  agent route [type]      Routing hint for task_type (default impl)
  agent execute <id>      POST execute (set AGENT_EXECUTE_TOKEN)
  agent pickup [task_id]  Pickup-and-execute pending task
  agent smart-reap        Preview; agent smart-reap run
  agent metrics|issues|effectiveness|...  (see agent.mjs)

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

   \x1b[1mMarketplace:\x1b[0m
   marketplace publish     Publish an idea to the cross-instance marketplace
   marketplace browse      Browse marketplace listings
   marketplace fork        Fork a marketplace listing

   \x1b[1mGraph:\x1b[0m
   graph nodes             Manage universal graph nodes (list, create)
   graph edges             Manage universal graph edges (list, create, neighbors)

   \x1b[1mOnboarding:\x1b[0m
   onboarding register     Register a new contributor (Trust-on-First-Use)
   onboarding session      Get contributor profile from session token
   onboarding upgrade      Upgrade trust level to verified (stub)

\x1b[2mHub: ${hubUrl}\x1b[0m
\x1b[2mDocs: https://coherencycoin.com\x1b[0m
`);
}

async function main() {
  const handler = COMMANDS[command];
  debugPytest(`command=${String(command)} args=${JSON.stringify(args)} handler=${handler ? "yes" : "no"}`);
  if (handler) {
    await handler();
    debugPytest(`command=${String(command)} completed`);
    await new Promise((resolve) => process.stdout.write("", resolve));
    await new Promise((resolve) => process.stderr.write("", resolve));
    return;
  }
  if (!command) {
    debugPytest("showHelp(no-command)");
    showHelp();
    return;
  }
  debugPytest(`unknown-command=${String(command)}`);
  console.log(`Unknown command: ${command}`);
  console.log("Run 'cc help' for available commands.");
  process.exit(1);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
