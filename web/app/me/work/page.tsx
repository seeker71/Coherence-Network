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
  ai_collaborators: { name: string; co_authorships: number }[];
  recent_prs: { number: number; date: string; title: string }[];
  github_url: string;
}

// Founder cell — Urs (seeker71). Numbers queried directly from git
// + repo file counts on 2026-05-05. Verifiable at the github_url below.
const FOUNDER_BODY_OF_WORK: BodyOfWork = {
  display_name: "Urs Muff",
  github_handle: "seeker71",
  first_commit: "2026-02-11",
  last_commit: "2026-05-04",
  commits: 1372,
  specs_authored: 90,
  ideas_captured: 16,
  concepts_written: 61,
  prs_merged: 200,
  ai_collaborators: [
    { name: "Claude (Anthropic)", co_authorships: 3163 },
    { name: "Cursor Agent", co_authorships: 1 },
    { name: "Codex Agent", co_authorships: 2 },
    { name: "Gemini", co_authorships: 0 },
  ],
  recent_prs: [
    { number: 1295, date: "2026-05-04", title: "identity: pre-fill page with visitor's actual identity" },
    { number: 1294, date: "2026-05-04", title: "with-us: update contact email" },
    { number: 1293, date: "2026-05-04", title: "with-us: ONE clean presentation page using existing visuals" },
    { number: 1292, date: "2026-05-04", title: "weave: /silence/built compound vision + /weave open invitation" },
    { number: 1288, date: "2026-05-04", title: "silence: Brahmavihara retreat — eight notebook pages" },
    { number: 1283, date: "2026-04-30", title: "welcome: handoff workflow + voice discipline" },
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

export default function BodyOfWorkPage() {
  const t = useT();
  const [identity, setIdentity] = useState<ReturnType<typeof readIdentity> | null>(null);

  useEffect(() => {
    setIdentity(readIdentity());
  }, []);

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
              value="83"
              unit={t("meWork.stats.buildingSpanUnit")}
              hint={interp(t("meWork.stats.buildingSpanHint"), {
                firstCommit: work.first_commit,
                lastCommit: work.last_commit,
              })}
            />
            <StatTile
              label={t("meWork.stats.avgPrsWeek")}
              value={Math.round((work.prs_merged / 12) * 10) / 10}
              hint={t("meWork.stats.avgPrsWeekHint")}
            />
            <StatTile
              label={t("meWork.stats.aiCollaborators")}
              value={work.ai_collaborators.filter((a) => a.co_authorships > 0).length}
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
                .filter((a) => a.co_authorships > 0)
                .sort((a, b) => b.co_authorships - a.co_authorships)
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
