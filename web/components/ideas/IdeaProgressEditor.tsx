"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type IdeaProgressEditorProps = {
  ideaId: string;
  initialActualValue: number;
  initialActualCost: number;
  initialConfidence: number;
  initialManifestationStatus: "none" | "partial" | "validated";
};

type SaveState = "idle" | "saving" | "error" | "saved";

function formatMoneyInput(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0";
  if (value < 0.01) return "0.01";
  return value.toFixed(2);
}

function toNumber(value: string, fallback: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) return fallback;
  return Math.round(parsed * 100) / 100;
}

export default function IdeaProgressEditor({
  ideaId,
  initialActualValue,
  initialActualCost,
  initialConfidence,
  initialManifestationStatus,
}: IdeaProgressEditorProps) {
  const [actualValueInput, setActualValueInput] = useState(formatMoneyInput(initialActualValue));
  const [actualCostInput, setActualCostInput] = useState(formatMoneyInput(initialActualCost));
  const [confidenceInput, setConfidenceInput] = useState(String(initialConfidence));
  const [manifestationStatus, setManifestationStatus] = useState(initialManifestationStatus);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  async function save() {
    setSaveState("saving");
    setErrorMsg("");
    const actualValue = toNumber(actualValueInput, initialActualValue);
    const actualCost = toNumber(actualCostInput, initialActualCost);
    const confidenceRaw = Number(confidenceInput);
    const confidence =
      Number.isFinite(confidenceRaw) && confidenceRaw >= 0 && confidenceRaw <= 1
        ? confidenceRaw
        : initialConfidence;

    try {
      const response = await fetch(`/api/ideas/${encodeURIComponent(ideaId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          actual_value: actualValue,
          actual_cost: actualCost,
          confidence,
          manifestation_status: manifestationStatus,
        }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      const updated = (await response.json()) as {
        actual_value: number;
        actual_cost: number;
        confidence: number;
        manifestation_status: "none" | "partial" | "validated";
      };
      setActualValueInput(formatMoneyInput(updated.actual_value));
      setActualCostInput(formatMoneyInput(updated.actual_cost));
      setConfidenceInput(String(updated.confidence));
      setManifestationStatus(updated.manifestation_status);
      setSaveState("saved");
    } catch (error) {
      setSaveState("error");
      setErrorMsg(String(error));
    }
  }

  return (
    <section className="rounded border p-4 space-y-3">
      <h2 className="font-semibold">Update What You Have Learned</h2>
      <p className="text-sm text-muted-foreground">
        Save what this idea has delivered so far, how much it has cost, and how proven it feels right now.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Value seen so far (USD)</span>
          <Input
            type="number"
            min="0"
            step="0.1"
            title="How much real value this idea has already delivered in US dollars."
            placeholder="e.g. 1200.00"
            value={actualValueInput}
            onChange={(event) => setActualValueInput(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Cost so far (USD)</span>
          <Input
            type="number"
            min="0"
            step="0.1"
            title="How much time, money, or effort has already been spent in US dollars."
            placeholder="e.g. 300.00"
            value={actualCostInput}
            onChange={(event) => setActualCostInput(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">How sure are you? (0 to 1)</span>
          <Input
            type="number"
            min="0"
            max="1"
            step="0.01"
            title="0 means no confidence yet. 1 means you feel fully sure."
            placeholder="e.g. 0.85"
            value={confidenceInput}
            onChange={(event) => setConfidenceInput(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">How proven is this?</span>
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            title="How much of this idea is already proven in real use."
            value={manifestationStatus}
            onChange={(event) =>
              setManifestationStatus(event.target.value as "none" | "partial" | "validated")
            }
          >
            <option value="none">Not proven yet</option>
            <option value="partial">Partly proven</option>
            <option value="validated">Proven in real use</option>
          </select>
        </label>
      </div>
      <p className="text-xs text-muted-foreground">
        Tip: use the same money assumptions each time so changes stay easy to compare.
      </p>
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving..." : "Save Changes"}
        </Button>
        {saveState === "saved" ? (
          <span className="text-sm text-green-700">Saved</span>
        ) : null}
        {saveState === "error" ? (
          <span className="text-sm text-destructive">Save failed: {errorMsg}</span>
        ) : null}
      </div>
    </section>
  );
}
