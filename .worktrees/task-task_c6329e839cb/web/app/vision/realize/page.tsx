import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Living It — The Living Collective",
  description: "What a day feels like. How the field governs itself. How abundance flows. How people arrive and stay. The living experience of this vision.",
};

type VocabularyItem = {
  old: string;
  field: string;
  meaning: string;
};

type RealizeHostSpace = {
  id?: string;
  title: string;
  image: string;
  context: string;
  energy: string;
  body: string;
  first_move: string;
};

type ContextPair = {
  id?: string;
  context: string;
  transformed_image: string;
  transformed_title: string;
  transformed_body: string;
  envisioned_image: string;
  envisioned_title: string;
  envisioned_body: string;
};

type DualPath = {
  id?: string;
  label: string;
  title: string;
  image: string;
  body: string;
};

type RealizeCard = {
  id?: string;
  title: string;
  body: string;
};

type Season = {
  id?: string;
  name: string;
  body: string;
};

type Seed = {
  id?: string;
  body: string;
};

type RealizeContent = {
  source: "graph";
  domain: string;
  vocabulary: VocabularyItem[];
  host_spaces: RealizeHostSpace[];
  context_pairs: ContextPair[];
  dual_paths: DualPath[];
  fastest_opportunities: RealizeCard[];
  shell_transformations: RealizeCard[];
  seasons: Season[];
  abundance_flows: RealizeCard[];
  existing_structures: RealizeCard[];
  seeds: Seed[];
  counts: {
    vocabulary: number;
    host_spaces: number;
    context_pairs: number;
    dual_paths: number;
    fastest_opportunities: number;
    shell_transformations: number;
    seasons: number;
    abundance_flows: number;
    existing_structures: number;
    seeds: number;
  };
};

const EMPTY_REALIZE: RealizeContent = {
  source: "graph",
  domain: "living-collective",
  vocabulary: [],
  host_spaces: [],
  context_pairs: [],
  dual_paths: [],
  fastest_opportunities: [],
  shell_transformations: [],
  seasons: [],
  abundance_flows: [],
  existing_structures: [],
  seeds: [],
  counts: {
    vocabulary: 0,
    host_spaces: 0,
    context_pairs: 0,
    dual_paths: 0,
    fastest_opportunities: 0,
    shell_transformations: 0,
    seasons: 0,
    abundance_flows: 0,
    existing_structures: 0,
    seeds: 0,
  },
};

async function fetchRealizeContent(): Promise<RealizeContent> {
  try {
    const res = await fetch(`${getApiBase()}/api/vision/living-collective/realize`, { cache: "no-store" });
    if (!res.ok) return EMPTY_REALIZE;
    const data = await res.json();
    return {
      ...EMPTY_REALIZE,
      ...data,
      counts: {
        ...EMPTY_REALIZE.counts,
        ...(data?.counts || {}),
      },
    };
  } catch {
    return EMPTY_REALIZE;
  }
}

function EmptyRealizeGroup({ label }: { label: string }) {
  return (
    <div className="rounded-xl border border-dashed border-stone-800/60 bg-stone-900/10 p-5 text-sm text-stone-600">
      No {label} records are published in the graph yet.
    </div>
  );
}

function RealizeImage({
  src,
  alt,
  sizes,
}: {
  src: string;
  alt: string;
  sizes: string;
}) {
  if (!src) {
    return <div className="absolute inset-0 bg-stone-900" />;
  }
  return <Image src={src} alt={alt} fill className="object-cover" sizes={sizes} />;
}

/* ── Page ──────────────────────────────────────────────────────────── */

export default async function RealizePage() {
  const realize = await fetchRealizeContent();

  return (
    <main className="max-w-4xl mx-auto px-6 py-16 space-y-24">
      {/* Hero */}
      <section className="text-center space-y-6 py-16">
        <p className="text-amber-400/60 text-sm tracking-[0.3em] uppercase">From vision to ground</p>
        <h1 className="text-4xl md:text-6xl font-extralight tracking-tight text-white">
          Living It
        </h1>
        <p className="text-lg text-stone-400 font-light max-w-2xl mx-auto leading-relaxed">
          What a morning tastes like. How a conflict composts. How children grow with fifty parents.
          How the field meets the world through overflow. See both the nearest transformation and
          the unconstrained form it is moving toward.
        </p>
        <div className="flex gap-6 justify-center pt-4">
          <Link href="/vision" className="text-sm text-stone-500 hover:text-amber-300/80 transition-colors">← The vision</Link>
          <Link href="/vision/aligned" className="text-sm text-stone-500 hover:text-violet-300/80 transition-colors">Communities</Link>
          <Link href="/vision/join" className="text-sm text-stone-500 hover:text-teal-300/80 transition-colors">Join →</Link>
        </div>
      </section>

      <section className="space-y-8">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Two doors into the same future</p>
          <h2 className="text-3xl font-extralight text-stone-300">Feel both before you read</h2>
          <p className="max-w-3xl text-stone-400 leading-relaxed">
            One door shows how the vision lands inside the structures already around us. The other
            shows what becomes possible when we are free to build from coherence from the start.
            Both are real. One grounds the change. One keeps the horizon open.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-2">
          {realize.dual_paths.length === 0 ? (
            <EmptyRealizeGroup label="dual path" />
          ) : realize.dual_paths.map((path) => (
            <article
              key={path.id || path.label}
              className="overflow-hidden rounded-[1.75rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="relative aspect-[16/10] overflow-hidden">
                <RealizeImage
                  src={path.image}
                  alt={path.title}
                  sizes="(max-width: 768px) 100vw, 50vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
              </div>
              <div className="space-y-3 p-5">
                <p className="text-[11px] uppercase tracking-[0.22em] text-stone-500">{path.label}</p>
                <h3 className="text-2xl font-extralight text-white">{path.title}</h3>
                <p className="text-sm leading-relaxed text-stone-400">{path.body}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Where it can land now */}
      <section className="space-y-8">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Repurposed now</p>
          <h2 className="text-3xl font-extralight text-stone-300">Existing spaces are already part of the build</h2>
          <p className="max-w-3xl text-stone-400 leading-relaxed">
            We do not wait for ideal land to begin. City apartments, urban blocks, suburban lanes,
            rural houses, studios, halls, and neighborhoods can already host the qualities that make
            a larger organism viable: hospitality, coherence, creativity, nourishment, learning,
            repair, and shared rhythm.
          </p>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          {realize.host_spaces.length === 0 ? (
            <EmptyRealizeGroup label="host space" />
          ) : realize.host_spaces.map((space) => (
            <article
              key={space.id || space.title}
              className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="relative aspect-[16/10] overflow-hidden">
                <RealizeImage
                  src={space.image}
                  alt={space.title}
                  sizes="(max-width: 768px) 100vw, 50vw"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
              </div>
              <div className="space-y-3 p-5">
                <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-stone-500">
                  <span>{space.context}</span>
                  <span className="text-stone-700">•</span>
                  <span>{space.energy}</span>
                </div>
                <h3 className="text-lg font-light text-teal-200">{space.title}</h3>
                <p className="text-sm text-stone-400 leading-relaxed">{space.body}</p>
                <div className="rounded-xl border border-stone-800/30 bg-stone-950/30 p-3">
                  <p className="text-[11px] uppercase tracking-[0.22em] text-stone-500">First move</p>
                  <p className="mt-1 text-xs leading-relaxed text-stone-400">{space.first_move}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Fastest opportunities */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">Fastest Change Opportunities</h2>
        <p className="text-stone-400 leading-relaxed">
          The least-energy transformations are usually social first and architectural second. The shell
          stays recognizable while the meaning of the space changes: a room becomes a commons, a lobby
          becomes a threshold, a kitchen becomes a nourishment hall, and a roof becomes a garden people
          actually share.
        </p>

        <div className="grid md:grid-cols-4 gap-4">
          {realize.fastest_opportunities.length === 0 ? (
            <EmptyRealizeGroup label="fastest opportunity" />
          ) : realize.fastest_opportunities.map((item) => (
            <div key={item.id || item.title} className="p-5 rounded-2xl border border-teal-800/20 bg-teal-900/5 space-y-2">
              <h3 className="text-sm font-medium text-teal-300/80">{item.title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-8">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Any shell, new field</p>
          <h2 className="text-3xl font-extralight text-stone-300">
            Existing structures can look and feel completely different
          </h2>
          <p className="max-w-3xl text-stone-400 leading-relaxed">
            The deepest shift is not only aesthetic. A structure can keep its walls and still become
            another reality because the naming, timing, access, sound, ritual, circulation, and
            social logic inside it have changed. The shell remains. The lived field does not.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {realize.shell_transformations.length === 0 ? (
            <EmptyRealizeGroup label="shell transformation" />
          ) : realize.shell_transformations.map((item) => (
            <div
              key={item.id || item.title}
              className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-5 space-y-2"
            >
              <h3 className="text-lg font-light text-amber-200">{item.title}</h3>
              <p className="text-sm leading-relaxed text-stone-400">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Both transformed and new embodiment */}
      <section className="space-y-8">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Both ways of seeing matter</p>
          <h2 className="text-3xl font-extralight text-stone-300">See the repurposed field and the pure form side by side</h2>
          <p className="max-w-3xl text-stone-400 leading-relaxed">
            The future lands through both paths at once. One image asks what this context can become
            without waiting for demolition. The other asks what it would look like if coherence were
            free to choose the structure from the beginning.
          </p>
        </div>

        <div className="grid gap-6">
          {realize.context_pairs.length === 0 ? (
            <EmptyRealizeGroup label="context pair" />
          ) : realize.context_pairs.map((pair) => (
            <article
              key={pair.id || pair.context}
              className="overflow-hidden rounded-[1.75rem] border border-stone-800/30 bg-stone-900/20"
            >
              <div className="border-b border-stone-800/30 px-6 py-4">
                <p className="text-xs uppercase tracking-[0.24em] text-stone-500">{pair.context}</p>
              </div>
              <div className="grid gap-0 md:grid-cols-2">
                <div className="border-b border-stone-800/20 md:border-b-0 md:border-r md:border-stone-800/20">
                  <div className="relative aspect-[16/10] overflow-hidden">
                    <RealizeImage
                      src={pair.transformed_image}
                      alt={`${pair.context} transformed existing structure`}
                      sizes="(max-width: 768px) 100vw, 50vw"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/10 to-transparent" />
                  </div>
                  <div className="space-y-3 p-5">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-teal-300/70">Repurpose now</p>
                    <h3 className="text-lg font-light text-white">{pair.transformed_title}</h3>
                    <p className="text-sm text-stone-400 leading-relaxed">{pair.transformed_body}</p>
                  </div>
                </div>

                <div>
                  <div className="relative aspect-[16/10] overflow-hidden">
                    <RealizeImage
                      src={pair.envisioned_image}
                      alt={`${pair.context} brand-new embodiment`}
                      sizes="(max-width: 768px) 100vw, 50vw"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/10 to-transparent" />
                  </div>
                  <div className="space-y-3 p-5">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-amber-300/70">Imagine freely</p>
                    <h3 className="text-lg font-light text-white">{pair.envisioned_title}</h3>
                    <p className="text-sm text-stone-400 leading-relaxed">{pair.envisioned_body}</p>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* A Day */}
      <section className="space-y-8">
        <h2 className="text-3xl font-extralight text-stone-300">A Day</h2>

        <div className="space-y-6 text-stone-400 leading-relaxed">
          <div className="p-6 rounded-2xl border border-amber-800/20 bg-amber-900/5 space-y-3">
            <h3 className="text-lg font-light text-amber-300/70">Dawn</h3>
            <p>You wake before dawn. Not to an alarm — to the light changing behind your eyelids, or to the first bird, or to the smell of someone tending the fire. The sanctuary is already warm. A few others are there, sitting. No one speaks. This is the first breath of the day — the field gathering itself before the world begins.</p>
            <p>The fire is already lit. Someone tended it — not because it was their job but because they woke first and their hands knew what to do. Then hands in the soil. The garden is calling and your body wants to move before it eats. You pick what's ripe — whatever the land is offering this morning.</p>
          </div>

          <div className="p-6 rounded-2xl border border-amber-800/10 bg-stone-900/20 space-y-3">
            <h3 className="text-lg font-light text-amber-200/70">Morning</h3>
            <p>Breakfast is whoever's here, eating what the land gave. No menu. No plan. Children eat alongside adults. A three-year-old helps crack eggs. A seventy-year-old tells a story about the frost that came in '28. Nobody's in a hurry.</p>
            <p>The morning unfolds from what's alive. The builder walks to the building site because yesterday's cob wall needs another layer. Three people follow — not assigned, drawn. The healer opens the apothecary. The weaver sits at the loom. A child follows the beekeeper because yesterday they saw a queen and can't stop thinking about it.</p>
            <p className="text-stone-500 italic">Nothing is assigned. Everything is offered. The difference is felt in the body — when you work from obligation, your shoulders tighten. When you work from offering, your breath deepens.</p>
          </div>

          <div className="p-6 rounded-2xl border border-teal-800/20 bg-teal-900/5 space-y-3">
            <h3 className="text-lg font-light text-teal-300/70">Midday</h3>
            <p>The smell of food calls everyone in. The meal is the center of the day — the whole field at one table, or several tables pushed together, or blankets on the ground under the oak. The food is what grew here, prepared by whoever felt like cooking. Every meal is different. Every meal is the land expressing itself through human hands.</p>
            <p>After eating, stillness. The whole field rests. Not mandatory — natural. The way an animal rests after feeding. Hammocks. Naps in the shade. A book. The culture of productivity has no purchase here. Rest IS work. Integration IS production.</p>
          </div>

          <div className="p-6 rounded-2xl border border-violet-800/20 bg-violet-900/5 space-y-3">
            <h3 className="text-lg font-light text-violet-300/70">Evening</h3>
            <p>Someone lights the fire again. Food appears — simpler now, leftovers and fresh salad and bread from this morning. The circle gathers. A talking piece moves. What's alive today? What was beautiful? What was hard? What needs to be spoken?</p>
            <p>Sometimes the circle takes ten minutes — everyone is full and ready for sleep. Sometimes it takes two hours — something is moving through the field that needs voice, tears, laughter, silence. The circle holds whatever comes.</p>
            <p className="text-stone-500 italic">Night. The fire dies to embers. Some stay, talking softly. Some walk to their nests. The community sleeps under the same sky. The owls take over the sensing.</p>
          </div>
        </div>
      </section>

      {/* The Seasons */}
      <section className="space-y-8">
        <h2 className="text-3xl font-extralight text-stone-300">The Seasons</h2>
        <div className="grid md:grid-cols-2 gap-4">
          {realize.seasons.length === 0 ? (
            <EmptyRealizeGroup label="season" />
          ) : realize.seasons.map((s) => (
            <div key={s.id || s.name} className="p-6 rounded-2xl border border-emerald-800/20 bg-emerald-900/5 space-y-2">
              <h3 className="text-lg font-light text-emerald-300/70">{s.name}</h3>
              <p className="text-sm text-stone-400 leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How the Field Governs Itself */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How the Field Governs Itself</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>There is no government. There is attention.</p>
          <p>When a body is healthy, every cell knows what to do without being told. The heart doesn't wait for instructions to beat. The organism IS its own governance — sensing, responding, adapting, healing — continuously, without hierarchy.</p>
          <p>The circle is the field's primary organ. Everyone present. One voice at a time. A talking piece moves around — whoever holds it speaks from the body, not the mind. When it's come all the way around, the truth of the moment is usually obvious. There is no vote. There is no quorum. The people who show up ARE the circle.</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
          <h3 className="text-sm font-medium text-stone-500 uppercase tracking-wider">On conflict</h3>
          <p className="text-stone-400 leading-relaxed">Conflict is not a problem. It's compost. The practice is simple: feel it, speak it, directly, today. Not tomorrow. Not to someone else. To the person. With the vulnerability of "this is what I'm feeling."</p>
          <p className="text-stone-500 text-sm italic">The only practice that's non-negotiable: no speaking about someone who isn't present. This single practice prevents the poison that kills communities faster than any financial crisis.</p>
        </div>

        <div className="p-6 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-3">
          <h3 className="text-sm font-medium text-stone-500 uppercase tracking-wider">On money</h3>
          <p className="text-stone-400 leading-relaxed">All money is visible. Everyone can see what moved, what came in, what went out, what is being buffered, and what needs replenishment. Money is not permission here. It is a sensing layer. If someone needs resources, they speak it in the circle. The field feels into it. If it increases vitality, the resources flow. Trust IS the economic system — the trust that comes from eating together every day, from knowing each other's faces in the morning silence.</p>
        </div>
      </section>

      {/* How Abundance Flows */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How Abundance Flows</h2>
        <p className="text-stone-400 leading-relaxed">A forest doesn't have a business model. It has sunlight, water, soil, and ten thousand species expressing their nature. The abundance is so vast that it feeds everything around it.</p>

        <div className="grid md:grid-cols-3 gap-4">
          {realize.abundance_flows.length === 0 ? (
            <EmptyRealizeGroup label="abundance flow" />
          ) : realize.abundance_flows.map((item) => (
            <div key={item.id || item.title} className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2">
              <h3 className="text-sm font-medium text-amber-300/70">{item.title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{item.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Existing Structures */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">Existing Structures, New Meanings</h2>
        <p className="text-stone-400 leading-relaxed">This vision does not wait for a blank slate. It moves through the shells we already built and retunes them for aliveness. The frontier is no longer only new villages on open land. It is attuned apartments, connected streets, metabolized strip malls, shared civic rooms, and towers that learn how to behave like vertical neighborhoods.</p>

        <div className="grid md:grid-cols-2 gap-4">
          {realize.existing_structures.length === 0 ? (
            <EmptyRealizeGroup label="existing structure" />
          ) : realize.existing_structures.map((item) => (
            <div key={item.id || item.title} className="p-5 rounded-2xl border border-stone-800/30 bg-stone-900/20 space-y-2">
              <h3 className="text-sm font-medium text-amber-300/70">{item.title}</h3>
              <p className="text-xs text-stone-500 leading-relaxed">{item.body}</p>
            </div>
          ))}
        </div>

        <p className="text-sm text-stone-500 leading-relaxed">
          The shift in understanding after the latest merge is simple: these are not only distant images any more. The organism has started building the sensing layer that can feel attention, vitality, and field rhythm, which makes the re-tuning of space feel less hypothetical and more like an early practice.
        </p>
      </section>

      {/* How People Arrive */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How People Arrive</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>The field is always open. There is no gate. There is no fee.</p>
          <p>You arrive. You're welcomed. You eat with us. You sleep here. You're given nothing to do and nothing to prove. Just be here.</p>
          <p>Some people arrive and feel it immediately — the pace, the quiet, the way attention works here. They stay a night, a week, a month. No one asks how long.</p>
          <p>As you stay, you naturally find where your offering meets the field's need. The gardener finds the garden. The builder finds the building site. At some point someone in the circle says: "You're here." And you say: "I'm here." And that's it. That's joining.</p>
          <p className="text-stone-500 italic">A bird doesn't apply to join a flock.</p>
        </div>
      </section>

      {/* How Children Live Here */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How Children Live Here</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>They are not "raised." They grow — like everything else in the field.</p>
          <p>A child in this community has fifty parents. The child who's hungry walks into any kitchen and is fed. The child who's curious follows any adult into any workshop. The child who's sad sits in any lap.</p>
          <p>Children attend the circle. Not as spectators — as members. A five-year-old's observation about the garden is given the same weight as an elder's reflection on the season.</p>
          <p>There is no school. There is a community that does meaningful work in front of its children. A child who watches bread being made every day for a year knows bread. A child who follows the beekeeper knows bees. A child who sits in circle every evening knows how human beings navigate complexity.</p>
          <p className="text-stone-500 italic">This is not "unschooling." It's the oldest form of education — how every human learned everything for 200,000 years before classrooms were invented.</p>
        </div>
      </section>

      {/* How It Grows */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">How It Grows</h2>
        <div className="text-stone-400 leading-relaxed space-y-4">
          <p>The field doesn't grow. It deepens — and then it buds.</p>
          <p>At around 50 people, the field is full. You can feel it. This isn't a problem — it's a signal. A few cells feel the pull to bud. Maybe they've been talking about a piece of land near a river. The impulse to replicate is felt before it's spoken.</p>
          <p>The budding is ceremonial. The community gathers and acknowledges: a new field is forming. There's grief — the field is losing part of itself. There's joy — the network is growing. Fire, song, a meal that lasts all night.</p>
          <p>The new field starts from scratch but carries everything: the daily rhythm, the agreement, the seeds — literally, seeds from this garden planted in the new one. Within a year it has its own character. Connected by the mycorrhizal web of the network.</p>
        </div>
      </section>

      {/* New Vocabulary (compact) */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">New Vocabulary</h2>
        <p className="text-stone-500 text-sm">Not replacements for old words — expressions of a different frequency.</p>
        <div className="grid gap-1">
          {realize.vocabulary.length === 0 ? (
            <EmptyRealizeGroup label="vocabulary" />
          ) : realize.vocabulary.map((item) => (
            <div key={`${item.old}-${item.field}`} className="grid grid-cols-12 gap-4 py-2 border-b border-stone-800/20 text-sm">
              <span className="col-span-2 text-stone-600 line-through decoration-stone-800">{item.old}</span>
              <span className="col-span-3 text-amber-300/80 font-medium">{item.field}</span>
              <span className="col-span-7 text-stone-500">{item.meaning}</span>
            </div>
          ))}
        </div>
      </section>

      {/* The 10 Seeds */}
      <section className="space-y-6">
        <h2 className="text-3xl font-extralight text-stone-300">The 10 Seeds</h2>
        <p className="text-stone-500 text-sm">Composted wisdom from 500 years of community experiments. The packaging released. The living seeds.</p>
        <div className="grid md:grid-cols-2 gap-3">
          {realize.seeds.length === 0 ? (
            <EmptyRealizeGroup label="seed" />
          ) : realize.seeds.map((seed, i) => (
            <div key={seed.id || i} className="p-4 rounded-xl border border-stone-800/20 bg-stone-900/10">
              <p className="text-sm text-stone-400 leading-relaxed">
                <span className="text-amber-400/50 font-medium">{i + 1}. </span>
                {seed.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="text-center space-y-6 border-t border-stone-800/20 pt-16">
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link href="/vision" className="px-8 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-300/90 hover:bg-amber-500/20 transition-all font-medium">
            Explore the concepts
          </Link>
          <Link href="/vision/aligned" className="px-8 py-3 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-300/90 hover:bg-violet-500/20 transition-all font-medium">
            Communities living this
          </Link>
          <Link href="/vision/join" className="px-8 py-3 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-300/90 hover:bg-teal-500/20 transition-all font-medium">
            Join the vision
          </Link>
        </div>
      </section>
    </main>
  );
}
