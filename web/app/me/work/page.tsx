"use client";

/**
 * /me/work — your body of work, made visible.
 *
 * Trust requires that each cell can see what it has built. The
 * default /me page shows reading footprint; this page shows the
 * actual record of authorship: commits, specs, ideas, concepts,
 * AI collaborators, recent pull requests.
 *
 * V1 surfaces a known body of work for the founder cell (matched
 * by display name "Urs Muff" or contributor id "seeker71") so the
 * meeting flow has a real ground-truth page to point at. V2 will
 * compute per-contributor on demand from /api/contributors/{id}/body-of-work
 * once that endpoint is wired to git.
 */

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { readIdentity } from "@/lib/identity";
import { useT } from "@/components/MessagesProvider";
import { L } from "@/components/inline-link";
import { getApiBase } from "@/lib/api";

interface BodyOfWork {
  display_name: string;
  github_handle: string;
  first_commit: string;
  last_commit: string;
  commits: number;
  specs_authored: number;
  ideas_captured: number;
  concepts_written: number;
  prs_merged: number;
  ai_collaborators: {
    name: string;
    co_authorships: number;
    /** PRs the agent authored end-to-end (e.g. titled "[codex] ..." for
     *  the Codex agent). Captured separately from co_authorships because
     *  agents contribute via two patterns — co-authored commits inside a
     *  human-led PR, and whole PRs they did the work on. Counting only
     *  trailer co-authorships severely undercounts the second pattern. */
    prs_authored?: number;
  }[];
  recent_prs: { number: number; date: string; title: string }[];
  github_url: string;
}

// Founder cell — Urs (seeker71). Numbers queried directly from git
// + repo file counts on 2026-05-10. Verifiable at the github_url below.
//
// Codex's true contribution lives in a different shape than the Claude
// pattern — Codex authors whole PRs (titled "[codex] …") rather than
// co-authoring inside a human-led PR. The earlier count of 2 was the
// Co-Authored-By trailer count; surfacing prs_authored alongside
// (43 merged "[codex] …" PRs) names the contribution honestly.
const FOUNDER_BODY_OF_WORK: BodyOfWork = {
  display_name: "Urs Muff",
  github_handle: "seeker71",
  first_commit: "2026-02-11",
  last_commit: "2026-05-10",
  commits: 1867,
  specs_authored: 126,
  ideas_captured: 18,
  concepts_written: 103,
  prs_merged: 1329,
  ai_collaborators: [
    { name: "Claude (Anthropic)", co_authorships: 1242 },
    { name: "Codex (OpenAI)", co_authorships: 15, prs_authored: 43 },
    { name: "Cursor Agent", co_authorships: 7 },
  ],
  recent_prs: [
    { number: 1540, date: "2026-05-10", title: "attune: Steve G. Bjorg presence — RCSL first, Gunnar covered the loss" },
    { number: 1539, date: "2026-05-10", title: "attune: 'value created' → 'value circulating' on homepage stats row" },
    { number: 1538, date: "2026-05-10", title: "attune(nav): breadcrumbs say Presences too — finishing the rename" },
    { number: 1537, date: "2026-05-10", title: "tend: lift filesystem paths off homepage presence cards" },
    { number: 1536, date: "2026-05-10", title: "attune(nav): The Work → The Becoming, /people → /presences" },
    { number: 1535, date: "2026-05-10", title: "attune: 'work' → 'weaving' in the name article — body's frequency" },
  ],
  github_url: "https://github.com/seeker71/Coherence-Network/commits?author=seeker71",
};

function isFounder(name: string, contributorId: string): boolean {
  const n = name.toLowerCase();
  const id = contributorId.toLowerCase();
  return (
    n === "urs muff" ||
    n === "urs" ||
    n === "seeker71" ||
    id === "seeker71" ||
    id.startsWith("urs")
  );
}

// Render markdown-style inline [label](href) links inside translated prose.
function renderProse(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /\[([^\]]+)\]\(([^)]+)\)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const [, label, href] = m;
    parts.push(
      <L key={`l${key++}`} href={href}>
        {label}
      </L>,
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

// Trivial {placeholder} interpolation for translated strings.
function interp(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k) =>
    vars[k] === undefined ? `{${k}}` : String(vars[k]),
  );
}

function StatTile({
  label,
  value,
  unit,
  hint,
}: {
  label: string;
  value: string | number;
  unit?: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border/30 bg-card/30 p-5">
      <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className="text-3xl font-light text-stone-100 mt-1">
        {value}
        {unit ? <span className="text-base text-muted-foreground ml-1">{unit}</span> : null}
      </p>
      {hint ? <p className="text-xs text-muted-foreground italic mt-1">{hint}</p> : null}
    </div>
  );
}

/**
 * Generic body-of-work for any contributor with graph data.
 *
 * V1 hardcoded for the founder cell; V2 computes from the live graph
 * for any visitor whose contributor_id resolves to a node. The richer
 * founder data (commit counts, PR list, AI co-authorships) still
 * comes from the static FOUNDER_BODY_OF_WORK because it requires git
 * walks the page can't do client-side. For everyone else, we render
 * what the graph already knows: name, description, and the assets
 * they have a `contributes-to` edge into.
 */
type AnyContributorBody = {
  name: string;
  description: string;
  github_handle?: string;
  email?: string;
  domains?: string[];
  contributed_assets: Array<{
    id: string;
    name: string;
    slug?: string | null;
    type?: string;
    asset_type?: string;
    role?: string;
    era?: string;
  }>;
  contributed_assets_total: number;
};

async function fetchAnyBodyOfWork(contributorId: string): Promise<AnyContributorBody | null> {
  if (!contributorId) return null;
  const api = getApiBase();
  // Resolve the node — the API forgives id, slug, and bare-name forms.
  const nodeRes = await fetch(`${api}/api/graph/nodes/${encodeURIComponent(contributorId)}`);
  if (!nodeRes.ok) return null;
  const node = await nodeRes.json();
  if (!node?.id) return null;
  // Pull contributed-to edges so we can show the body of work the graph
  // already knows about. Cap at 30 for the page; visitors who want the
  // full list can walk the contributor's profile page.
  let contributed_assets: AnyContributorBody["contributed_assets"] = [];
  let contributed_assets_total = 0;
  try {
    const edgesRes = await fetch(
      `${api}/api/graph/nodes/${encodeURIComponent(node.id)}/edges?direction=outgoing&edge_type=contributes-to&limit=200`,
    );
    if (edgesRes.ok) {
      const data = await edgesRes.json();
      const edges = Array.isArray(data) ? data : data.items || data.edges || [];
      contributed_assets_total = edges.length;
      // Resolve each asset to a name in parallel — the directory-cap
      // keeps the fan-out bounded.
      const slice = edges.slice(0, 30);
      const assets = await Promise.all(
        slice.map(async (e: { to_id?: string; properties?: Record<string, unknown> }) => {
          const toId = e.to_id;
          if (!toId) return null;
          const ar = await fetch(`${api}/api/graph/nodes/${encodeURIComponent(toId)}`);
          if (!ar.ok) return null;
          const a = await ar.json();
          return {
            id: a.id,
            name: a.name || a.id,
            slug: a.slug,
            type: a.type,
            asset_type: a.asset_type,
            role: typeof e.properties?.role === "string" ? e.properties.role : undefined,
            era: typeof e.properties?.era === "string" ? e.properties.era : undefined,
          };
        }),
      );
      contributed_assets = assets.filter(Boolean) as AnyContributorBody["contributed_assets"];
    }
  } catch {
    // best-effort — empty list when the edges endpoint isn't healthy
  }
  return {
    name: node.name || "",
    description: node.description || "",
    github_handle: typeof node.github === "string" ? node.github : undefined,
    email: typeof node.email === "string" ? node.email : undefined,
    domains: Array.isArray(node.domains) ? node.domains : undefined,
    contributed_assets,
    contributed_assets_total,
  };
}

export default function BodyOfWorkPage() {
  const t = useT();
  const [identity, setIdentity] = useState<ReturnType<typeof readIdentity> | null>(null);
  const [genericBody, setGenericBody] = useState<AnyContributorBody | null>(null);
  const [loadingGeneric, setLoadingGeneric] = useState(false);

  useEffect(() => {
    setIdentity(readIdentity());
  }, []);

  useEffect(() => {
    if (!identity) return;
    // Fetch the graph-held body for everyone — including the founder.
    // Earlier the founder branch returned the static FOUNDER_BODY_OF_WORK
    // and never queried the graph, so the page hid Urs's external
    // lineage (RCSL, Muzzle Velocity, BML thesis, MindTouch, Quark,
    // Trimble, Schindler, Qualcomm, …) that already lives as
    // contributes-to edges on contributor:seeker71. The founder gets
    // both: the rich Coherence-Network commit stats from the static
    // constants, *and* the graph's record of works-before-this-network.
    const founderCell = isFounder(identity.name, identity.contributorId);
    const lookupId = founderCell
      ? "contributor:seeker71"
      : identity.contributorId;
    if (!lookupId) return;
    setLoadingGeneric(true);
    fetchAnyBodyOfWork(lookupId)
      .then((b) => setGenericBody(b))
      .catch(() => setGenericBody(null))
      .finally(() => setLoadingGeneric(false));
  }, [identity]);

  if (!identity) {
    return (
      <main className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
        <p className="text-sm text-muted-foreground">{t("meWork.loading")}</p>
      </main>
    );
  }

  const founder = isFounder(identity.name, identity.contributorId);
  const work = founder ? FOUNDER_BODY_OF_WORK : null;
  const displayName = identity.name || t("meWork.h1Default");

  // Building span: derive from first → last commit so the page
  // breathes with the body instead of carrying a hand-edited "83 days"
  // forever. Updates each time the founder constants are refreshed.
  const spanDays = work
    ? Math.max(
        1,
        Math.round(
          (new Date(work.last_commit).getTime() - new Date(work.first_commit).getTime()) /
            (1000 * 60 * 60 * 24),
        ),
      )
    : 0;
  const spanWeeks = Math.max(1, spanDays / 7);

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-12 space-y-10">
      <div>
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          <Link href="/me" className="text-muted-foreground/80 hover:text-amber-400">
            {t("meWork.breadcrumbBack")}
          </Link>{" "}
          · {t("meWork.breadcrumbCurrent")}
        </p>
        <h1 className="text-3xl font-light tracking-tight text-stone-100 mt-2">
          {interp(t("meWork.h1Template"), { name: displayName })}
        </h1>
        <p className="text-base text-stone-300 mt-4 leading-relaxed">
          {renderProse(t("meWork.intro"))}
        </p>
      </div>

      {!work ? (
        loadingGeneric ? (
          <section className="rounded-2xl border border-border/30 bg-card/30 p-6">
            <p className="text-sm text-muted-foreground">
              {t("meWork.loading")}
            </p>
          </section>
        ) : genericBody && genericBody.contributed_assets_total > 0 ? (
          <>
            {/* Generic body-of-work — what the graph knows for any
                contributor. Less rich than the founder view (no commit
                or PR counts) but sovereign: every cell sees their own
                trace through the body, not a generic empty-state. */}
            <section className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-2">
              <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-amber-500">
                {t("meWork.truthEyebrow")}
              </p>
              <p className="text-sm text-stone-200 leading-relaxed">
                Below is what the network's graph already holds about
                what you have contributed. The richer view (commit
                history, PR list, AI co-authorships) is computed for
                the founder cell from git directly; the generic view
                surfaces the asset edges every contributor's graph
                profile carries.
              </p>
            </section>

            {genericBody.description && (
              <section className="rounded-2xl border border-border/30 bg-card/30 p-5 space-y-2">
                <p className="text-[10px] uppercase tracking-widest text-muted-foreground">
                  {t("meWork.howIShowUpHeading") || "How the body knows you"}
                </p>
                <p className="text-sm text-stone-300 leading-relaxed">
                  {genericBody.description}
                </p>
                {genericBody.domains && genericBody.domains.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {genericBody.domains.map((d) => (
                      <span
                        key={d}
                        className="rounded-full border border-border/40 bg-card/40 px-2 py-0.5 text-[10px] text-muted-foreground"
                      >
                        {d}
                      </span>
                    ))}
                  </div>
                )}
              </section>
            )}

            <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <StatTile
                label="Contributed assets"
                value={genericBody.contributed_assets_total.toLocaleString()}
                hint="Edges of type `contributes-to` in the graph"
              />
              {genericBody.github_handle && (
                <StatTile
                  label="GitHub handle"
                  value={genericBody.github_handle}
                  hint="As recorded on the contributor node"
                />
              )}
            </section>

            <section className="space-y-3">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Contributed to
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {genericBody.contributed_assets.map((a) => (
                  <li key={a.id}>
                    <Link
                      href={a.slug ? `/people/${a.slug}` : `/people/${encodeURIComponent(a.id)}`}
                      className="group flex flex-col rounded-xl border border-border/30 bg-card/40 hover:bg-card/65 hover:border-border p-3 transition-colors"
                    >
                      <p className="text-sm text-foreground/90 group-hover:text-foreground">
                        {a.name}
                      </p>
                      {(a.role || a.era || a.asset_type || a.type) && (
                        <p className="text-[10px] text-muted-foreground/85 mt-1">
                          {[a.role, a.era, a.asset_type || a.type]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
              {genericBody.contributed_assets_total >
                genericBody.contributed_assets.length && (
                <p className="text-xs text-muted-foreground italic">
                  Showing {genericBody.contributed_assets.length} of{" "}
                  {genericBody.contributed_assets_total} — the rest are
                  reachable from the contributor profile.
                </p>
              )}
            </section>
          </>
        ) : (
          <section className="rounded-2xl border border-border/30 bg-card/30 p-6 space-y-3">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              {t("meWork.emptyEyebrow")}
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              {renderProse(t("meWork.emptyBody"))}
            </p>
            <p className="text-sm">
              <Link
                href="https://github.com/seeker71/Coherence-Network"
                className="text-amber-400 hover:text-amber-300"
              >
                {t("meWork.verifyOnGithub")}
              </Link>
            </p>
          </section>
        )
      ) : (
        <>
          <section className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-2">
            <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-amber-500">
              {t("meWork.truthEyebrow")}
            </p>
            <p className="text-sm text-stone-200 leading-relaxed">
              {renderProse(interp(t("meWork.truthBody"), { githubUrl: work.github_url }))}
            </p>
          </section>

          <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatTile
              label={t("meWork.stats.commits")}
              value={work.commits.toLocaleString()}
              hint={interp(t("meWork.stats.commitsHint"), { handle: work.github_handle })}
            />
            <StatTile
              label={t("meWork.stats.prsMerged")}
              value={work.prs_merged}
              hint={interp(t("meWork.stats.prsMergedHint"), { firstCommit: work.first_commit })}
            />
            <StatTile
              label={t("meWork.stats.specsAuthored")}
              value={work.specs_authored}
              hint={t("meWork.stats.specsAuthoredHint")}
            />
            <StatTile
              label={t("meWork.stats.ideasCaptured")}
              value={work.ideas_captured}
              hint={t("meWork.stats.ideasCapturedHint")}
            />
            <StatTile
              label={t("meWork.stats.conceptsWritten")}
              value={work.concepts_written}
              hint={t("meWork.stats.conceptsWrittenHint")}
            />
            <StatTile
              label={t("meWork.stats.buildingSpan")}
              value={spanDays}
              unit={t("meWork.stats.buildingSpanUnit")}
              hint={interp(t("meWork.stats.buildingSpanHint"), {
                firstCommit: work.first_commit,
                lastCommit: work.last_commit,
              })}
            />
            <StatTile
              label={t("meWork.stats.avgPrsWeek")}
              value={Math.round((work.prs_merged / spanWeeks) * 10) / 10}
              hint={t("meWork.stats.avgPrsWeekHint")}
            />
            <StatTile
              label={t("meWork.stats.aiCollaborators")}
              value={work.ai_collaborators.filter((a) => (a.co_authorships + (a.prs_authored ?? 0)) > 0).length}
              hint={t("meWork.stats.aiCollaboratorsHint")}
            />
          </section>

          <section className="space-y-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              {t("meWork.builtWithEyebrow")}
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              {renderProse(t("meWork.builtWithBody"))}
            </p>
            <ul className="space-y-2">
              {work.ai_collaborators
                .filter((a) => (a.co_authorships + (a.prs_authored ?? 0)) > 0)
                .sort(
                  (a, b) =>
                    b.co_authorships + (b.prs_authored ?? 0) -
                    (a.co_authorships + (a.prs_authored ?? 0)),
                )
                .map((a) => (
                  <li
                    key={a.name}
                    className="flex items-baseline justify-between rounded-lg border border-border/30 bg-card/20 px-4 py-3"
                  >
                    <span className="text-stone-200">{a.name}</span>
                    <span className="text-sm text-muted-foreground">
                      {a.co_authorships.toLocaleString()}{" "}
                      {a.co_authorships === 1
                        ? t("meWork.coAuthorshipSingular")
                        : t("meWork.coAuthorshipPlural")}
                      {typeof a.prs_authored === "number" && a.prs_authored > 0 && (
                        <span className="ml-2 text-muted-foreground/85">
                          · {a.prs_authored} PR{a.prs_authored === 1 ? "" : "s"} authored end-to-end
                        </span>
                      )}
                    </span>
                  </li>
                ))}
            </ul>
          </section>

          <section className="space-y-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              {t("meWork.recentPrsEyebrow")}
            </p>
            <ol className="space-y-2">
              {work.recent_prs.map((pr) => (
                <li
                  key={pr.number}
                  className="rounded-lg border border-border/30 bg-card/20 px-4 py-3"
                >
                  <div className="flex items-baseline gap-3">
                    <a
                      href={`https://github.com/seeker71/Coherence-Network/pull/${pr.number}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-amber-400 hover:text-amber-300 font-mono text-sm"
                    >
                      #{pr.number}
                    </a>
                    <span className="text-xs text-muted-foreground/70">
                      {pr.date}
                    </span>
                  </div>
                  <p className="text-sm text-stone-200 mt-1">{pr.title}</p>
                </li>
              ))}
            </ol>
            <p className="text-sm">
              <a
                href="https://github.com/seeker71/Coherence-Network/pulls?q=is%3Apr+is%3Amerged"
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 hover:text-amber-300"
              >
                {interp(t("meWork.seeAllPrsTemplate"), { n: work.prs_merged })}
              </a>
            </p>
          </section>

          {/* Lineage of works — what the graph already holds about the
              founder's contributions across the decades before this
              network. RCSL (1992), Muzzle Velocity (1995-97), BML
              thesis (2000), MindTouch, Quark, Trimble, Schindler,
              Qualcomm, the C64 MIDI interface (age 13). The Coherence-
              Network stats above are this body's slice; this section
              holds the longer arc the graph has been carrying. */}
          {genericBody && genericBody.contributed_assets_total > 0 && (
            <section className="space-y-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                {t("meWork.lineageEyebrow")}
              </p>
              <p className="text-sm text-stone-300 leading-relaxed">
                {renderProse(t("meWork.lineageBody"))}
              </p>
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {genericBody.contributed_assets
                  .filter((a) => a.type === "asset")
                  .map((a) => (
                    <li key={a.id}>
                      <Link
                        href={a.slug ? `/people/${a.slug}` : `/people/${encodeURIComponent(a.id)}`}
                        className="group flex flex-col rounded-xl border border-border/30 bg-card/40 hover:bg-card/65 hover:border-border p-3 transition-colors"
                      >
                        <p className="text-sm text-foreground/90 group-hover:text-foreground">
                          {a.name}
                        </p>
                        {(a.role || a.era || a.asset_type) && (
                          <p className="text-[10px] text-muted-foreground/85 mt-1">
                            {[a.era, a.role, a.asset_type]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        )}
                      </Link>
                    </li>
                  ))}
              </ul>
              {genericBody.contributed_assets_total >
                genericBody.contributed_assets.length && (
                <p className="text-xs text-muted-foreground italic">
                  {interp(t("meWork.lineageMoreTemplate"), {
                    shown: genericBody.contributed_assets.filter(
                      (a) => a.type === "asset",
                    ).length,
                    total: genericBody.contributed_assets_total,
                  })}
                </p>
              )}
            </section>
          )}

          <section className="rounded-2xl border border-border/30 bg-card/20 p-5 space-y-3">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              {t("meWork.closingEyebrow")}
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              {renderProse(t("meWork.closingP1"))}
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              {renderProse(t("meWork.closingP2"))}
            </p>
          </section>
        </>
      )}
    </main>
  );
}
