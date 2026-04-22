import { describe, expect, it } from "vitest";

import {
  receiveMovement,
  senseLivingField,
  type LivingSignalEvent,
} from "@/lib/living-signal";

const gatheredSignals = (): LivingSignalEvent[] => [
  {
    id: "vision-thread",
    surface: "vision",
    quality: "gathering",
    intensity: 0.62,
    vitality: { breath: 0.58, clarity: 0.54, agency: 0.5, grounding: 0.48 },
    receivedAt: "2026-04-20T10:00:00.000Z",
    note: "A theme is returning with warmth.",
  },
  {
    id: "evidence-arrives",
    surface: "evidence",
    quality: "grounding",
    intensity: 0.74,
    vitality: { breath: 0.64, clarity: 0.7, agency: 0.62, grounding: 0.78 },
    receivedAt: "2026-04-20T10:06:00.000Z",
    note: "Proof is giving the signal a place to stand.",
  },
  {
    id: "agent-movement",
    surface: "agent",
    quality: "embodying",
    intensity: 0.82,
    vitality: { breath: 0.72, clarity: 0.74, agency: 0.8, grounding: 0.68 },
    receivedAt: "2026-04-20T10:14:00.000Z",
    note: "Action is returning as visible movement.",
  },
  {
    id: "community-thread",
    surface: "community",
    quality: "integrating",
    intensity: 0.76,
    vitality: { breath: 0.74, clarity: 0.68, agency: 0.7, grounding: 0.66 },
    receivedAt: "2026-04-20T10:21:00.000Z",
    note: "Separate voices are finding shared language.",
  },
];

describe("living signal layer", () => {
  it("senses living pulse above form when varied signals gather", () => {
    const field = senseLivingField(gatheredSignals());

    expect(field.formVitality.score).toBeGreaterThan(0.55);
    expect(field.livingPulse.score).toBeGreaterThan(field.formVitality.score);
    expect(field.activeTone).toBe("embodying");
    expect(field.guidance).toMatch(/experiment|shared memory|movement/i);
  });

  it("adapts guidance after receiving an embodied movement", () => {
    const before = senseLivingField(gatheredSignals().slice(0, 2));
    const afterEvents = receiveMovement(gatheredSignals().slice(0, 2), "embody");
    const after = senseLivingField(afterEvents);

    expect(afterEvents).toHaveLength(3);
    expect(after.guidance).not.toEqual(before.guidance);
    expect(after.livingPulse.score).toBeGreaterThan(before.livingPulse.score);
    expect(after.nextMovement).toMatch(/share|memory|experiment/i);
  });

  it("keeps sparse signals gentle and actionable", () => {
    const field = senseLivingField([gatheredSignals()[0]]);

    expect(field.formVitality.label).toBe("taking shape");
    expect(field.livingPulse.label).toBe("warming");
    expect(field.guidance).toContain("simple form");
    expect(field.nextMovement).toContain("Name");
  });
});
