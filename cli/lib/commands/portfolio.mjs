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
// direction examples:
//   "Implement 'Foo bar' (foo-bar).\n..."
//   "Write a spec for 'Foo bar' (foo-bar).\n..."
//   "Code review for 'Foo bar' (foo-bar).\n..."
function extractIdeaId(direction) {
  if (!direction) return null;
  const m = direction.match(/\(([a-z0-9][a-z0-9-]{2,})\)[.\n]/);
  return m ? m[1] : null;
}

// ── main ──────────────────────────────────────────────────────────────────

export async function showPortfolio() {
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

  // Build per-category task type counts from recent tasks
  // Map idea_id → category
  const ideaToCategory = {};
  for (const idea of ideas) {
    ideaToCategory[idea.id] = classify(idea);
    if (idea.slug) ideaToCategory[idea.slug] = classify(idea);
  }

  const catTaskCounts = {}; // catName → { spec:0, impl:0, test:0, review:0, heal:0, total:0 }
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

  // Compute streak: how many of the last N recent tasks were in this category (consecutive from head)
  // We order tasks most-recent-first from recentTasks (already ordered by API)
  const catStreaks = {};
  const streakWindow = recentTasks.slice(0, 20);
  for (const c of sorted) catStreaks[c.name] = 0;
  // streak = count of the most-recent contiguous run for each category
  for (const c of sorted) {
    let streak = 0;
    for (const t of streakWindow) {
      const ideaId = extractIdeaId(t.direction);
      const catName = ideaId ? ideaToCategory[ideaId] : null;
      if (catName === c.name) streak++;
    }
    catStreaks[c.name] = streak;
  }

  // ── effort data from recent completed tasks ──────────────────────────────
  const effortByType = {}; // type → [duration_seconds, ...]
  for (const t of recentTasks) {
    if (t.duration_seconds && t.duration_seconds > 0) {
      const tt = t.task_type || "other";
      effortByType[tt] = effortByType[tt] || [];
      effortByType[tt].push(t.duration_seconds);
    }
  }
  // Totals from effectiveness endpoint
  const progressTotals = effectiveness?.progress || {};

  // ── top new experiences: validated ideas with actual_value, sorted by last_activity ─
  const validated = ideas
    .filter(i => i.manifestation_status === "validated" && (i.actual_value || 0) > 0)
    .sort((a, b) => (b.last_activity_at || "").localeCompare(a.last_activity_at || ""))
    .slice(0, 8);

  // ── render ───────────────────────────────────────────────────────────────
  const totalPot  = sorted.reduce((s, c) => s + c.pot, 0);
  const totalAct  = sorted.reduce((s, c) => s + c.act, 0);
  const totalGap  = totalPot - totalAct;
  const totalPct  = totalPot > 0 ? Math.round(100 * totalAct / totalPot) : 0;

  console.log();
  console.log(`${B}  PORTFOLIO${R}  ${D}${ideas.length} active ideas · ${fmtCC(totalGap)} CC gap · ${valBadge(totalPct)} captured${R}`);
  console.log(`  ${hr(72)}`);

  // Header
  const COL = [24, 4, 7, 5, 5, 22];
  console.log(
    `  ${D}${pad("Category", COL[0])} ${pad("N", COL[1], true)} ${pad("Gap CC", COL[2], true)}` +
    ` ${pad("Val%", COL[3], true)} ${pad("Streak", COL[4], true)}  Task mix (recent)${R}`
  );
  console.log(`  ${hr(72)}`);

  const maxGap = sorted[0] ? (sorted[0].pot - sorted[0].act) : 1;

  for (const c of sorted) {
    const gap  = c.pot - c.act;
    const pct  = c.pot > 0 ? Math.round(100 * c.act / c.pot) : 0;
    const tc   = catTaskCounts[c.name] || {};
    const streak = catStreaks[c.name] || 0;

    // task mix text: only show types with > 0
    const mixParts = [];
    for (const tt of ["spec", "impl", "test", "review"]) {
      if (tc[tt]) mixParts.push(`${D}${tt}${R} ${tc[tt]}`);
    }
    const mixStr = mixParts.length ? mixParts.join("  ") : `${D}no recent activity${R}`;

    console.log(
      `  ${B}${pad(c.name, COL[0])}${R}` +
      ` ${pad(c.ideas.length, COL[1], true)}` +
      ` ${C}${pad(fmtCC(gap), COL[2], true)}${R}` +
      ` ${valBadge(pct).padEnd(14)}` +   // padded wider to account for escape codes
      ` ${streakBar(streak, Math.max(...Object.values(catStreaks), 1))}` +
      `  ${mixStr}`
    );
  }

  console.log(`  ${hr(72)}`);
  console.log(
    `  ${B}${pad("Total", COL[0])}${R}` +
    ` ${pad(ideas.length, COL[1], true)}` +
    ` ${C}${pad(fmtCC(totalGap), COL[2], true)}${R}` +
    ` ${valBadge(totalPct)}`
  );

  // ── task effort breakdown ─────────────────────────────────────────────────
  console.log();
  console.log(`${B}  Task Effort${R}  ${D}(recent sample + lifetime totals)${R}`);
  console.log(`  ${hr(55)}`);

  const typeOrder = ["spec", "impl", "test", "review", "heal"];
  const typeLabel = { spec: "Spec", impl: "Impl", test: "Test", review: "Review", heal: "Heal" };
  const typeColor = { spec: C, impl: G, test: Y, review: M, heal: D };

  for (const tt of typeOrder) {
    const samples = effortByType[tt] || [];
    const total   = progressTotals[tt] || 0;
    if (total === 0 && samples.length === 0) continue;

    const avg  = samples.length ? samples.reduce((a, b) => a + b, 0) / samples.length : null;
    const max_ = samples.length ? Math.max(...samples) : null;

    const avgStr = avg  ? fmtDur(avg)  : "—";
    const maxStr = max_ ? fmtDur(max_) : "—";

    console.log(
      `  ${typeColor[tt]}${pad(typeLabel[tt], 7)}${R}` +
      `  avg ${pad(avgStr, 6)}  max ${pad(maxStr, 6)}` +
      `  ${D}${total.toLocaleString()} total${R}`
    );
  }

  // ── top new experiences ───────────────────────────────────────────────────
  if (validated.length > 0) {
    console.log();
    console.log(`${B}  Top New Experiences${R}  ${D}(recently validated, by last activity)${R}`);
    console.log(`  ${hr(65)}`);

    for (let i = 0; i < validated.length; i++) {
      const v = validated[i];
      const ago = v.last_activity_at
        ? relativeTime(v.last_activity_at)
        : "unknown";
      const name = (v.name || v.id).slice(0, 42);
      const gain = (v.actual_value || 0).toFixed(1);
      const cat  = classify(v);
      console.log(
        `  ${D}${i + 1}.${R}` +
        ` ${B}${pad(name, 44)}${R}` +
        ` ${G}+${gain} CC${R}` +
        `  ${D}${cat} · ${ago}${R}`
      );
    }
  }

  // ── running right now ─────────────────────────────────────────────────────
  if (runningTasks.length > 0) {
    console.log();
    console.log(`${B}  Running now${R}  ${D}(${runningTasks.length} active)${R}`);
    console.log(`  ${hr(65)}`);
    const shown = runningTasks.slice(0, 6);
    for (const t of shown) {
      const elapsed = t.running_seconds ? fmtDur(t.running_seconds) : "?";
      const dir = (t.direction || "").split("\n")[0].slice(0, 50);
      const tt  = t.task_type || "?";
      const typeC = typeColor[tt] || D;
      console.log(`  ${typeC}${pad(tt, 7)}${R}  ${D}${elapsed}${R}  ${dir}`);
    }
    if (runningTasks.length > 6) {
      console.log(`  ${D}  … and ${runningTasks.length - 6} more${R}`);
    }
  }

  console.log();
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
