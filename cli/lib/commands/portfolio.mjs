/**
 * Portfolio command: cc portfolio
 *
 * Single-query overview of all ideas by category showing:
 *   - idea count, gap (CC), value capture %
 *   - task streak (consecutive recent completions in that category)
 *   - task type mix for the category (spec / impl / test / review)
 *   - top new experiences (recently validated ideas)
 *   - effort breakdown (avg duration per task type)
 */

import { get } from "../api.mjs";

// ── colour / format helpers ────────────────────────────────────────────────

const B  = "\x1b[1m";
const D  = "\x1b[2m";
const R  = "\x1b[0m";
const G  = "\x1b[32m";
const Y  = "\x1b[33m";
const C  = "\x1b[36m";
const M  = "\x1b[35m";
const RED= "\x1b[31m";

function hr(w = 70) { return "─".repeat(w); }

function pad(s, n, right = false) {
  const str = String(s ?? "");
  return right ? str.padStart(n) : str.padEnd(n);
}

function fmtCC(n) {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n));
}

function fmtDur(secs) {
  if (!secs) return "—";
  if (secs < 60) return `${Math.round(secs)}s`;
  const m = Math.floor(secs / 60), s = Math.round(secs % 60);
  return s > 0 ? `${m}m${s}s` : `${m}m`;
}

function streakBar(n, max = 8, width = 5) {
  const filled = Math.min(Math.round((n / Math.max(max, 1)) * width), width);
  return G + "■".repeat(filled) + R + D + "□".repeat(width - filled) + R;
}

function valBadge(pct) {
  if (pct >= 80) return G + `${pct}%` + R;
  if (pct >= 50) return Y + `${pct}%` + R;
  return RED + `${pct}%` + R;
}

// ── category classifier (mirrors the Python one used for gap analysis) ─────

const CATEGORIES = [
  { name: "Runner & Pipeline",      kw: ["runner","pipeline","task","worker","phase","worktree","deploy","prompt","seeder","reaper"] },
  { name: "Graph & Ontology",       kw: ["graph","ontology","neo4j","node","edge","resonan","concept","federation","ontol"] },
  { name: "Web & UX",               kw: ["web","ui","ux","frontend","dashboard","component","page","display","showcase","homepage","navigation"] },
  { name: "Validation/Testing",     kw: ["test","validat","qa","verify","ci","coverage","proof"] },
  { name: "Identity/Contributors",  kw: ["contributor","identity","auth","attribution","wallet","cc-mint","coin","credit","minting"] },
  { name: "CLI/MCP",                kw: ["cli","mcp","command","autocomplete","registry"] },
  { name: "Economics",              kw: ["econom","reward","incentiv","treasury","staking","distribution"] },
  { name: "News/Content",           kw: ["news","content","post","blog","publish"] },
];

function classify(idea) {
  const txt = ((idea.name || "") + " " + (idea.description || "")).toLowerCase();
  for (const cat of CATEGORIES) {
    if (cat.kw.some(k => txt.includes(k))) return cat.name;
  }
  return "Other";
}

// ── extract idea_id from a task direction string ───────────────────────────
function extractIdeaId(direction) {
  if (!direction) return null;
  const m = direction.match(/\(([a-z0-9][a-z0-9-]{2,})\)[.\n]/);
  return m ? m[1] : null;
}

// ── relative time helper ──────────────────────────────────────────────────

function relativeTime(iso) {
  try {
    const ms  = Date.now() - new Date(iso).getTime();
    const min = Math.floor(ms / 60_000);
    const hr  = Math.floor(min / 60);
    const day = Math.floor(hr / 24);
    if (day > 0) return `${day}d ago`;
    if (hr  > 0) return `${hr}h ago`;
    if (min > 0) return `${min}m ago`;
    return "just now";
  } catch {
    return "?";
  }
}

// ── main ──────────────────────────────────────────────────────────────────

/**
 * showIdeaPortfolio()
 * Network-wide idea portfolio by category.
 */
export async function showIdeaPortfolio() {
  // Parallel fetch: ideas + pipeline status (has recent tasks + task type counts)
  const [ideasRaw, pipeline, effectiveness] = await Promise.all([
    get("/api/ideas", { limit: 400, lifecycle: "active" }),
    get("/api/agent/pipeline-status"),
    get("/api/agent/effectiveness"),
  ]);

  const ideas = Array.isArray(ideasRaw) ? ideasRaw : (ideasRaw?.ideas ?? []);

  // ── aggregate ideas by category ─────────────────────────────────────────
  const cats = {};
  for (const name of [...CATEGORIES.map(c => c.name), "Other"]) {
    cats[name] = { name, ideas: [], pot: 0, act: 0 };
  }
  for (const idea of ideas) {
    const cat = cats[classify(idea)];
    cat.ideas.push(idea);
    cat.pot += idea.potential_value || 0;
    cat.act += idea.actual_value    || 0;
  }

  // sort categories by gap descending
  const sorted = Object.values(cats)
    .filter(c => c.ideas.length > 0)
    .sort((a, b) => (b.pot - b.act) - (a.pot - a.act));

  // ── task data from pipeline status ──────────────────────────────────────
  const recentTasks  = pipeline?.recent_completed ?? [];
  const runningTasks = (pipeline?.running ?? []);
  const allRecentTasks = [...runningTasks, ...recentTasks];

  const ideaToCategory = {};
  for (const idea of ideas) {
    ideaToCategory[idea.id] = classify(idea);
    if (idea.slug) ideaToCategory[idea.slug] = classify(idea);
  }

  const catTaskCounts = {};
  for (const c of sorted) {
    catTaskCounts[c.name] = { spec:0, impl:0, test:0, review:0, heal:0, total:0 };
  }

  for (const t of allRecentTasks) {
    const ideaId = extractIdeaId(t.direction);
    const catName = ideaId ? ideaToCategory[ideaId] : null;
    if (catName && catTaskCounts[catName]) {
      const tt = t.task_type || "other";
      catTaskCounts[catName][tt] = (catTaskCounts[catName][tt] || 0) + 1;
      catTaskCounts[catName].total += 1;
    }
  }

  const catStreaks = {};
  const streakWindow = recentTasks.slice(0, 20);
  for (const c of sorted) catStreaks[c.name] = 0;
  for (const c of sorted) {
    let streak = 0;
    for (const t of streakWindow) {
      const ideaId = extractIdeaId(t.direction);
      if (ideaId && ideaToCategory[ideaId] === c.name) streak++;
    }
    catStreaks[c.name] = streak;
  }

  const effortByType = {};
  for (const t of recentTasks) {
    if (t.duration_seconds && t.duration_seconds > 0) {
      const tt = t.task_type || "other";
      effortByType[tt] = effortByType[tt] || [];
      effortByType[tt].push(t.duration_seconds);
    }
  }
  const progressTotals = effectiveness?.progress || {};

  const validated = ideas
    .filter(i => i.manifestation_status === "validated" && (i.actual_value || 0) > 0)
    .sort((a, b) => (b.last_activity_at || "").localeCompare(a.last_activity_at || ""))
    .slice(0, 8);

  const totalPot  = sorted.reduce((s, c) => s + c.pot, 0);
  const totalAct  = sorted.reduce((s, c) => s + c.act, 0);
  const totalGap  = totalPot - totalAct;
  const totalPct  = totalPot > 0 ? Math.round(100 * totalAct / totalPot) : 0;

  console.log();
  console.log(`${B}  NETWORK PORTFOLIO${R}  ${D}${ideas.length} active ideas · ${fmtCC(totalGap)} CC gap · ${valBadge(totalPct)} captured${R}`);
  console.log(`  ${hr(72)}`);

  const COL = [24, 4, 7, 5, 5, 22];
  console.log(`  ${D}${pad("Category", COL[0])} ${pad("N", COL[1], true)} ${pad("Gap CC", COL[2], true)} ${pad("Val%", COL[3], true)} ${pad("Streak", COL[4], true)}  Task mix (recent)${R}`);
  console.log(`  ${hr(72)}`);

  for (const c of sorted) {
    const gap  = c.pot - c.act;
    const pct  = c.pot > 0 ? Math.round(100 * c.act / c.pot) : 0;
    const tc   = catTaskCounts[c.name] || {};
    const streak = catStreaks[c.name] || 0;
    const mixParts = [];
    for (const tt of ["spec", "impl", "test", "review"]) {
      if (tc[tt]) mixParts.push(`${D}${tt}${R} ${tc[tt]}`);
    }
    const mixStr = mixParts.length ? mixParts.join("  ") : `${D}no recent activity${R}`;

    console.log(
      `  ${B}${pad(c.name, COL[0])}${R}` +
      ` ${pad(c.ideas.length, COL[1], true)}` +
      ` ${C}${pad(fmtCC(gap), COL[2], true)}${R}` +
      ` ${valBadge(pct).padEnd(14)}` +
      ` ${streakBar(streak, Math.max(...Object.values(catStreaks), 1))}` +
      `  ${mixStr}`
    );
  }
  console.log(`  ${hr(72)}`);

  // Task Effort
  console.log(`\n${B}  Task Effort${R}  ${D}(recent sample + lifetime totals)${R}`);
  console.log(`  ${hr(55)}`);
  const typeOrder = ["spec", "impl", "test", "review", "heal"];
  const typeLabel = { spec: "Spec", impl: "Impl", test: "Test", review: "Review", heal: "Heal" };
  const typeColor = { spec: C, impl: G, test: Y, review: M, heal: D };

  for (const tt of typeOrder) {
    const samples = effortByType[tt] || [];
    const total   = progressTotals[tt] || 0;
    if (total === 0 && samples.length === 0) continue;
    const avg  = samples.length ? samples.reduce((a, b) => a + b, 0) / samples.length : null;
    const avgStr = avg ? fmtDur(avg) : "—";
    console.log(`  ${typeColor[tt]}${pad(typeLabel[tt], 7)}${R}  avg ${pad(avgStr, 6)}  ${D}${total.toLocaleString()} total${R}`);
  }

  // New Experiences
  if (validated.length > 0) {
    console.log(`\n${B}  Top New Experiences${R}  ${D}(recently validated)${R}`);
    console.log(`  ${hr(65)}`);
    for (let i = 0; i < validated.length; i++) {
      const v = validated[i];
      console.log(`  ${D}${i + 1}.${R} ${B}${pad((v.name || v.id).slice(0, 42), 44)}${R} ${G}+${(v.actual_value || 0).toFixed(1)} CC${R}  ${D}${classify(v)}${R}`);
    }
  }

  // Running
  if (runningTasks.length > 0) {
    console.log(`\n${B}  Running now${R}  ${D}(${runningTasks.length} active)${R}`);
    console.log(`  ${hr(65)}`);
    for (const t of runningTasks.slice(0, 5)) {
      const elapsed = t.running_seconds ? fmtDur(t.running_seconds) : "?";
      const dir = (t.direction || "").split("\n")[0].slice(0, 50);
      console.log(`  ${typeColor[t.task_type] || D}${pad(t.task_type || "?", 7)}${R}  ${D}${elapsed}${R}  ${dir}`);
    }
  }
  console.log();
}

/**
 * showPortfolio(args)
 * Personal contributor view.
 * If args[0] is present, show public portfolio for that ID.
 * Otherwise, show /api/me/portfolio using current API key.
 */
export async function showPortfolio(args) {
  const contributorId = args[0];
  const isMe = !contributorId;
  const base = isMe ? "/api/me" : `/api/contributors/${encodeURIComponent(contributorId)}`;

  console.log(`${D}  Loading portfolio...${R}`);

  const [summary, history, ideas, stakes, tasks] = await Promise.all([
    get(`${base}/portfolio`),
    get(`${base}/cc-history`, { window: "90d", bucket: "7d" }),
    get(`${base}/idea-contributions`, { sort: "cc_attributed_desc", limit: 10 }),
    get(`${base}/stakes`, { sort: "roi_desc", limit: 10 }),
    get(`${base}/tasks`, { status: "completed", limit: 10 }),
  ]);

  if (!summary) {
    console.log(`${RED}  Portfolio not found.${R}`);
    if (isMe) console.log(`  ${D}Try running 'cc setup' or providing an ID: cc portfolio <id>${R}`);
    return;
  }

  const { contributor } = summary;
  console.log(`\n${B}  ${isMe ? "MY" : "CONTRIBUTOR"} PORTFOLIO${R}  ${D}${contributor.display_name} (${contributor.id})${R}`);
  console.log(`  ${hr(60)}`);

  // Identities
  if (contributor.identities?.length) {
    const ids = contributor.identities.map(i => `${D}${i.type}:${R}${i.handle}${i.verified ? G+"✓"+R : ""}`).join("  ");
    console.log(`  ${ids}`);
    console.log(`  ${hr(60)}`);
  }

  // Quick Stats
  const QCOL = [15, 10, 10, 10];
  console.log(
    `  ${pad("CC Balance", QCOL[0])} ${pad("Ideas", QCOL[1])} ${pad("Stakes", QCOL[2])} ${pad("Tasks", QCOL[3])}`
  );
  console.log(
    `  ${B}${pad(summary.cc_balance?.toFixed(2) ?? "0.00", QCOL[0])}${R} ` +
    `${pad(summary.idea_contribution_count, QCOL[1])} ` +
    `${pad(summary.stake_count, QCOL[2])} ` +
    `${pad(summary.task_completion_count, QCOL[3])}`
  );
  if (summary.cc_network_pct !== null) {
    console.log(`  ${D}${summary.cc_network_pct.toFixed(4)}% of network${R}`);
  }
  console.log(`  ${hr(60)}`);

  // Earning History Chart (ASCII)
  if (history?.series?.length) {
    console.log(`\n  ${B}CC Earning History${R} ${D}(90d · 7d buckets)${R}`);
    const maxEarned = Math.max(...history.series.map(b => b.cc_earned), 0.1);
    const bars = history.series.map(b => {
      const h = Math.round((b.cc_earned / maxEarned) * 5);
      return " ▂▃▄▅▆▇".charAt(h);
    }).join("");
    console.log(`  ${G}${bars}${R} ${D}total: ${history.series.at(-1)?.running_total.toFixed(1)} CC${R}`);
  }

  // Ideas
  if (ideas?.items?.length) {
    console.log(`\n  ${B}Ideas Contributed To${R}`);
    for (const idea of ideas.items) {
      const type = (idea.contribution_types[0] || "other").slice(0, 6);
      console.log(
        `  ${D}${pad(type, 7)}${R} ${B}${pad(idea.idea_title.slice(0, 30), 31)}${R} ` +
        `${G}${pad(idea.cc_attributed.toFixed(1), 6, true)}${R} ${D}CC${R}`
      );
    }
  }

  // Stakes
  if (stakes?.items?.length) {
    console.log(`\n  ${B}Stakes${R}`);
    for (const stake of stakes.items) {
      const roi = stake.roi_pct !== null ? (stake.roi_pct >= 0 ? G : RED) + stake.roi_pct.toFixed(1) + "%" + R : D + "—" + R;
      console.log(
        `  ${pad(stake.idea_title.slice(0, 30), 31)} ${pad(stake.cc_staked.toFixed(1), 6, true)} ${D}staked${R}  ${roi}`
      );
    }
  }

  // Tasks
  if (tasks?.items?.length) {
    console.log(`\n  ${B}Recent Tasks${R}`);
    for (const task of tasks.items.slice(0, 5)) {
      const date = task.completed_at ? new Date(task.completed_at).toLocaleDateString("en-US", {month:"short", day:"numeric"}) : "—";
      console.log(`  ${D}${pad(date, 6)}${R} ${task.description.slice(0, 50)}`);
    }
  }

  console.log();
}
