"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";

type IdeaDsssSpecBuilderProps = {
  ideaId: string;
  ideaName: string;
  description: string;
  potentialValue: number;
  estimatedCost: number;
  openQuestions: string[];
  existingSpecIds: string[];
};

type DsssMode = "single" | "set";
type CreateState = "idle" | "saving" | "saved" | "error";
type SuggestedSpecDraft = {
  specId: string;
  title: string;
  whyItMatters: string;
  whatItCovers: string;
  successEvidence: string;
  summary: string;
  processSummary: string;
  pseudocodeSummary: string;
  implementationSummary: string;
  potentialValue: number;
  estimatedCost: number;
};

function normalizeText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

function clipText(value: string, maxLength = 220): string {
  const normalized = normalizeText(value);
  if (normalized.length <= maxLength) return normalized;
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function slugify(value: string): string {
  const slug = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "idea";
}

function scaledValue(value: number, fraction: number): number {
  return Number((Math.max(0, value) * fraction).toFixed(1));
}

function primaryQuestion(openQuestions: string[]): string {
  return clipText(openQuestions.find((item) => normalizeText(item).length > 0) || "", 180);
}

function buildDsssGuide(
  ideaName: string,
  description: string,
  openQuestions: string[],
  mode: DsssMode,
): { direction: string; scope: string; slices: string; success: string } {
  const cleanDescription =
    clipText(description, 200) || `${ideaName} needs a clear first public outcome and a way to explain it simply.`;
  const question = primaryQuestion(openQuestions);

  return {
    direction: `Clarify the first real-world outcome ${ideaName} should create and the person it helps first.`,
    scope: `Keep the MVP tight: one walkable flow, one visible result, and only the minimum support needed. ${cleanDescription}`,
    slices:
      mode === "single"
        ? "Keep the idea in one spec so the team can align on the MVP before splitting further."
        : "Split the idea into promise, flow, and proof so each spec stays small enough to build and validate.",
    success: question
      ? `A human can understand the value, walk the flow, and answer this open question next: ${question}`
      : "A human can understand the value, walk the flow, and see what proof confirms the idea is working.",
  };
}

function buildSuggestedSpecs(props: IdeaDsssSpecBuilderProps, mode: DsssMode): SuggestedSpecDraft[] {
  const cleanDescription =
    clipText(props.description, 220) || `${props.ideaName} needs a clear first release shape that people can understand quickly.`;
  const question = primaryQuestion(props.openQuestions);
  const baseId = slugify(props.ideaId || props.ideaName);

  if (mode === "single") {
    const whyItMatters = `Capture the smallest version of ${props.ideaName} that an external person can understand, try, and judge.`;
    const whatItCovers = question
      ? `Describe the first user journey, the data it needs, and how this open question should be resolved: ${question}`
      : `Describe the first user journey, the supporting data it needs, and the boundary for what this MVP leaves out. ${cleanDescription}`;
    const successEvidence = "A first-time user can explain the promise, complete the flow, and see what changed or what should happen next.";

    return [
      {
        specId: `${baseId}-dsss-mvp`,
        title: `${props.ideaName}: MVP direction, scope, and success`,
        whyItMatters,
        whatItCovers,
        successEvidence,
        summary: `${whyItMatters} ${whatItCovers}`,
        processSummary: `DSSS direction: define the first audience and outcome. DSSS scope: keep the MVP to one walkable flow.`,
        pseudocodeSummary: `DSSS slices: hold this as one spec until the first user-facing flow and evidence path are unambiguous.`,
        implementationSummary: `DSSS success: ${successEvidence}`,
        potentialValue: Math.max(1, props.potentialValue),
        estimatedCost: Math.max(1, props.estimatedCost),
      },
    ];
  }

  return [
    {
      specId: `${baseId}-dsss-promise`,
      title: `${props.ideaName}: MVP promise and audience`,
      whyItMatters: `Lock the first audience and promise for ${props.ideaName} so the MVP says something concrete.`,
      whatItCovers: `Define who this helps first, what tension it resolves, and what the first visible result should be. ${cleanDescription}`,
      successEvidence: "A new user can tell who this is for, why it matters, and where to start without extra explanation.",
      summary: `Define the first audience, promise, and visible result for ${props.ideaName}.`,
      processSummary: "DSSS direction: audience, promise, and first outcome.",
      pseudocodeSummary: "DSSS scope: keep only the first externally valuable journey and exclude secondary complexity.",
      implementationSummary: "DSSS success: the MVP promise is obvious and actionable.",
      potentialValue: scaledValue(props.potentialValue, 0.35),
      estimatedCost: scaledValue(props.estimatedCost, 0.25),
    },
    {
      specId: `${baseId}-dsss-flow`,
      title: `${props.ideaName}: end-to-end human flow`,
      whyItMatters: `Turn ${props.ideaName} into one walkable flow instead of a loose collection of internal actions.`,
      whatItCovers: question
        ? `Map the creation, update, review, and follow-up loop in plain language. Use this open question as a design constraint: ${question}`
        : "Map the creation, update, review, and follow-up loop in plain language so a new person can actually use it.",
      successEvidence: "Someone can complete the core journey locally without needing internal IDs, operator jargon, or hidden navigation.",
      summary: `Define the main human flow for ${props.ideaName} from entry to outcome.`,
      processSummary: "DSSS scope: capture the smallest complete user journey.",
      pseudocodeSummary: "DSSS slices: entry, action, review, and next-step handoff.",
      implementationSummary: "DSSS success: the end-to-end flow is walkable and understandable.",
      potentialValue: scaledValue(props.potentialValue, 0.4),
      estimatedCost: scaledValue(props.estimatedCost, 0.45),
    },
    {
      specId: `${baseId}-dsss-evidence`,
      title: `${props.ideaName}: measurement, trust, and follow-up`,
      whyItMatters: `Make progress for ${props.ideaName} credible by showing what changed, what is blocked, and what should happen next.`,
      whatItCovers: "Define the status signals, proof markers, human review points, and follow-up rules that keep the MVP trustworthy.",
      successEvidence: "The system makes value movement, blockers, and next actions visible to a human without extra technical interpretation.",
      summary: `Define measurement, trust, and next-step evidence for ${props.ideaName}.`,
      processSummary: "DSSS direction: prove value and trust, not just activity.",
      pseudocodeSummary: "DSSS slices: evidence, review checkpoints, and follow-up handoff.",
      implementationSummary: "DSSS success: humans can judge whether the idea is advancing or stuck.",
      potentialValue: scaledValue(props.potentialValue, 0.25),
      estimatedCost: scaledValue(props.estimatedCost, 0.3),
    },
  ];
}

export default function IdeaDsssSpecBuilder({
  ideaId,
  ideaName,
  description,
  potentialValue,
  estimatedCost,
  openQuestions,
  existingSpecIds,
}: IdeaDsssSpecBuilderProps) {
  const [mode, setMode] = useState<DsssMode>(existingSpecIds.length === 0 ? "set" : "single");
  const [createState, setCreateState] = useState<CreateState>("idle");
  const [busyKey, setBusyKey] = useState("");
  const [message, setMessage] = useState("");
  const [knownSpecIds, setKnownSpecIds] = useState<string[]>(existingSpecIds);

  const guide = useMemo(() => {
    return buildDsssGuide(ideaName, description, openQuestions, mode);
  }, [description, ideaName, mode, openQuestions]);

  const suggestedSpecs = useMemo(() => {
    return buildSuggestedSpecs(
      {
        ideaId,
        ideaName,
        description,
        potentialValue,
        estimatedCost,
        openQuestions,
        existingSpecIds,
      },
      mode,
    );
  }, [description, estimatedCost, existingSpecIds, ideaId, ideaName, mode, openQuestions, potentialValue]);

  const allSuggestedKnown = suggestedSpecs.every((draft) => knownSpecIds.includes(draft.specId));

  function applyMode(nextMode: DsssMode): void {
    setMode(nextMode);
    setCreateState("idle");
    setBusyKey("");
    setMessage("");
  }

  async function createSpecDraft(draft: SuggestedSpecDraft): Promise<"created" | "existing"> {
    const response = await fetch("/api/spec-registry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        spec_id: draft.specId,
        title: draft.title,
        summary: draft.summary,
        idea_id: ideaId,
        potential_value: draft.potentialValue,
        estimated_cost: draft.estimatedCost,
        process_summary: draft.processSummary,
        pseudocode_summary: draft.pseudocodeSummary,
        implementation_summary: draft.implementationSummary,
      }),
    });

    if (response.status === 409) {
      setKnownSpecIds((current) => (current.includes(draft.specId) ? current : [...current, draft.specId]));
      return "existing";
    }

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }

    setKnownSpecIds((current) => (current.includes(draft.specId) ? current : [...current, draft.specId]));
    return "created";
  }

  async function createSingleSpec(draft: SuggestedSpecDraft): Promise<void> {
    setCreateState("saving");
    setBusyKey(draft.specId);
    setMessage("");
    try {
      const result = await createSpecDraft(draft);
      setCreateState("saved");
      setMessage(
        result === "created"
          ? `${draft.title} is now in the spec registry.`
          : `${draft.title} already existed, so the builder linked you to the existing spec.`,
      );
    } catch (error) {
      setCreateState("error");
      setMessage(String(error));
    } finally {
      setBusyKey("");
    }
  }

  async function createAllSpecs(): Promise<void> {
    setCreateState("saving");
    setBusyKey("all");
    setMessage("");
    let createdCount = 0;
    let existingCount = 0;

    try {
      for (const draft of suggestedSpecs) {
        const result = await createSpecDraft(draft);
        if (result === "created") createdCount += 1;
        if (result === "existing") existingCount += 1;
      }

      setCreateState("saved");
      setMessage(
        `DSSS spec set ready: ${createdCount} created${existingCount > 0 ? `, ${existingCount} already existed` : ""}.`,
      );
    } catch (error) {
      setCreateState("error");
      setMessage(String(error));
    } finally {
      setBusyKey("");
    }
  }

  return (
    <section className="rounded border p-4 space-y-4">
      <div className="space-y-2">
        <h2 className="font-semibold">Turn This Idea Into Specs</h2>
        <p className="text-sm text-muted-foreground">
          Use the DSSS framing to move from a broad idea to concrete spec work: set the direction, narrow the scope,
          split the work into slices, and define the success evidence.
        </p>
        {existingSpecIds.length > 0 ? (
          <p className="text-sm text-muted-foreground">
            Already linked specs: {existingSpecIds.length}. Use DSSS to tighten the MVP or add the missing slice.
          </p>
        ) : null}
      </div>

      <section className="grid gap-3 md:grid-cols-2 text-sm">
        <div className="rounded border p-3">
          <p className="font-medium">Direction</p>
          <p className="text-muted-foreground">{guide.direction}</p>
        </div>
        <div className="rounded border p-3">
          <p className="font-medium">Scope</p>
          <p className="text-muted-foreground">{guide.scope}</p>
        </div>
        <div className="rounded border p-3">
          <p className="font-medium">Slices</p>
          <p className="text-muted-foreground">{guide.slices}</p>
        </div>
        <div className="rounded border p-3">
          <p className="font-medium">Success</p>
          <p className="text-muted-foreground">{guide.success}</p>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant={mode === "single" ? "default" : "outline"} onClick={() => applyMode("single")}>
          One spec
        </Button>
        <Button type="button" variant={mode === "set" ? "default" : "outline"} onClick={() => applyMode("set")}>
          Split into spec set
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void createAllSpecs()}
          disabled={createState === "saving" || allSuggestedKnown}
        >
          {createState === "saving" && busyKey === "all" ? "Creating specs..." : "Create all suggested specs"}
        </Button>
      </div>

      <div className="space-y-3">
        {suggestedSpecs.map((draft) => {
          const exists = knownSpecIds.includes(draft.specId);
          return (
            <article key={draft.specId} className="rounded border p-4 space-y-2" title={`Spec ID: ${draft.specId}`}>
              <div className="space-y-1">
                <h3 className="font-medium">{draft.title}</h3>
                <p className="text-sm text-muted-foreground">{draft.whyItMatters}</p>
              </div>
              <p className="text-sm text-muted-foreground">{draft.whatItCovers}</p>
              <p className="text-sm text-muted-foreground">Success evidence: {draft.successEvidence}</p>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {exists ? (
                  <Link href={`/specs/${encodeURIComponent(draft.specId)}`} className="underline hover:text-foreground">
                    Open spec
                  </Link>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void createSingleSpec(draft)}
                    disabled={createState === "saving"}
                  >
                    {createState === "saving" && busyKey === draft.specId ? "Creating..." : "Create spec"}
                  </Button>
                )}
                <span className="text-muted-foreground">
                  Potential value {draft.potentialValue.toFixed(1)} | Estimated cost {draft.estimatedCost.toFixed(1)}
                </span>
              </div>
            </article>
          );
        })}
      </div>

      {createState === "saved" && message ? <p className="text-sm text-green-700">{message}</p> : null}
      {createState === "error" && message ? <p className="text-sm text-destructive">Create failed: {message}</p> : null}
    </section>
  );
}
