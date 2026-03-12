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
type StartState = "idle" | "saving" | "saved" | "error";
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
    scope: `Keep the first version tight: one walkable flow, one visible result, and only the minimum support needed. ${cleanDescription}`,
    slices:
      mode === "single"
        ? "Keep the idea in one plan so people can agree on the first version before splitting it further."
        : "Split the idea into promise, flow, and proof so each plan stays small enough to build and check.",
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
      : `Describe the first user journey, the supporting data it needs, and the boundary for what this first version leaves out. ${cleanDescription}`;
    const successEvidence = "A first-time user can explain the promise, complete the flow, and see what changed or what should happen next.";

    return [
      {
        specId: `${baseId}-dsss-mvp`,
        title: `${props.ideaName}: first release plan`,
        whyItMatters,
        whatItCovers,
        successEvidence,
        summary: `${whyItMatters} ${whatItCovers}`,
        processSummary: "Direction: define the first audience and outcome. Scope: keep the first version to one walkable flow.",
        pseudocodeSummary: "Smaller parts: keep this as one plan until the first user-facing flow and proof path are clear.",
        implementationSummary: `Proof of success: ${successEvidence}`,
        potentialValue: Math.max(1, props.potentialValue),
        estimatedCost: Math.max(1, props.estimatedCost),
      },
    ];
  }

  return [
    {
      specId: `${baseId}-dsss-promise`,
      title: `${props.ideaName}: promise and audience`,
      whyItMatters: `Lock the first audience and promise for ${props.ideaName} so the first version says something concrete.`,
      whatItCovers: `Define who this helps first, what tension it resolves, and what the first visible result should be. ${cleanDescription}`,
      successEvidence: "A new user can tell who this is for, why it matters, and where to start without extra explanation.",
      summary: `Define the first audience, promise, and visible result for ${props.ideaName}.`,
      processSummary: "Direction: audience, promise, and first outcome.",
      pseudocodeSummary: "Scope: keep only the first externally valuable journey and leave out secondary complexity.",
      implementationSummary: "Proof of success: the promise is obvious and actionable.",
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
      successEvidence: "Someone can complete the core journey locally without needing hidden IDs, inside language, or hard-to-find navigation.",
      summary: `Define the main human flow for ${props.ideaName} from entry to outcome.`,
      processSummary: "Scope: capture the smallest complete user journey.",
      pseudocodeSummary: "Smaller parts: entry, action, review, and next-step handoff.",
      implementationSummary: "Proof of success: the end-to-end flow is easy to walk and understand.",
      potentialValue: scaledValue(props.potentialValue, 0.4),
      estimatedCost: scaledValue(props.estimatedCost, 0.45),
    },
    {
      specId: `${baseId}-dsss-evidence`,
      title: `${props.ideaName}: measurement, trust, and follow-up`,
      whyItMatters: `Make progress for ${props.ideaName} credible by showing what changed, what is blocked, and what should happen next.`,
      whatItCovers: "Define the status signals, proof markers, human review points, and follow-up rules that keep the first version trustworthy.",
      successEvidence: "The experience makes value movement, blockers, and next actions visible without extra technical interpretation.",
      summary: `Define measurement, trust, and next-step evidence for ${props.ideaName}.`,
      processSummary: "Direction: prove value and trust, not just activity.",
      pseudocodeSummary: "Smaller parts: proof, review checkpoints, and next-step handoff.",
      implementationSummary: "Proof of success: people can judge whether the idea is moving or stuck.",
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
  const [startState, setStartState] = useState<StartState>("idle");
  const [startBusyKey, setStartBusyKey] = useState("");
  const [startedFromSpecId, setStartedFromSpecId] = useState("");
  const [startMessage, setStartMessage] = useState("");
  const [startedTaskId, setStartedTaskId] = useState("");

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
    setStartState("idle");
    setStartBusyKey("");
    setStartedFromSpecId("");
    setStartMessage("");
    setStartedTaskId("");
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
          ? `${draft.title} is now saved as a plan.`
          : `${draft.title} already existed, so this page linked you to the existing plan.`,
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
        `Plan set ready: ${createdCount} created${existingCount > 0 ? `, ${existingCount} already existed` : ""}.`,
      );
    } catch (error) {
      setCreateState("error");
      setMessage(String(error));
    } finally {
      setBusyKey("");
    }
  }

  async function startWorkFromPlan(draft: SuggestedSpecDraft): Promise<void> {
    setStartState("saving");
    setStartBusyKey(draft.specId);
    setStartedFromSpecId(draft.specId);
    setStartMessage("");
    setStartedTaskId("");

    try {
      const response = await fetch("/api/agent/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_type: "impl",
          direction: `Start the first visible work step for ${ideaName} using this plan: ${draft.title}. Keep it small, clear, and easy for a first-time user to follow.`,
          context: {
            idea_id: ideaId,
            idea_name: ideaName,
            spec_id: draft.specId,
            spec_title: draft.title,
            created_from: "idea_dsss_spec_builder_start_work",
            source_plan_summary: draft.summary,
            source_plan_success: draft.successEvidence,
          },
        }),
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }

      const payload = (await response.json()) as { id?: string };
      const taskId = String(payload.id || "").trim();
      if (!taskId) throw new Error("The work card was created, but the response did not include its id.");

      setStartedTaskId(taskId);
      setStartState("saved");
      setStartMessage("The first work step is ready from this plan.");
    } catch (error) {
      setStartState("error");
      setStartMessage(String(error));
    } finally {
      setStartBusyKey("");
    }
  }

  return (
    <section className="rounded border p-4 space-y-4">
      <div className="space-y-2">
        <h2 className="font-semibold">Turn This Idea Into A Clear Plan</h2>
        <p className="text-sm text-muted-foreground">
          Start with the big idea, then make it easier to act on. This view helps you name the direction, keep the
          scope small, break the work into smaller parts, and say how you will know it worked.
        </p>
        <p className="text-sm text-muted-foreground">
          This creates plan cards only. You can review them first, then start work from the plan you want to use.
        </p>
        {existingSpecIds.length > 0 ? (
          <p className="text-sm text-muted-foreground">
            Plans already linked here: {existingSpecIds.length}. Use this to tighten the first version or fill in the
            missing part.
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
          <p className="font-medium">Smaller parts</p>
          <p className="text-muted-foreground">{guide.slices}</p>
        </div>
        <div className="rounded border p-3">
          <p className="font-medium">Proof of success</p>
          <p className="text-muted-foreground">{guide.success}</p>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant={mode === "single" ? "default" : "outline"} onClick={() => applyMode("single")}>
          One clear plan
        </Button>
        <Button type="button" variant={mode === "set" ? "default" : "outline"} onClick={() => applyMode("set")}>
          Split into smaller plans
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => void createAllSpecs()}
          disabled={createState === "saving" || allSuggestedKnown}
        >
          {createState === "saving" && busyKey === "all" ? "Creating plans..." : "Create all plans"}
        </Button>
      </div>

      <div className="space-y-3">
        {suggestedSpecs.map((draft) => {
          const exists = knownSpecIds.includes(draft.specId);
          return (
            <article key={draft.specId} className="rounded border p-4 space-y-2" title={`Plan ID: ${draft.specId}`}>
              <div className="space-y-1">
                <h3 className="font-medium">{draft.title}</h3>
                <p className="text-sm text-muted-foreground">{draft.whyItMatters}</p>
              </div>
              <p className="text-sm text-muted-foreground">{draft.whatItCovers}</p>
              <p className="text-sm text-muted-foreground">How you will know it worked: {draft.successEvidence}</p>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                {exists ? (
                  <>
                    <Link href={`/specs/${encodeURIComponent(draft.specId)}`} className="underline hover:text-foreground">
                      Open plan
                    </Link>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void startWorkFromPlan(draft)}
                      disabled={startState === "saving"}
                    >
                      {startState === "saving" && startBusyKey === draft.specId ? "Creating work card..." : "Start first work step"}
                    </Button>
                  </>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void createSingleSpec(draft)}
                    disabled={createState === "saving"}
                  >
                    {createState === "saving" && busyKey === draft.specId ? "Creating..." : "Create plan"}
                  </Button>
                )}
                <span className="text-muted-foreground">
                  Expected impact {draft.potentialValue.toFixed(1)} | Work size {draft.estimatedCost.toFixed(1)}
                </span>
              </div>
              {startedFromSpecId === draft.specId && startState === "saved" && startMessage ? (
                <p className="text-sm text-green-700">
                  {startMessage}{" "}
                  {startedTaskId ? (
                    <Link href={`/tasks?task_id=${encodeURIComponent(startedTaskId)}`} className="underline">
                      Open work card
                    </Link>
                  ) : null}
                </p>
              ) : null}
              {startedFromSpecId === draft.specId && startState === "error" && startMessage ? (
                <p className="text-sm text-destructive">Could not create the work card: {startMessage}</p>
              ) : null}
            </article>
          );
        })}
      </div>

      {createState === "saved" && message ? <p className="text-sm text-green-700">{message}</p> : null}
      {createState === "error" && message ? <p className="text-sm text-destructive">Could not create the plan: {message}</p> : null}
    </section>
  );
}
