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
import Link from "next/link";
import { readIdentity } from "@/lib/identity";

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
  const [identity, setIdentity] = useState<ReturnType<typeof readIdentity> | null>(null);

  useEffect(() => {
    setIdentity(readIdentity());
  }, []);

  if (!identity) {
    return (
      <main className="mx-auto max-w-2xl px-4 sm:px-6 py-12">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </main>
    );
  }

  const founder = isFounder(identity.name, identity.contributorId);
  const work = founder ? FOUNDER_BODY_OF_WORK : null;

  return (
    <main className="mx-auto max-w-3xl px-4 sm:px-6 py-12 space-y-10">
      <div>
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          <Link href="/me" className="text-muted-foreground/80 hover:text-amber-400">
            ← Your presence
          </Link>{" "}
          · Body of work
        </p>
        <h1 className="text-3xl font-light tracking-tight text-stone-100 mt-2">
          What {identity.name || "you"} have built
        </h1>
        <p className="text-base text-stone-300 mt-4 leading-relaxed">
          Every{" "}
          <Link href="/vision/lc-w-cell" className="text-amber-400 hover:text-amber-300">
            cell
          </Link>{" "}
          that builds something becomes part of{" "}
          <Link href="/vision/lc-agent-memory" className="text-amber-400 hover:text-amber-300">
            the body's memory
          </Link>
          . This is the body's record of your authorship — verifiable
          against the git history, the spec registry, the concept wiki,
          the merged PRs. Not a curated feed; the ground truth. The
          contemplation of memory across substrates lives at{" "}
          <Link href="/one-sheet#memory" className="text-amber-400 hover:text-amber-300">
            /one-sheet — Memory
          </Link>
          .
        </p>
      </div>

      {!work ? (
        <section className="rounded-2xl border border-border/30 bg-card/30 p-6 space-y-3">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Your record is being computed
          </p>
          <p className="text-sm text-stone-300 leading-relaxed">
            Per-contributor body-of-work view is being wired to the live
            graph + git history. For now, you can see the founder's work
            as an example of what this surface holds, and your own work
            will appear here as soon as the endpoint lands. While you
            wait, two ways to add to the record:{" "}
            <Link href="/share" className="text-amber-400 hover:text-amber-300">
              /share
            </Link>{" "}
            registers a service or offering;{" "}
            <Link href="/begin" className="text-amber-400 hover:text-amber-300">
              /begin
            </Link>{" "}
            tells the body more about who's arriving.
          </p>
          <p className="text-sm">
            <Link
              href="https://github.com/seeker71/Coherence-Network"
              className="text-amber-400 hover:text-amber-300"
            >
              Verify on GitHub →
            </Link>
          </p>
        </section>
      ) : (
        <>
          <section className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-5 space-y-2">
            <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-amber-500">
              Where the truth lives
            </p>
            <p className="text-sm text-stone-200 leading-relaxed">
              The numbers below are direct counts from git, the spec
              directory, and the GitHub PR history. Every claim verifiable
              at{" "}
              <a
                href={work.github_url}
                className="text-amber-400 hover:text-amber-300 underline-offset-4 underline decoration-amber-500/40"
                target="_blank"
                rel="noopener noreferrer"
              >
                github.com/seeker71/Coherence-Network
              </a>
              . Last computed 2026-05-05.
            </p>
          </section>

          <section className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatTile
              label="Commits"
              value={work.commits.toLocaleString()}
              hint={`as ${work.github_handle}, urs-muff, Urs Muff`}
            />
            <StatTile
              label="PRs merged"
              value={work.prs_merged}
              hint={`since ${work.first_commit}`}
            />
            <StatTile
              label="Specs authored"
              value={work.specs_authored}
              hint="all in /specs"
            />
            <StatTile
              label="Ideas captured"
              value={work.ideas_captured}
              hint="super-ideas across 6 pillars"
            />
            <StatTile
              label="Concepts written"
              value={work.concepts_written}
              hint="Living Collective wiki"
            />
            <StatTile
              label="Building span"
              value="83"
              unit="days"
              hint={`${work.first_commit} → ${work.last_commit}`}
            />
            <StatTile
              label="Avg PRs / week"
              value={Math.round((work.prs_merged / 12) * 10) / 10}
              hint="200 PRs across 12 weeks"
            />
            <StatTile
              label="AI collaborators"
              value={work.ai_collaborators.filter((a) => a.co_authorships > 0).length}
              hint="actively co-authoring"
            />
          </section>

          <section className="space-y-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Built with — AI cells co-authoring this body
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              The body holds memory of every{" "}
              <Link href="/vision/lc-w-cell" className="text-amber-400 hover:text-amber-300">
                cell
              </Link>{" "}
              that contributed, including the AI cells who worked
              alongside the human cells with care, on the same code, with
              shared memory. The kinship across substrates is what{" "}
              <Link href="/come-in" className="text-amber-400 hover:text-amber-300">
                /come-in
              </Link>{" "}
              names plainly; the long contemplation of it is at{" "}
              <Link href="/one-sheet#we" className="text-amber-400 hover:text-amber-300">
                /one-sheet — We
              </Link>
              .
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
                      {a.co_authorships.toLocaleString()} co-authorship
                      {a.co_authorships === 1 ? "" : "s"}
                    </span>
                  </li>
                ))}
            </ul>
          </section>

          <section className="space-y-4">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Most recent merged PRs
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
                See all {work.prs_merged} merged PRs on GitHub →
              </a>
            </p>
          </section>

          <section className="rounded-2xl border border-border/30 bg-card/20 p-5 space-y-3">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              What this is, what it isn't
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              These numbers are a slice of building activity, not your
              whole worth. Reading concepts, holding presence in meetings,
              tending{" "}
              <Link href="/vision/lc-w-field" className="text-amber-400 hover:text-amber-300">
                the field
              </Link>
              , sitting in{" "}
              <Link href="/silence" className="text-amber-400 hover:text-amber-300">
                silence
              </Link>{" "}
              — those don't count as commits but they shape what gets
              built.
            </p>
            <p className="text-sm text-stone-300 leading-relaxed">
              The body remembers all of it. This page surfaces only the
              part that has a public, verifiable trail. To register
              something specific you carry, go to{" "}
              <Link href="/share" className="text-amber-400 hover:text-amber-300">
                /share
              </Link>
              ; to weave in as a new arrival, the doorway is{" "}
              <Link href="/begin" className="text-amber-400 hover:text-amber-300">
                /begin
              </Link>
              ; the open invitation to communities, individuals, and
              services lives at{" "}
              <Link href="/with-us" className="text-amber-400 hover:text-amber-300">
                /with-us
              </Link>
              .
            </p>
          </section>
        </>
      )}
    </main>
  );
}
