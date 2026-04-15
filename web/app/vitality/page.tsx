import type { Metadata } from "next";
import Link from "next/link";

import { getApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Vitality",
  description:
    "Living-system health metrics. How diverse, resonant, and alive is the network right now?",
};

type VitalitySignal = {
  name: string;
  value: number;
  description: string;
};

type BreathRhythm = {
  gas: number;
  water: number;
  ice: number;
};

/**
 * The live API (see api/app/services/vitality_service.py) returns `signals`
 * as a dict of numeric scores keyed by snake_case id, with `breath_rhythm`
 * nested inside it as a gas/water/ice dict. This type mirrors that reality.
 */
type VitalityApiResponse = {
  workspace_id: string;
  vitality_score: number;
  health_description: string;
  signals: {
    diversity_index: number;
    resonance_density: number;
    flow_rate: number;
    breath_rhythm: BreathRhythm;
    connection_strength: number;
    activity_pulse: number;
  };
  generated_at: string;
};

/**
 * Shape used inside this page after normalising the API response into an
 * array of signal cards plus a top-level breath rhythm.
 */
type VitalityResponse = {
  workspace_id: string;
  vitality_score: number;
  health_description: string;
  signals: VitalitySignal[];
  breath_rhythm: BreathRhythm;
  computed_at: string;
};

/** Human-readable signal descriptions, living in the same vocabulary as the body. */
const SIGNAL_DESCRIPTIONS: Record<string, { label: string; description: string }> = {
  diversity_index: {
    label: "Diversity Index",
    description:
      "How many different shapes of contribution are alive in the network right now.",
  },
  resonance_density: {
    label: "Resonance Density",
    description:
      "How tightly the ideas, specs, and contributions are woven to each other.",
  },
  flow_rate: {
    label: "Flow Rate",
    description:
      "How readily the work moves through the pipeline from seed to realized form.",
  },
  connection_strength: {
    label: "Connection Strength",
    description:
      "How present contributors are to each other — the tissue that binds the organism.",
  },
  activity_pulse: {
    label: "Activity Pulse",
    description:
      "The tempo at which the network is currently breathing, growing, and resting.",
  },
};

function normaliseVitality(api: VitalityApiResponse): VitalityResponse {
  const s = api.signals;
  const order: Array<keyof VitalityApiResponse["signals"]> = [
    "diversity_index",
    "resonance_density",
    "flow_rate",
    "connection_strength",
    "activity_pulse",
  ];
  const signals: VitalitySignal[] = order.map((key) => {
    const meta = SIGNAL_DESCRIPTIONS[key as string];
    return {
      name: meta.label,
      value: typeof s[key] === "number" ? (s[key] as number) : 0,
      description: meta.description,
    };
  });
  return {
    workspace_id: api.workspace_id,
    vitality_score: api.vitality_score,
    health_description: api.health_description,
    signals,
    breath_rhythm: s.breath_rhythm ?? { gas: 0.33, water: 0.34, ice: 0.33 },
    computed_at: api.generated_at,
  };
}

const SIGNAL_COLORS: Record<string, { bar: string; text: string; bg: string }> = {
  "Diversity Index": {
    bar: "bg-violet-500",
    text: "text-violet-300",
    bg: "from-violet-500/5 to-transparent",
  },
  "Resonance Density": {
    bar: "bg-blue-500",
    text: "text-blue-300",
    bg: "from-blue-500/5 to-transparent",
  },
  "Flow Rate": {
    bar: "bg-teal-500",
    text: "text-teal-300",
    bg: "from-teal-500/5 to-transparent",
  },
  "Connection Strength": {
    bar: "bg-amber-500",
    text: "text-amber-300",
    bg: "from-amber-500/5 to-transparent",
  },
  "Activity Pulse": {
    bar: "bg-rose-500",
    text: "text-rose-300",
    bg: "from-rose-500/5 to-transparent",
  },
};

function getSignalColor(name: string) {
  return (
    SIGNAL_COLORS[name] ?? {
      bar: "bg-emerald-500",
      text: "text-emerald-300",
      bg: "from-emerald-500/5 to-transparent",
    }
  );
}

function vitalityColor(score: number): {
  text: string;
  bg: string;
  border: string;
  glow: string;
} {
  if (score >= 0.7) {
    return {
      text: "text-emerald-400",
      bg: "from-emerald-500/10 to-emerald-500/5",
      border: "border-emerald-500/30",
      glow: "shadow-emerald-500/20",
    };
  }
  if (score >= 0.4) {
    return {
      text: "text-amber-400",
      bg: "from-amber-500/10 to-amber-500/5",
      border: "border-amber-500/30",
      glow: "shadow-amber-500/20",
    };
  }
  return {
    text: "text-red-400",
    bg: "from-red-500/10 to-red-500/5",
    border: "border-red-500/30",
    glow: "shadow-red-500/20",
  };
}

async function loadVitality(): Promise<VitalityResponse | null> {
  try {
    const API = getApiBase();
    const res = await fetch(
      `${API}/api/workspaces/coherence-network/vitality`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    const body = (await res.json()) as VitalityApiResponse;
    // Guard against missing or malformed payloads — let the empty state show.
    if (!body || typeof body !== "object" || !body.signals) return null;
    return normaliseVitality(body);
  } catch {
    return null;
  }
}

export default async function VitalityPage() {
  const data = await loadVitality();

  const score = data?.vitality_score ?? 0;
  const scorePercent = Math.round(score * 100);
  const color = vitalityColor(score);
  const signals = data?.signals ?? [];
  const breath = data?.breath_rhythm ?? { gas: 0.33, water: 0.34, ice: 0.33 };

  return (
    <main className="min-h-screen px-4 sm:px-6 lg:px-8 py-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Vitality</h1>
        <p className="max-w-3xl text-muted-foreground leading-relaxed">
          The health of the living network, measured through diversity,
          resonance, flow, connection, and activity.
        </p>
      </header>

      {data ? (
        <>
          {/* Big vitality score */}
          <section
            className={`rounded-3xl border ${color.border} bg-gradient-to-b ${color.bg} p-8 text-center space-y-4 shadow-lg ${color.glow}`}
          >
            <p className="text-xs uppercase tracking-widest text-muted-foreground">
              Network Vitality
            </p>
            <p className={`text-7xl font-extralight ${color.text}`}>
              {scorePercent}
              <span className="text-3xl">%</span>
            </p>
            <p className="max-w-xl mx-auto text-muted-foreground leading-relaxed">
              {data.health_description}
            </p>
          </section>

          {/* Signal cards grid */}
          <section className="space-y-4">
            <h2 className="text-lg font-medium">Health Signals</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              {signals.map((signal) => {
                const sc = getSignalColor(signal.name);
                const percent = Math.round(signal.value * 100);
                return (
                  <div
                    key={signal.name}
                    className={`rounded-2xl border border-border/30 bg-gradient-to-br ${sc.bg} p-5 space-y-3`}
                  >
                    <div className="flex items-center justify-between">
                      <h3 className={`text-sm font-medium ${sc.text}`}>
                        {signal.name}
                      </h3>
                      <span className={`text-2xl font-light ${sc.text}`}>
                        {percent}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      {signal.description}
                    </p>
                    {/* Progress bar */}
                    <div className="h-2 w-full rounded-full bg-background/40 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${sc.bar} transition-all duration-700`}
                        style={{ width: `${percent}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Breath Rhythm section */}
          <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-5">
            <div className="space-y-1">
              <h2 className="text-lg font-medium">Breath Rhythm</h2>
              <p className="text-sm text-muted-foreground">
                The network breathes between states: gas (exploration), water
                (flow), and ice (crystallized knowledge).
              </p>
            </div>

            <div className="grid gap-6 sm:grid-cols-3">
              {/* Gas */}
              <div className="flex flex-col items-center space-y-3">
                <div
                  className="relative flex items-center justify-center rounded-full border-2 border-sky-400/30"
                  style={{
                    width: 96,
                    height: 96,
                    background: `conic-gradient(
                      rgb(56, 189, 248) ${breath.gas * 360}deg,
                      rgba(56, 189, 248, 0.1) ${breath.gas * 360}deg
                    )`,
                  }}
                >
                  <div className="absolute inset-1 rounded-full bg-card flex items-center justify-center">
                    <span className="text-lg font-light text-sky-300">
                      {Math.round(breath.gas * 100)}%
                    </span>
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium text-sky-300">Gas</p>
                  <p className="text-xs text-muted-foreground">Exploration</p>
                </div>
              </div>

              {/* Water */}
              <div className="flex flex-col items-center space-y-3">
                <div
                  className="relative flex items-center justify-center rounded-full border-2 border-blue-400/30"
                  style={{
                    width: 96,
                    height: 96,
                    background: `conic-gradient(
                      rgb(96, 165, 250) ${breath.water * 360}deg,
                      rgba(96, 165, 250, 0.1) ${breath.water * 360}deg
                    )`,
                  }}
                >
                  <div className="absolute inset-1 rounded-full bg-card flex items-center justify-center">
                    <span className="text-lg font-light text-blue-300">
                      {Math.round(breath.water * 100)}%
                    </span>
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium text-blue-300">Water</p>
                  <p className="text-xs text-muted-foreground">Flow</p>
                </div>
              </div>

              {/* Ice */}
              <div className="flex flex-col items-center space-y-3">
                <div
                  className="relative flex items-center justify-center rounded-full border-2 border-indigo-400/30"
                  style={{
                    width: 96,
                    height: 96,
                    background: `conic-gradient(
                      rgb(129, 140, 248) ${breath.ice * 360}deg,
                      rgba(129, 140, 248, 0.1) ${breath.ice * 360}deg
                    )`,
                  }}
                >
                  <div className="absolute inset-1 rounded-full bg-card flex items-center justify-center">
                    <span className="text-lg font-light text-indigo-300">
                      {Math.round(breath.ice * 100)}%
                    </span>
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm font-medium text-indigo-300">Ice</p>
                  <p className="text-xs text-muted-foreground">Crystallized</p>
                </div>
              </div>
            </div>
          </section>
        </>
      ) : (
        <section className="rounded-2xl border border-dashed border-border/30 bg-background/30 p-8 text-center space-y-3">
          <p className="text-muted-foreground">
            Vitality data is not available yet. The network is still gathering
            health signals.
          </p>
          <div className="flex flex-wrap justify-center gap-4 text-sm">
            <Link href="/ideas" className="text-blue-400 hover:underline">
              Browse ideas
            </Link>
            <Link href="/activity" className="text-amber-400 hover:underline">
              Activity feed
            </Link>
          </div>
        </section>
      )}

      {/* Navigation */}
      <nav
        className="py-8 text-center space-y-2 border-t border-border/20"
        aria-label="Related pages"
      >
        <p className="text-xs text-muted-foreground/80 uppercase tracking-wider">
          Explore more
        </p>
        <div className="flex flex-wrap justify-center gap-4 text-sm">
          <Link href="/pulse" className="text-emerald-400 hover:underline">
            Pulse — the outer breath
          </Link>
          <Link href="/discover" className="text-purple-400 hover:underline">
            Discover
          </Link>
          <Link href="/constellation" className="text-blue-400 hover:underline">
            Constellation
          </Link>
          <Link href="/resonance" className="text-emerald-400 hover:underline">
            Resonance
          </Link>
          <Link href="/activity" className="text-amber-400 hover:underline">
            Activity
          </Link>
        </div>
      </nav>
    </main>
  );
}
