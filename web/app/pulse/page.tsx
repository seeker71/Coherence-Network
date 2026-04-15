import type { Metadata } from "next";
import Link from "next/link";

import { getPulseBaseServer } from "@/lib/pulse-server";

import { OrganRow } from "./organ-row";
import { OverallBanner } from "./overall-banner";
import { RangeToggle } from "./range-toggle";
import { SilenceList } from "./silence-list";
import { WitnessQuiet } from "./witness-quiet";
import type { PulseHistory, PulseNow, PulseSilences } from "./types";

export const metadata: Metadata = {
  title: "Pulse",
  description:
    "The breath of our living body, remembered. Uptime, silences, and the pulse of Coherence Network's organs.",
};

// Re-render at most once per minute. The witness probes every 30s, so
// anything finer is wasted work.
export const revalidate = 60;

const ALLOWED_DAYS = [7, 30, 90] as const;
const DEFAULT_DAYS = 90;

type PulseSnapshot = {
  now: PulseNow | null;
  history: PulseHistory | null;
  silences: PulseSilences | null;
};

async function loadPulse(base: string, days: number): Promise<PulseSnapshot> {
  if (!base) return { now: null, history: null, silences: null };

  const opts: RequestInit = { cache: "no-store" };
  const urls = [
    `${base}/pulse/now`,
    `${base}/pulse/history?days=${days}`,
    `${base}/pulse/silences?days=${days}`,
  ];

  try {
    const responses = await Promise.all(
      urls.map((u) =>
        fetch(u, opts).catch((err) => {
          console.warn(`[pulse] fetch failed: ${u}`, err);
          return null;
        }),
      ),
    );
    const [nowRes, historyRes, silencesRes] = responses;

    const now = nowRes && nowRes.ok ? ((await nowRes.json()) as PulseNow) : null;
    const history =
      historyRes && historyRes.ok
        ? ((await historyRes.json()) as PulseHistory)
        : null;
    const silences =
      silencesRes && silencesRes.ok
        ? ((await silencesRes.json()) as PulseSilences)
        : null;

    return { now, history, silences };
  } catch (err) {
    console.warn("[pulse] loadPulse crashed", err);
    return { now: null, history: null, silences: null };
  }
}

function resolveDays(raw: string | string[] | undefined): number {
  const s = Array.isArray(raw) ? raw[0] : raw;
  const n = Number(s);
  if (ALLOWED_DAYS.includes(n as (typeof ALLOWED_DAYS)[number])) return n;
  return DEFAULT_DAYS;
}

export default async function PulsePage({
  searchParams,
}: {
  searchParams?: Promise<{ days?: string | string[] }>;
}) {
  const params = (await searchParams) ?? {};
  const days = resolveDays(params.days);
  const pulseBase = getPulseBaseServer();
  const { now, history, silences } = await loadPulse(pulseBase, days);
  const witnessAlive = now !== null && history !== null;

  const organsNowByName = new Map(
    (now?.organs ?? []).map((o) => [o.name, o]),
  );
  const silenceList = silences?.silences ?? [];

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <span className="relative inline-flex h-3 w-3" aria-hidden="true">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/40" />
              <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500/80" />
            </span>
            <h1 className="text-3xl font-bold tracking-tight">Pulse</h1>
          </div>
          {witnessAlive && <RangeToggle active={days} />}
        </div>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          The breath of our living body, remembered. An external witness
          listens to every organ of the network and writes down what it
          hears, so the collective can sense its own health over time.
        </p>
      </header>

      {witnessAlive && now && history ? (
        <>
          <OverallBanner
            overall={now.overall}
            checkedAt={now.checked_at}
            ongoing={now.ongoing_silences}
            historyOverall={history.overall ?? null}
            windowDays={days}
          />

          <section className="space-y-3">
            <h2 className="text-lg font-medium">Organs</h2>
            <div className="space-y-3">
              {history.organs.map((organ) => (
                <OrganRow
                  key={organ.name}
                  history={organ}
                  now={organsNowByName.get(organ.name)}
                  silences={silenceList.filter((s) => s.organ === organ.name)}
                />
              ))}
            </div>
          </section>

          <SilenceList silences={silenceList} />

          <p className="text-[11px] text-muted-foreground/60 text-center">
            Witness started {new Date(now.witness_started_at).toLocaleString()}
            {" · "}
            window {history.days} days
          </p>
        </>
      ) : (
        <WitnessQuiet pulseBase={pulseBase} />
      )}

      {/* Footer navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Also sense the body
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/vitality" className="text-emerald-400 hover:underline">
            Vitality — the deeper signal of life
          </Link>
          <Link href="/identity/keys" className="text-purple-400 hover:underline">
            Attribution — who is moving through the body
          </Link>
          <Link href="/api-health" className="text-blue-400 hover:underline">
            API health — raw, current
          </Link>
          <Link href="/diagnostics" className="text-amber-400 hover:underline">
            Diagnostics
          </Link>
        </div>
      </nav>
    </main>
  );
}
