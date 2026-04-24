import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getApiBase } from "@/lib/api";
import type { Concept, Edge, LCConcept } from "@/lib/types/vision";
import { ConnectedConcepts } from "../[conceptId]/_components/ConnectedConcepts";
import { EnergyContributors } from "../[conceptId]/_components/EnergyContributors";
import { ReaderPresence } from "../[conceptId]/_components/ReaderPresence";
import { ResonantAssets } from "../[conceptId]/_components/ResonantAssets";
import { StoryContent } from "../[conceptId]/_components/StoryContent";
import { WorldSignals } from "../[conceptId]/_components/WorldSignals";
import { LiveProof } from "./_components/LiveProof";

export const dynamic = "force-dynamic";
const CONCEPT_ID = "lc-economy";

export const metadata: Metadata = {
  title: "The Living Economy — The Living Collective",
  description:
    "A creation economy where basics are not gated, contribution widens beyond jobs, and money becomes a sensing layer for circulation rather than scarcity.",
};

const PURE_FORM = [
  {
    title: "Money becomes sensing",
    body:
      "The record exists to show what moved, what restored, and what asks to flow next. It does not decide who gets to belong.",
    tone: "border-amber-500/20 bg-amber-500/10 text-amber-200",
  },
  {
    title: "Contribution widens",
    body:
      "Writing, repair, hosting, care work, conflict tending, land restoration, child support, and beauty all become legible as creation.",
    tone: "border-teal-500/20 bg-teal-500/10 text-teal-200",
  },
  {
    title: "Buffers serve vitality",
    body:
      "Storage remains only where it protects the organism: illness, winter, repair, birth, migration, experimentation. Everything else stays in flow.",
    tone: "border-violet-500/20 bg-violet-500/10 text-violet-200",
  },
];

const EMBODIED_NOW = [
  {
    title: "Start from access, not extraction",
    body:
      "Open the work, the meal, the room, or the tool first. Add tracking only to understand circulation, not to put another gate in front of aliveness.",
  },
  {
    title: "Name what already nourishes",
    body:
      "A host, cook, repairer, elder, or organizer may already be carrying the field without economic language catching up to it yet.",
  },
  {
    title: "Make the flow visible",
    body:
      "One simple board, ledger, dashboard, or shared note can show what is abundant, what is needed, what is buffered, and what wants to move today.",
  },
];

const TRANSFORMATIONS = [
  {
    context: "City",
    title: "Creator floor",
    image: "/visuals/transform-apartment.png",
    body:
      "A floor in an existing building keeps its walls but changes everything else: open studio hours, shared production tools, a visible food buffer, free creative output, and attribution that stays attached as work moves.",
    firstMove:
      "Keep the shell and reimagine the schedule, access, naming, and contribution logic of one room before trying to redesign the whole building.",
  },
  {
    context: "Urban",
    title: "Provision house",
    image: "/visuals/transform-neighborhood.png",
    body:
      "A storefront keeps its address and frontage but drops checkout logic in favor of repair, borrowing, fitting, public learning, and a neighborhood ledger of what is moving through the block.",
    firstMove:
      "Leave the shell in place and rearrange the threshold, counters, timings, and social ritual around one repair table or shared pantry edge.",
  },
  {
    context: "Suburban",
    title: "Commons lane",
    image: "/visuals/generated/lc-attuned-spaces-0.jpg",
    body:
      "Several households keep their homes but reimagine the edges between them: shared staples, child support, rides, tools, and a small resilience buffer for illness and repair. The economy feels local because the bracing stops being private.",
    firstMove:
      "Keep the houses, reimagine the porches, driveways, meal rhythm, and buffer logic with one weekly meal and one visible pantry shelf.",
  },
  {
    context: "Rural",
    title: "Anchor membrane",
    image: "/visuals/community-earthship.png",
    body:
      "A house, barn, or greenhouse stays physically intact while welcome, storage, surplus flow, skill sharing, and local exchange are rearranged into one visible metabolism.",
    firstMove:
      "Leave the structure alone at first and redesign how it receives people, tools, food, and shared responsibility before building anything new.",
  },
];

const RENAMES = [
  ["Store", "Provision house"],
  ["Restaurant", "Nourishment hall"],
  ["Customer", "Guest or participant"],
  ["Job", "Offering"],
  ["Budget", "Circulation view"],
  ["Savings", "Vital buffer"],
];

const VISUAL_DOORS = [
  {
    label: "Repurposed now",
    title: "An existing shell drops extraction logic",
    image: "/visuals/transform-neighborhood.png",
    body:
      "A storefront, floor, hall, or studio keeps its walls and changes its social metabolism: less checkout, more repair, nourishment, visibility, and shared contribution.",
  },
  {
    label: "Pure imagination",
    title: "The economy as architecture from the beginning",
    image: "/visuals/generated/lc-economy-0.jpg",
    body:
      "When the field is free to build from first principles, creation, hospitality, vitality buffers, and beauty become visible in the structure itself, not added later as programs.",
  },
];

async function fetchConcept(): Promise<Concept | null> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${CONCEPT_ID}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchEdges(): Promise<Edge[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/${CONCEPT_ID}/edges`, {
      next: { revalidate: 30 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

async function fetchAllLC(): Promise<LCConcept[]> {
  const base = getApiBase();
  try {
    const res = await fetch(`${base}/api/concepts/domain/living-collective?limit=200`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.items || [];
  } catch {
    return [];
  }
}

export default async function EconomyPage() {
  const [concept, edges, allLC] = await Promise.all([fetchConcept(), fetchEdges(), fetchAllLC()]);

  const relevantEdges = edges.filter((e) => {
    if (e.from.startsWith("visual-lc-") || e.to.startsWith("visual-lc-")) return false;
    if (e.from.startsWith("renderer-") || e.to.startsWith("renderer-")) return false;
    return true;
  });
  const outgoing = relevantEdges.filter((e) => e.from === CONCEPT_ID);
  const incoming = relevantEdges.filter((e) => e.to === CONCEPT_ID);

  const nameMap: Record<string, string> = {};
  for (const c of allLC) {
    if (c.id && c.name) nameMap[c.id] = c.name;
  }
  const unresolvedTargets = new Set<string>();
  for (const e of relevantEdges) {
    for (const target of [e.from, e.to]) {
      if (target !== CONCEPT_ID && !nameMap[target] && !target.startsWith("lc-")) {
        unresolvedTargets.add(target);
      }
    }
  }
  if (unresolvedTargets.size > 0) {
    const base = getApiBase();
    const resolved = await Promise.all(
      Array.from(unresolvedTargets).map(async (id) => {
        try {
          const r = await fetch(
            `${base}/api/graph/nodes/${encodeURIComponent(id)}`,
            { next: { revalidate: 60 } },
          );
          if (!r.ok) return null;
          const n = await r.json();
          return { id, name: n?.name || n?.author_display_name || null };
        } catch {
          return null;
        }
      }),
    );
    for (const entry of resolved) {
      if (entry?.name) nameMap[entry.id] = entry.name;
    }
  }
  const pageTitle = concept?.name || "The Living Economy";

  return (
    <main>
      <section className="relative overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(234,179,8,0.12),_transparent_34%),radial-gradient(circle_at_bottom_right,_rgba(45,212,191,0.12),_transparent_28%),radial-gradient(circle_at_bottom_left,_rgba(196,181,253,0.1),_transparent_24%)]">
        <div className="mx-auto max-w-5xl px-6 py-20 text-center md:py-28">
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400/70">The living economy</p>
          <h1 className="mt-4 text-5xl font-extralight tracking-tight text-white md:text-6xl">
            Creation stays open.
            <br />
            Circulation becomes visible.
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-lg font-light leading-relaxed text-stone-300 md:text-xl">
            The creator economy was the first legible tissue. The living economy widens it into a
            creation economy where meals, repair, care work, hosting, design, code, land tending,
            and wisdom all become visible contributions, while basics stop being used as leverage.
          </p>
          <div className="mt-4 flex justify-center">
            <ReaderPresence conceptId={CONCEPT_ID} />
          </div>
          <div className="mt-8 flex flex-wrap justify-center gap-3 text-sm">
            <Link
              href="/vision/realize"
              className="rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-2 text-amber-200 transition-colors hover:border-amber-400/40 hover:text-amber-100"
            >
              See space transformations
            </Link>
            <Link
              href="/vision/lc-energy"
              className="rounded-full border border-teal-500/30 bg-teal-500/10 px-4 py-2 text-teal-200 transition-colors hover:border-teal-400/40 hover:text-teal-100"
            >
              Trace energy across forms
            </Link>
            <Link
              href="/energy-flow"
              className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-emerald-200 transition-colors hover:border-emerald-400/40 hover:text-emerald-100"
            >
              Sense live energy
            </Link>
            <Link
              href="/verify"
              className="rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-violet-200 transition-colors hover:border-violet-400/40 hover:text-violet-100"
            >
              Verify the flow
            </Link>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-6 pb-20">
        <nav className="mb-8 flex items-center gap-2 pt-8 text-sm text-stone-500" aria-label="breadcrumb">
          <Link href="/vision" className="transition-colors hover:text-amber-400/80">
            The Living Collective
          </Link>
          <span className="text-stone-700">/</span>
          <span className="text-stone-300">{pageTitle}</span>
        </nav>

        <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="rounded-[1.75rem] border border-stone-800/40 bg-stone-900/30 p-8">
            <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Pure form</p>
            <h2 className="mt-3 text-3xl font-extralight text-stone-200">
              The economy as a sensing organ
            </h2>
            <div className="mt-6 space-y-4">
              {PURE_FORM.map((item) => (
                <div key={item.title} className={`rounded-2xl border p-5 ${item.tone}`}>
                  <h3 className="text-lg font-light text-white">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-stone-300">{item.body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[1.75rem] border border-stone-800/40 bg-stone-950/40 p-8">
            <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Embodied now</p>
            <h2 className="mt-3 text-3xl font-extralight text-stone-200">
              The first shifts are already practical
            </h2>
            <div className="mt-6 space-y-4">
              {EMBODIED_NOW.map((item) => (
                <div key={item.title} className="rounded-2xl border border-stone-800/30 bg-stone-900/30 p-5">
                  <h3 className="text-lg font-light text-teal-200">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-stone-400">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mt-12 space-y-8">
          <div className="space-y-3">
            <p className="text-sm uppercase tracking-[0.28em] text-stone-500">See it quickly</p>
            <h2 className="text-3xl font-extralight text-stone-200">The economy also needs two visual doors</h2>
            <p className="max-w-3xl text-stone-400 leading-relaxed">
              One image shows what can be repurposed now inside existing shells. The other protects
              the uncompressed horizon so reuse does not become another name for compromise.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            {VISUAL_DOORS.map((item) => (
              <article
                key={item.label}
                className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
              >
                <div className="relative aspect-[16/10] overflow-hidden">
                  <Image
                    src={item.image}
                    alt={item.title}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 100vw, 50vw"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
                </div>
                <div className="space-y-3 p-5">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-stone-500">{item.label}</p>
                  <h3 className="text-xl font-light text-white">{item.title}</h3>
                  <p className="text-sm leading-relaxed text-stone-400">{item.body}</p>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-12 rounded-2xl border border-stone-800/40 bg-stone-900/30 p-8">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">What stays, what changes</p>
          <h2 className="mt-3 text-3xl font-extralight text-stone-200">Leave the shell. Reimagine the rest.</h2>
          <p className="mt-4 max-w-3xl text-stone-400 leading-relaxed">
            In many places the fastest transformation is not demolition. It is questioning every
            social default inside an existing structure: the name of the room, who it is for, when
            it opens, what happens there, how resources move, which rituals slow people down, and
            what forms of contribution become visible once extraction is removed.
          </p>
        </section>

        <section className="mt-12 rounded-2xl border border-stone-800/40 bg-stone-900/30 p-8">
          <h2 className="text-lg font-light text-stone-300">How Creation Flows</h2>
          <div className="mt-5 space-y-1 overflow-x-auto font-mono text-xs leading-loose text-stone-500">
            <div className="text-amber-400/70">Creation</div>
            <div>  │ today: article, blueprint, 3D model, image, code, meal, repair, hosting, care, land tending</div>
            <div>  │ digital traces register first because attribution is easiest there</div>
            <div>  │ the system widens by learning to sense real-world nourishment without pretending certainty</div>
            <div>  ▼</div>
            <div className="text-teal-400/70">Receiver</div>
            <div>  │ receives freely: no paywall, no subscription, no ad-mediated access to basics</div>
            <div>  │ may identify voluntarily → contributor presence becomes legible without becoming coercive</div>
            <div>  ▼</div>
            <div className="text-violet-400/70">Resonant Return</div>
            <div>  │ later creation, support, repair, referral, hosting, or nourishment routes value back through the path</div>
            <div>  │ weighted by resonance, not by who shouts loudest</div>
            <div>  ▼</div>
            <div className="text-emerald-400/70">The Field Senses</div>
            <div>  │ what moved, what restored, what needs replenishment, what wants to open next</div>
            <div>  │ the record is for honest circulation, not for permission</div>
            <div>  ▼</div>
            <div className="text-amber-400/70">Verification</div>
            <div>  │ hash chains, signed snapshots, public APIs, recomputable proof</div>
            <div>  └─ the math exists so trust does not depend on authority</div>
          </div>
        </section>

        <section className="mt-12 space-y-8">
          <div className="space-y-3">
            <p className="text-sm uppercase tracking-[0.28em] text-stone-500">
              Concrete right-now transformations
            </p>
            <h2 className="text-3xl font-extralight text-stone-200">
              What this economy can look like before the full system arrives
            </h2>
            <p className="max-w-3xl text-stone-400 leading-relaxed">
              The living economy does not start when every metric is perfect. It starts when a room,
              block, lane, or rural anchor stops treating every need as a private burden and begins
              making circulation visible enough to respond together.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            {TRANSFORMATIONS.map((item) => (
              <article
                key={item.title}
                className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
              >
                <div className="relative aspect-[16/10] overflow-hidden">
                  <Image
                    src={item.image}
                    alt={`${item.context} ${item.title}`}
                    fill
                    className="object-cover"
                    sizes="(max-width: 768px) 100vw, 50vw"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
                </div>
                <div className="space-y-3 p-5">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-stone-500">{item.context}</p>
                  <h3 className="text-xl font-light text-white">{item.title}</h3>
                  <p className="text-sm leading-relaxed text-stone-400">{item.body}</p>
                  <div className="rounded-xl border border-stone-800/30 bg-stone-950/30 p-3">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-stone-500">First move</p>
                    <p className="mt-1 text-xs leading-relaxed text-stone-400">{item.firstMove}</p>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-12 rounded-2xl border border-stone-800/40 bg-stone-900/30 p-8">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">What changes name first</p>
          <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {RENAMES.map(([from, to]) => (
              <div
                key={`${from}-${to}`}
                className="rounded-xl border border-stone-800/30 bg-stone-950/30 px-4 py-3"
              >
                <p className="text-xs uppercase tracking-[0.22em] text-stone-600 line-through decoration-stone-800">
                  {from}
                </p>
                <p className="mt-1 text-sm font-light text-amber-200">{to}</p>
              </div>
            ))}
          </div>
        </section>

        {concept?.story_content && (
          <div className="mt-12 max-w-3xl">
            <StoryContent content={concept.story_content} conceptId={CONCEPT_ID} nameMap={nameMap} />
          </div>
        )}

        <div className="mt-12 max-w-3xl space-y-8">
          <EnergyContributors conceptId={CONCEPT_ID} />
          <ResonantAssets conceptId={CONCEPT_ID} />
          <WorldSignals conceptId={CONCEPT_ID} />
          <ConnectedConcepts outgoing={outgoing} incoming={incoming} nameMap={nameMap} mode="full" />
        </div>

        <section className="mt-12 rounded-2xl border border-stone-800/40 bg-stone-900/30 p-6 space-y-3">
          <h2 className="text-lg font-light text-stone-300">First organs live</h2>
          <p className="text-sm leading-relaxed text-stone-400">
            This is no longer only speculative language. Views, discovery chains, reward policies,
            contributor surfaces, and the live energy map are the first software tissues of a wider
            sensing economy. They are partial, narrow, and honest, which is exactly what lets the
            next layer be built without pretending the organism can already feel everything.
          </p>
          <div className="flex flex-wrap gap-4 text-sm">
            <Link href="/analytics" className="text-stone-500 transition-colors hover:text-amber-300/80">
              Attention flow
            </Link>
            <Link href="/energy-flow" className="text-stone-500 transition-colors hover:text-teal-300/80">
              Energy map
            </Link>
            <Link href="/alive" className="text-stone-500 transition-colors hover:text-violet-300/80">
              Community pulse
            </Link>
          </div>
        </section>

        <LiveProof />

        <div className="flex gap-4 pt-12 text-sm">
          <Link href="/vision" className="text-stone-500 transition-colors hover:text-amber-300/80">
            &larr; The Living Collective
          </Link>
          <Link href="/vision/realize" className="text-stone-500 transition-colors hover:text-amber-300/80">
            Living it
          </Link>
          <Link href="/verify" className="text-stone-500 transition-colors hover:text-teal-300/80">
            Verify any asset
          </Link>
          <Link href="/vision/join" className="text-stone-500 transition-colors hover:text-teal-300/80">
            Join
          </Link>
        </div>
      </div>
    </main>
  );
}
