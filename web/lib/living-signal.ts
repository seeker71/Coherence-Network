export type SignalSurface =
  | "vision"
  | "evidence"
  | "agent"
  | "task"
  | "community"
  | "implementation";

export type SignalQuality =
  | "gathering"
  | "orienting"
  | "grounding"
  | "embodying"
  | "integrating"
  | "renewing";

export type Movement = "attune" | "clarify" | "ground" | "embody";

export type VitalityVector = {
  breath: number;
  clarity: number;
  agency: number;
  grounding: number;
};

export type LivingSignalEvent = {
  id: string;
  surface: SignalSurface;
  quality: SignalQuality;
  intensity: number;
  vitality: VitalityVector;
  receivedAt: string;
  note: string;
};

export type SignalRibbon = {
  id: string;
  label: string;
  value: number;
  hue: string;
};

export type SensedLivingField = {
  formVitality: {
    score: number;
    label: string;
    detail: string;
  };
  livingPulse: {
    score: number;
    label: string;
    trajectory: number;
    detail: string;
  };
  activeTone: SignalQuality;
  guidance: string;
  nextMovement: string;
  ribbons: SignalRibbon[];
  recentSignals: LivingSignalEvent[];
};

const SURFACE_HUES: Record<SignalSurface, string> = {
  vision: "hsl(36 82% 62%)",
  evidence: "hsl(158 42% 50%)",
  agent: "hsl(198 46% 58%)",
  task: "hsl(12 68% 66%)",
  community: "hsl(45 74% 70%)",
  implementation: "hsl(285 38% 66%)",
};

const MOVEMENTS: Record<Movement, Omit<LivingSignalEvent, "id" | "receivedAt">> = {
  attune: {
    surface: "community",
    quality: "gathering",
    intensity: 0.68,
    vitality: { breath: 0.78, clarity: 0.62, agency: 0.6, grounding: 0.58 },
    note: "Attention is gathering around one shared tone.",
  },
  clarify: {
    surface: "vision",
    quality: "orienting",
    intensity: 0.72,
    vitality: { breath: 0.68, clarity: 0.84, agency: 0.66, grounding: 0.62 },
    note: "Language is becoming precise enough to carry the movement.",
  },
  ground: {
    surface: "evidence",
    quality: "grounding",
    intensity: 0.78,
    vitality: { breath: 0.66, clarity: 0.76, agency: 0.7, grounding: 0.88 },
    note: "Proof is giving the signal a place to stand.",
  },
  embody: {
    surface: "implementation",
    quality: "embodying",
    intensity: 0.86,
    vitality: { breath: 0.76, clarity: 0.8, agency: 0.88, grounding: 0.78 },
    note: "Insight is returning as visible movement.",
  },
};

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

function round(value: number): number {
  return Math.round(clamp01(value) * 100) / 100;
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function eventVitality(event: LivingSignalEvent): number {
  return average([
    event.vitality.breath,
    event.vitality.clarity,
    event.vitality.agency,
    event.vitality.grounding,
  ]);
}

function dominantQuality(events: LivingSignalEvent[]): SignalQuality {
  return [...events].sort((a, b) => {
    const aSignal = a.intensity * eventVitality(a);
    const bSignal = b.intensity * eventVitality(b);
    return bSignal - aSignal;
  })[0]?.quality ?? "gathering";
}

function labelForm(score: number): string {
  if (score >= 0.78) return "well formed";
  if (score >= 0.58) return "taking shape";
  return "just arriving";
}

function labelPulse(score: number): string {
  if (score >= 0.78) return "alive";
  if (score >= 0.58) return "warming";
  return "quietly moving";
}

function guidanceFor(
  events: LivingSignalEvent[],
  activeTone: SignalQuality,
  formScore: number,
  pulseScore: number,
): { guidance: string; nextMovement: string } {
  const vitality = average(events.map(eventVitality));
  const grounding = average(events.map((event) => event.vitality.grounding));
  const clarity = average(events.map((event) => event.vitality.clarity));
  const surfaces = new Set(events.map((event) => event.surface)).size;
  const latest = events[events.length - 1];

  if (events.length <= 1) {
    return {
      guidance: "The signal is young. Give it a simple form and one true movement.",
      nextMovement: "Name the living question in one sentence.",
    };
  }

  if (latest?.surface === "implementation") {
    return {
      guidance: "The movement has entered form. Let the field receive it and sense what opens.",
      nextMovement: "Place this slice into shared memory.",
    };
  }

  if (latest?.surface === "community") {
    return {
      guidance: "Attention is gathering around one shared movement.",
      nextMovement: "Invite the people already leaning toward this signal.",
    };
  }

  if (pulseScore >= 0.76 && surfaces >= 3) {
    return {
      guidance: "The field has enough shape for one embodied experiment.",
      nextMovement: "Share the smallest experiment with the people already listening.",
    };
  }

  if (activeTone === "grounding" || grounding > 0.74) {
    return {
      guidance: "Evidence is holding the vision. This movement is ready to become shared memory.",
      nextMovement: "Write the proof where future work can find it.",
    };
  }

  if (activeTone === "embodying" || vitality > 0.72) {
    return {
      guidance: "Insight is moving through form. Let the next step stay small, visible, and complete.",
      nextMovement: "Ship one embodied slice and sense what opens.",
    };
  }

  if (clarity < 0.58 || formScore < 0.58) {
    return {
      guidance: "The field is asking for language precise enough to carry the movement.",
      nextMovement: "Clarify the signal into one useful distinction.",
    };
  }

  return {
    guidance: "The rhythm is coherent. Keep listening for the next gentle movement.",
    nextMovement: "Invite one more signal, then resense the field.",
  };
}

export function senseLivingField(events: LivingSignalEvent[]): SensedLivingField {
  const received = events.map((event) => ({
    ...event,
    intensity: clamp01(event.intensity),
    vitality: {
      breath: clamp01(event.vitality.breath),
      clarity: clamp01(event.vitality.clarity),
      agency: clamp01(event.vitality.agency),
      grounding: clamp01(event.vitality.grounding),
    },
  }));

  const avgVitality = average(received.map(eventVitality));
  const avgIntensity = average(received.map((event) => event.intensity));
  const surfaceDiversity = received.length
    ? new Set(received.map((event) => event.surface)).size / Math.min(5, received.length)
    : 0;
  const completeSignals = received.filter((event) => event.note.trim().length > 0).length;
  const formCompleteness = received.length ? completeSignals / received.length : 0;
  const formScore = round(avgVitality * 0.5 + surfaceDiversity * 0.25 + formCompleteness * 0.25);

  const firstHalf = received.slice(0, Math.max(1, Math.ceil(received.length / 2)));
  const secondHalf = received.slice(Math.max(0, Math.floor(received.length / 2)));
  const trajectory = average(secondHalf.map(eventVitality)) - average(firstHalf.map(eventVitality));
  const recencyLift = received.reduce((sum, event, index) => {
    const weight = (index + 1) / Math.max(1, received.length);
    return sum + event.intensity * weight;
  }, 0) / Math.max(1, received.length);
  const contactLift = received.length >= 3 ? 0.08 : received.length >= 2 ? 0.03 : 0;
  const pulseScore = round(
    formScore * 0.28
      + avgIntensity * 0.3
      + recencyLift * 0.22
      + surfaceDiversity * 0.14
      + Math.max(0, trajectory) * 0.9
      + contactLift,
  );

  const activeTone = dominantQuality(received);
  const { guidance, nextMovement } = guidanceFor(received, activeTone, formScore, pulseScore);
  const ribbons = [...new Set(received.map((event) => event.surface))].map((surface) => {
    const surfaceEvents = received.filter((event) => event.surface === surface);
    return {
      id: surface,
      label: surface,
      value: round(average(surfaceEvents.map((event) => event.intensity))),
      hue: SURFACE_HUES[surface],
    };
  });

  return {
    formVitality: {
      score: formScore,
      label: labelForm(formScore),
      detail: "How much shape the signal can hold right now.",
    },
    livingPulse: {
      score: pulseScore,
      label: labelPulse(pulseScore),
      trajectory: Math.round(trajectory * 100) / 100,
      detail: "How much the signal is changing through contact.",
    },
    activeTone,
    guidance,
    nextMovement,
    ribbons,
    recentSignals: received.slice(-5).reverse(),
  };
}

export function receiveMovement(
  events: LivingSignalEvent[],
  movement: Movement,
  receivedAt = new Date().toISOString(),
): LivingSignalEvent[] {
  const template = MOVEMENTS[movement];
  const next: LivingSignalEvent = {
    ...template,
    id: `${movement}-${events.length + 1}`,
    receivedAt,
  };
  return [...events, next];
}

export const INITIAL_LIVING_SIGNALS: LivingSignalEvent[] = [
  {
    id: "thread-returning",
    surface: "vision",
    quality: "gathering",
    intensity: 0.58,
    vitality: { breath: 0.62, clarity: 0.5, agency: 0.52, grounding: 0.46 },
    receivedAt: "2026-04-20T10:00:00.000Z",
    note: "A thread keeps returning with warmth.",
  },
  {
    id: "proof-arriving",
    surface: "evidence",
    quality: "grounding",
    intensity: 0.72,
    vitality: { breath: 0.66, clarity: 0.74, agency: 0.64, grounding: 0.82 },
    receivedAt: "2026-04-20T10:07:00.000Z",
    note: "A proof artifact gives the movement a place to stand.",
  },
  {
    id: "agent-finding-form",
    surface: "agent",
    quality: "embodying",
    intensity: 0.8,
    vitality: { breath: 0.72, clarity: 0.76, agency: 0.82, grounding: 0.7 },
    receivedAt: "2026-04-20T10:18:00.000Z",
    note: "An agent turns the signal into a visible slice.",
  },
];
