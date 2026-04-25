import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "The Gathering — The Living Collective",
  description:
    "People sensing the field, gatherings that let them meet, and visible ways presence, creativity, and wisdom become contribution.",
};

export const dynamic = "force-dynamic";

type CommunityMember = {
  id: string;
  name: string;
  location?: string;
  skills?: string;
  offering?: string;
  resonant_roles: string[];
};

type InterestStats = {
  total_interested: number;
  findable_count: number;
  role_interest: Record<string, number>;
  location_regions: Record<string, number>;
};

const ROLE_LABELS: Record<string, string> = {
  "living-structure-weaver": "Living-structure weaver",
  "nourishment-alchemist": "Nourishment alchemist",
  "frequency-holder": "Frequency holder",
  "vitality-keeper": "Vitality keeper",
  "transmission-source": "Transmission source",
  "form-grower": "Form-grower",
};

const ROLE_COLORS: Record<string, string> = {
  "living-structure-weaver": "border-amber-500/20 bg-amber-500/10 text-amber-300/80",
  "nourishment-alchemist": "border-emerald-500/20 bg-emerald-500/10 text-emerald-300/80",
  "frequency-holder": "border-violet-500/20 bg-violet-500/10 text-violet-300/80",
  "vitality-keeper": "border-rose-500/20 bg-rose-500/10 text-rose-300/80",
  "transmission-source": "border-sky-500/20 bg-sky-500/10 text-sky-300/80",
  "form-grower": "border-orange-500/20 bg-orange-500/10 text-orange-300/80",
};

const GATHERING_TYPES = [
  {
    title: "Presence circles",
    image: "/visuals/life-morning-circle.png",
    body:
      "Small groups that let people arrive as nervous systems first. Breath slows, names land, and a room becomes a field instead of a crowd.",
  },
  {
    title: "Creation sessions",
    image: "/visuals/life-creation-workshop.png",
    body:
      "Making together reveals a different kind of resonance. The builder, singer, cook, healer, and gardener become legible through shared doing.",
  },
  {
    title: "Seasonal convergences",
    image: "/visuals/network-midsummer-gathering.png",
    body:
      "Larger gatherings help cells from different places find each other, compare notes, and carry momentum back into their local host spaces.",
  },
];

const CONTRIBUTION_CURRENTS = [
  {
    title: "Presence",
    tone: "text-amber-300/80 border-amber-500/20 bg-amber-500/10",
    body:
      "Listening, holding a room, staying with complexity, steadying a gathering, and making other people easier to be fully here with.",
  },
  {
    title: "Creative energy",
    tone: "text-teal-300/80 border-teal-500/20 bg-teal-500/10",
    body:
      "Cooking, building, composing, designing, repairing, facilitating, gardening, singing, and every form that turns vitality into shared experience.",
  },
  {
    title: "Wisdom and pattern memory",
    tone: "text-violet-300/80 border-violet-500/20 bg-violet-500/10",
    body:
      "Mentoring, eldering, conflict sensing, teaching, storytelling, and helping a field remember what it already knows when the signal gets faint.",
  },
];

export default async function CommunityPage() {
  const base = getApiBase();

  const [membersRes, statsRes] = await Promise.all([
    fetch(`${base}/api/interest/community?limit=200`, { next: { revalidate: 30 } })
      .then((r) => r.json())
      .catch(() => []),
    fetch(`${base}/api/interest/stats`, { next: { revalidate: 30 } })
      .then((r) => r.json())
      .catch(() => ({
        total_interested: 0,
        findable_count: 0,
        role_interest: {},
        location_regions: {},
      })),
  ]);

  const members: CommunityMember[] = Array.isArray(membersRes) ? membersRes : [];
  const stats: InterestStats = statsRes;

  return (
    <main className="max-w-6xl mx-auto px-6 py-20 space-y-20">
      <section className="relative overflow-hidden rounded-[2rem] border border-stone-800/30 bg-stone-950/60 px-6 py-16 md:px-12 md:py-20">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(251,191,36,0.12),_transparent_35%),radial-gradient(circle_at_bottom_right,_rgba(45,212,191,0.12),_transparent_30%),radial-gradient(circle_at_bottom_left,_rgba(196,181,253,0.1),_transparent_28%)]" />
        <div className="relative space-y-6 text-center">
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400/70">People who feel the field</p>
          <h1 className="text-4xl font-extralight tracking-tight text-white md:text-6xl">
            The{" "}
            <span className="bg-gradient-to-r from-amber-300 via-teal-300 to-violet-300 bg-clip-text text-transparent">
              gathering
            </span>
          </h1>
          <p className="mx-auto max-w-3xl text-xl font-light leading-relaxed text-stone-300">
            A gathering is where aligned cells become visible to each other. Some arrive through
            quiet presence. Some through creative overflow. Some through wisdom, care, or pattern
            memory. The field needs all of it.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-2 text-sm">
            <Link
              href="/vision/aligned"
              className="rounded-full border border-stone-700/40 bg-stone-900/30 px-4 py-2 text-stone-300 transition-colors hover:border-amber-500/30 hover:text-amber-200"
            >
              Aligned hosts
            </Link>
            <Link
              href="/vision/lived"
              className="rounded-full border border-stone-700/40 bg-stone-900/30 px-4 py-2 text-stone-300 transition-colors hover:border-violet-500/30 hover:text-violet-200"
            >
              Lived experience
            </Link>
            <Link
              href="/vision/join"
              className="rounded-full border border-stone-700/40 bg-stone-900/30 px-4 py-2 text-stone-300 transition-colors hover:border-teal-500/30 hover:text-teal-200"
            >
              Join the field
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        {GATHERING_TYPES.map((item) => (
          <article
            key={item.title}
            className="overflow-hidden rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20"
          >
            <div className="relative aspect-[5/4] overflow-hidden">
              <Image
                src={item.image}
                alt={item.title}
                fill
                className="object-cover"
                sizes="(max-width: 1024px) 100vw, 33vw"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-stone-950/15 to-transparent" />
            </div>
            <div className="space-y-3 p-6">
              <h2 className="text-xl font-light text-white">{item.title}</h2>
              <p className="text-sm leading-relaxed text-stone-400">{item.body}</p>
            </div>
          </article>
        ))}
      </section>

      {stats.total_interested > 0 && (
        <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-stone-800/30 bg-stone-900/20 p-6 text-center">
            <div className="text-3xl font-light text-amber-300/80">{stats.total_interested}</div>
            <div className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-600">souls resonating</div>
          </div>
          <div className="rounded-2xl border border-stone-800/30 bg-stone-900/20 p-6 text-center">
            <div className="text-3xl font-light text-teal-300/80">{stats.findable_count}</div>
            <div className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-600">publicly visible</div>
          </div>
          <div className="rounded-2xl border border-stone-800/30 bg-stone-900/20 p-6 text-center">
            <div className="text-3xl font-light text-violet-300/80">
              {Object.keys(stats.location_regions).length}
            </div>
            <div className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-600">regions</div>
          </div>
          <div className="rounded-2xl border border-stone-800/30 bg-stone-900/20 p-6 text-center">
            <div className="text-3xl font-light text-rose-300/80">
              {Object.values(stats.role_interest).reduce((a, b) => a + b, 0)}
            </div>
            <div className="mt-1 text-xs uppercase tracking-[0.24em] text-stone-600">role resonances</div>
          </div>
        </section>
      )}

      <section className="space-y-8">
        <div className="space-y-3">
          <p className="text-sm uppercase tracking-[0.28em] text-stone-500">How contribution becomes visible</p>
          <h2 className="text-3xl font-extralight text-stone-200">A gathering senses more than credentials</h2>
          <p className="max-w-3xl text-stone-400">
            When people meet in real space, the field can sense tone, timing, generosity, steadiness,
            skill, and relational intelligence directly. That makes contribution broader and more honest.
          </p>
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          {CONTRIBUTION_CURRENTS.map((current) => (
            <div
              key={current.title}
              className={`rounded-[1.5rem] border p-6 ${current.tone}`}
            >
              <h3 className="text-xl font-light text-white">{current.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-300">{current.body}</p>
            </div>
          ))}
        </div>
      </section>

      {members.length > 0 ? (
        <section className="space-y-8">
          <div className="space-y-3">
            <p className="text-sm uppercase tracking-[0.28em] text-stone-500">Visible cells</p>
            <h2 className="text-3xl font-extralight text-stone-200">People already choosing to be seen</h2>
            <p className="max-w-3xl text-stone-400">
              This directory is consent-based. Everyone shown here chose visibility so aligned hosts,
              gatherings, and future communities can sense where resonance is already clustering.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {members.map((member) => (
              <article
                key={member.id}
                className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 p-6 transition-colors hover:border-stone-700/40"
              >
                <h3 className="text-lg font-light text-stone-100">{member.name}</h3>
                {member.location && <p className="mt-1 text-sm text-stone-500">{member.location}</p>}
                {member.skills && (
                  <p className="mt-4 text-sm leading-relaxed text-stone-300">{member.skills}</p>
                )}
                {member.offering && (
                  <p className="mt-3 text-sm italic leading-relaxed text-stone-500">{member.offering}</p>
                )}
                {member.resonant_roles.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-1.5">
                    {member.resonant_roles.map((role) => (
                      <span
                        key={role}
                        className={`rounded-full border px-2.5 py-1 text-xs ${
                          ROLE_COLORS[role] || "border-stone-700/30 bg-stone-800/30 text-stone-500"
                        }`}
                      >
                        {ROLE_LABELS[role] || role}
                      </span>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </div>
        </section>
      ) : (
        <section className="rounded-[1.5rem] border border-stone-800/30 bg-stone-900/20 px-6 py-12 text-center">
          <div className="text-5xl opacity-30">◉</div>
          <p className="mt-4 text-lg text-stone-400">
            The visible directory is still forming. The next gathering starts by letting yourself be found.
          </p>
        </section>
      )}

      <section className="rounded-[2rem] border border-stone-800/30 bg-gradient-to-br from-stone-900/50 via-stone-950/70 to-stone-900/30 px-6 py-14 text-center md:px-12">
        <h2 className="text-3xl font-extralight text-white md:text-4xl">
          Gatherings are how a future community rehearses itself
        </h2>
        <p className="mx-auto mt-4 max-w-3xl text-lg font-light leading-relaxed text-stone-300">
          A field becomes more real every time people meet with enough honesty, beauty, and shared
          activity to recognize each other beyond role and transaction. That recognition is part of the build.
        </p>
        <div className="mt-8 flex flex-col justify-center gap-4 sm:flex-row">
          <Link
            href="/vision/join#register"
            className="rounded-xl border border-amber-500/20 bg-amber-500/10 px-8 py-3 font-medium text-amber-200 transition-colors hover:bg-amber-500/20"
          >
            Join the field
          </Link>
          <Link
            href="/vision/aligned"
            className="rounded-xl border border-teal-500/20 bg-teal-500/10 px-8 py-3 font-medium text-teal-200 transition-colors hover:bg-teal-500/20"
          >
            Explore aligned hosts
          </Link>
        </div>
      </section>
    </main>
  );
}
