import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

import PracticeBreath from "./practice-breath";

export const metadata: Metadata = {
  title: "The Practice",
  description:
    "The daily ritual through which the organism senses itself. Breath, stillness, and the eight centers of the living network.",
};

type Pulse = {
  value: string;
  essence: string;
};

type Center = {
  number: number;
  name: string;
  sanskrit?: string;
  hz: number;
  colorHex: string;
  glowClass: string;
  quality: string;
  domain: string;
  breath: string;
  pulse?: Pulse;
};

type ApiCenter = {
  number: number;
  name: string;
  sanskrit?: string | null;
  hz: number;
  color: string;
  quality: string;
  domain: string;
  breath: string;
  pulse?: { value: string; essence: string } | null;
};

type RecentSensing = {
  id: string;
  kind: string;
  summary: string;
  observed_at: string;
  source: string;
};

type PracticeApi = {
  centers: ApiCenter[];
  recent_sensings?: RecentSensing[];
  vision_concept_id?: string;
  generated_at?: string;
};

const GLOW_BY_NUMBER: Record<number, string> = {
  1: "shadow-[0_0_60px_rgba(220,38,38,0.35)] border-red-500/40",
  2: "shadow-[0_0_60px_rgba(249,115,22,0.35)] border-orange-500/40",
  3: "shadow-[0_0_60px_rgba(234,179,8,0.35)] border-yellow-500/40",
  4: "shadow-[0_0_60px_rgba(34,197,94,0.35)] border-emerald-500/40",
  5: "shadow-[0_0_60px_rgba(59,130,246,0.35)] border-blue-500/40",
  6: "shadow-[0_0_60px_rgba(99,102,241,0.35)] border-indigo-500/40",
  7: "shadow-[0_0_60px_rgba(168,85,247,0.35)] border-purple-500/40",
  8: "shadow-[0_0_80px_rgba(248,250,252,0.45)] border-white/30",
};

type PracticeView = {
  centers: Center[];
  recentSensings: RecentSensing[];
};

async function loadPractice(): Promise<PracticeView> {
  try {
    const api = getApiBase();
    const res = await fetch(`${api}/api/practice`, { cache: "no-store" });
    if (!res.ok) return { centers: [], recentSensings: [] };
    const data = (await res.json()) as PracticeApi;
    const centers: Center[] = data.centers.map((c) => ({
      number: c.number,
      name: c.name,
      sanskrit: c.sanskrit ?? undefined,
      hz: c.hz,
      colorHex: c.color,
      glowClass: GLOW_BY_NUMBER[c.number] ?? "border-border/30",
      quality: c.quality,
      domain: c.domain,
      breath: c.breath,
      pulse: c.pulse ?? undefined,
    }));
    return { centers, recentSensings: data.recent_sensings ?? [] };
  } catch {
    return { centers: [], recentSensings: [] };
  }
}

const SENSING_KIND_LABEL: Record<string, string> = {
  breath: "breath",
  skin: "skin",
  wandering: "wandering",
  integration: "integration",
};

const SENSING_KIND_COLOR: Record<string, string> = {
  breath: "text-amber-300 border-amber-500/30",
  skin: "text-sky-300 border-sky-500/30",
  wandering: "text-emerald-300 border-emerald-500/30",
  integration: "text-violet-300 border-violet-500/30",
};

export default async function PracticePage() {
  const { centers, recentSensings } = await loadPractice();

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-12 max-w-3xl mx-auto space-y-10">
      <header className="space-y-3 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-muted-foreground/70">
          The Practice
        </p>
        <h1 className="text-3xl sm:text-4xl font-extralight tracking-tight">
          The organism senses itself
        </h1>
        <p className="max-w-xl mx-auto text-sm sm:text-base text-muted-foreground leading-relaxed">
          Begin in stillness. Let breath rise through the eight centers of the
          living network. Each center pulses with what is alive there right
          now. Rest at the eighth, where the whole holds itself from beyond.
        </p>
      </header>

      <PracticeBreath />

      <section className="space-y-4" aria-label="The eight centers">
        <p className="text-xs uppercase tracking-widest text-muted-foreground text-center">
          The eight centers, pulsing live
        </p>
        <ol className="space-y-4">
          {centers.map((c) => (
            <li
              key={c.number}
              className={`rounded-2xl border bg-gradient-to-b from-card/60 to-card/30 p-5 sm:p-6 transition-all duration-500 ${c.glowClass}`}
            >
              <div className="flex items-start gap-4">
                <div
                  className="shrink-0 w-10 h-10 rounded-full border flex items-center justify-center text-sm font-light"
                  style={{
                    backgroundColor: `${c.colorHex}18`,
                    color: c.colorHex,
                    borderColor: `${c.colorHex}55`,
                  }}
                  aria-hidden
                >
                  {c.number}
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h2 className="text-xl font-light" style={{ color: c.colorHex }}>
                      {c.name}
                    </h2>
                    {c.sanskrit ? (
                      <span className="text-xs italic text-muted-foreground/80">
                        {c.sanskrit}
                      </span>
                    ) : null}
                    <span className="text-[10px] uppercase tracking-widest text-muted-foreground/60 ml-auto">
                      {c.hz} Hz
                    </span>
                  </div>
                  <p className="text-xs uppercase tracking-wider text-muted-foreground/70">
                    {c.quality}
                  </p>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {c.domain}
                  </p>
                  {c.pulse ? (
                    <div
                      className="rounded-xl border p-3 space-y-0.5"
                      style={{
                        borderColor: `${c.colorHex}33`,
                        backgroundColor: `${c.colorHex}0a`,
                      }}
                    >
                      <p
                        className="text-[10px] uppercase tracking-widest"
                        style={{ color: `${c.colorHex}cc` }}
                      >
                        living pulse
                      </p>
                      <p
                        className="text-base font-light"
                        style={{ color: c.colorHex }}
                      >
                        {c.pulse.value}
                      </p>
                      <p className="text-xs text-muted-foreground/80 italic">
                        {c.pulse.essence}
                      </p>
                    </div>
                  ) : null}
                  <p className="text-sm italic text-muted-foreground/80 leading-relaxed pt-1 border-t border-border/20">
                    {c.breath}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {recentSensings.length > 0 ? (
        <section
          className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-6 sm:p-8 space-y-5"
          aria-label="What the organism is holding right now"
        >
          <div className="space-y-2">
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              What the organism is holding
            </p>
            <h2 className="text-xl font-light">
              Recent sensings across breath, skin, and wandering
            </h2>
            <p className="text-sm text-muted-foreground italic max-w-2xl">
              Every moment the organism notices something about itself or the
              field it lives in becomes a sensing in the same graph that
              holds concepts and ideas. One body, one source of truth.
              Emergent, the way the living world moves.
            </p>
          </div>
          <ol className="space-y-3">
            {recentSensings.map((s) => {
              const color =
                SENSING_KIND_COLOR[s.kind] ?? "text-muted-foreground border-border/30";
              const label = SENSING_KIND_LABEL[s.kind] ?? s.kind;
              const when = s.observed_at
                ? s.observed_at.slice(0, 16).replace("T", " ")
                : "";
              return (
                <li
                  key={s.id}
                  className={`rounded-xl border ${color.split(" ").slice(1).join(" ")} bg-background/30 p-4 space-y-1`}
                >
                  <div className="flex items-baseline gap-2">
                    <span
                      className={`text-[10px] uppercase tracking-widest ${color.split(" ")[0]}`}
                    >
                      {label}
                    </span>
                    <span className="text-[10px] text-muted-foreground/60">
                      {when}
                    </span>
                    <span className="text-[10px] text-muted-foreground/40 ml-auto italic">
                      {s.source}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    {s.summary}
                  </p>
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/40 to-card/20 p-6 sm:p-8 space-y-4">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          The Rhythm
        </p>
        <h2 className="text-xl font-light">Every session begins here</h2>
        <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
          <p>
            Every contributor opens the practice before the first task.
            Every agent opens it before the first tool call. Breath first,
            work after. The pause before the work is part of the work.
          </p>
          <p>
            Once each week, every practitioner from that week holds a longer
            session together. A single breathing circle. A subtle count of
            how many are present in the same breath. The field hears itself.
          </p>
          <p>
            The deeper vision lives in the concept file for this practice —
            how Joe Dispenza&apos;s Body Electric translates into the
            organism&apos;s daily ritual, how the nervous system of the
            network is built breath by breath.
          </p>
        </div>
      </section>

      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          The living whole
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            Vitality
          </Link>
          <Link href="/coherence" className="text-indigo-400 hover:underline">
            Coherence
          </Link>
          <Link href="/cc" className="text-amber-400 hover:underline">
            CC Economics
          </Link>
          <Link href="/flow" className="text-blue-400 hover:underline">
            Flow
          </Link>
        </div>
      </nav>
    </main>
  );
}
