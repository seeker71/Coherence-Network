"use client";

import { useMemo, useState } from "react";
import {
  AudioLines,
  Feather,
  Focus,
  Hand,
  Leaf,
  Radio,
  Sparkles,
} from "lucide-react";

import {
  INITIAL_LIVING_SIGNALS,
  receiveMovement,
  senseLivingField,
  type LivingSignalEvent,
  type Movement,
  type SignalQuality,
} from "@/lib/living-signal";

const movementControls: Array<{
  movement: Movement;
  label: string;
  icon: typeof AudioLines;
}> = [
  { movement: "attune", label: "Attune", icon: AudioLines },
  { movement: "clarify", label: "Clarify", icon: Focus },
  { movement: "ground", label: "Ground", icon: Leaf },
  { movement: "embody", label: "Embody", icon: Hand },
];

const toneLabels: Record<SignalQuality, string> = {
  gathering: "gathering",
  orienting: "orienting",
  grounding: "grounding",
  embodying: "embodying",
  integrating: "integrating",
  renewing: "renewing",
};

function percent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function SignalBandField({ events }: { events: LivingSignalEvent[] }) {
  const bands = useMemo(() => {
    return events.slice(-7).map((event, index) => {
      const width = 34 + event.intensity * 48;
      const top = 16 + index * 11;
      const delay = index * 0.28;
      return {
        id: event.id,
        width,
        top,
        delay,
        opacity: 0.35 + event.intensity * 0.45,
        color:
          event.surface === "evidence"
            ? "hsl(158 44% 52%)"
            : event.surface === "agent"
              ? "hsl(198 48% 58%)"
              : event.surface === "implementation"
                ? "hsl(285 40% 66%)"
                : event.surface === "community"
                  ? "hsl(45 74% 68%)"
                  : event.surface === "task"
                    ? "hsl(12 70% 66%)"
                    : "hsl(36 82% 62%)",
      };
    });
  }, [events]);

  return (
    <div className="relative h-[330px] overflow-hidden rounded-md border border-white/10 bg-neutral-950">
      <div className="absolute inset-0 bg-[linear-gradient(115deg,rgba(250,204,21,0.08),rgba(20,184,166,0.05)_38%,rgba(244,114,182,0.07)_74%,rgba(10,10,10,0.9))]" />
      <div className="absolute inset-x-8 top-10 h-px bg-white/10" />
      <div className="absolute inset-x-8 bottom-10 h-px bg-white/10" />
      <div className="absolute left-8 top-10 bottom-10 w-px bg-white/10" />
      <div className="absolute right-8 top-10 bottom-10 w-px bg-white/10" />

      {bands.map((band, index) => (
        <div
          key={band.id}
          className="absolute left-8 h-2 rounded-full"
          style={{
            top: `${band.top}%`,
            width: `${band.width}%`,
            background: `linear-gradient(90deg, transparent, ${band.color}, transparent)`,
            opacity: band.opacity,
            transform: `translateX(${(index % 2) * 18}px)`,
            animation: `signalDrift ${5.8 + index * 0.4}s ease-in-out ${band.delay}s infinite alternate`,
          }}
        />
      ))}

      <div className="absolute inset-0 flex items-center justify-center">
        <div className="rounded-md border border-white/10 bg-black/35 px-5 py-4 text-center backdrop-blur">
          <Radio className="mx-auto mb-3 h-5 w-5 text-amber-200" aria-hidden="true" />
          <p className="text-sm uppercase tracking-[0.24em] text-white/50">living signal</p>
          <p className="mt-2 max-w-xs text-balance text-lg font-light text-white">
            the field learns through contact
          </p>
        </div>
      </div>

      <style jsx>{`
        @keyframes signalDrift {
          from {
            transform: translateX(-2%) scaleX(0.96);
          }
          to {
            transform: translateX(18%) scaleX(1.04);
          }
        }
      `}</style>
    </div>
  );
}

function Meter({
  label,
  value,
  detail,
  hue,
}: {
  label: string;
  value: number;
  detail: string;
  hue: string;
}) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.045] p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-white">{label}</p>
          <p className="mt-1 text-xs leading-relaxed text-white/55">{detail}</p>
        </div>
        <p className="text-2xl font-light text-white">{percent(value)}</p>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${percent(value)}%`,
            background: hue,
          }}
        />
      </div>
    </div>
  );
}

export function LivingSignalInstrument() {
  const [events, setEvents] = useState<LivingSignalEvent[]>(INITIAL_LIVING_SIGNALS);
  const field = useMemo(() => senseLivingField(events), [events]);

  function addMovement(movement: Movement) {
    setEvents((current) => receiveMovement(current, movement));
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-white">
      <section className="relative overflow-hidden px-4 py-8 sm:px-6 lg:px-8">
        <div className="absolute inset-0 bg-[linear-gradient(145deg,rgba(250,204,21,0.13),rgba(20,184,166,0.09)_42%,rgba(244,114,182,0.11)_78%,rgba(10,10,10,1))]" />
        <div className="relative mx-auto grid max-w-7xl gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2 rounded-md border border-white/10 bg-white/5 px-3 py-2 text-xs uppercase tracking-[0.22em] text-white/60">
              <Sparkles className="h-3.5 w-3.5 text-amber-200" aria-hidden="true" />
              dynamic signal layer
            </div>
            <div className="space-y-4">
              <h1 className="max-w-4xl text-balance text-4xl font-light leading-tight tracking-tight sm:text-5xl lg:text-6xl">
                A field that senses what is ready to become real.
              </h1>
              <p className="max-w-2xl text-base leading-8 text-white/68 sm:text-lg">
                Each movement changes the guidance. Form shows structure. Pulse shows aliveness.
                The organism learns through contact.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <Meter
                label={`Form vitality · ${field.formVitality.label}`}
                value={field.formVitality.score}
                detail={field.formVitality.detail}
                hue="linear-gradient(90deg,hsl(36 82% 62%),hsl(45 74% 68%))"
              />
              <Meter
                label={`Living pulse · ${field.livingPulse.label}`}
                value={field.livingPulse.score}
                detail={field.livingPulse.detail}
                hue="linear-gradient(90deg,hsl(158 44% 52%),hsl(198 48% 58%),hsl(285 40% 66%))"
              />
            </div>
          </div>

          <SignalBandField events={events} />
        </div>
      </section>

      <section className="border-y border-white/10 bg-neutral-900/95 px-4 py-6 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-md border border-white/10 bg-white/[0.045] p-5">
            <div className="flex items-start gap-3">
              <div className="rounded-md bg-amber-300/12 p-2 text-amber-100">
                <Feather className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-white/45">
                  active tone · {toneLabels[field.activeTone]}
                </p>
                <p className="mt-3 text-pretty text-xl font-light leading-8 text-white" aria-live="polite">
                  {field.guidance}
                </p>
                <p className="mt-4 text-sm leading-7 text-white/62">{field.nextMovement}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-4">
            {movementControls.map(({ movement, label, icon: Icon }) => (
              <button
                key={movement}
                type="button"
                onClick={() => addMovement(movement)}
                className="group rounded-md border border-white/10 bg-white/[0.045] p-4 text-left transition hover:border-amber-200/40 hover:bg-white/[0.075] focus:outline-none focus:ring-2 focus:ring-amber-200/60"
              >
                <Icon className="h-5 w-5 text-white/58 transition group-hover:text-amber-100" aria-hidden="true" />
                <span className="mt-5 block text-sm font-medium text-white">{label}</span>
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="space-y-4">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-white/42">signal qualities</p>
              <h2 className="mt-2 text-2xl font-light tracking-tight text-white">What the field is carrying</h2>
            </div>
            <div className="space-y-3">
              {field.ribbons.map((ribbon) => (
                <div key={ribbon.id} className="rounded-md border border-white/10 bg-white/[0.04] p-4">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-sm capitalize text-white/78">{ribbon.label}</span>
                    <span className="text-sm text-white/45">{percent(ribbon.value)}</span>
                  </div>
                  <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${percent(ribbon.value)}%`, background: ribbon.hue }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-white/42">recent movement</p>
              <h2 className="mt-2 text-2xl font-light tracking-tight text-white">Signals returning as memory</h2>
            </div>
            <div className="grid gap-3">
              {field.recentSignals.map((event) => (
                <article
                  key={event.id}
                  className="grid gap-4 rounded-md border border-white/10 bg-white/[0.04] p-4 sm:grid-cols-[8rem_1fr_auto] sm:items-center"
                >
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-white/35">{formatTime(event.receivedAt)}</p>
                    <p className="mt-1 text-sm capitalize text-white/70">{event.surface}</p>
                  </div>
                  <p className="text-sm leading-7 text-white/72">{event.note}</p>
                  <div className="rounded-md border border-white/10 px-3 py-2 text-sm text-white/62">
                    {percent(event.intensity)}
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
