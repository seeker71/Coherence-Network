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
      <h2 className="font-semibold">Update Idea Progress</h2>
      <p className="text-sm text-muted-foreground">
        Save measured progress directly to this idea without leaving the detail page.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Actual value (USD)</span>
          <Input
            type="number"
            min="0"
            step="0.1"
            title="Measured value delivered in US dollars."
            placeholder="e.g. 1200.00"
            value={actualValueInput}
            onChange={(event) => setActualValueInput(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Actual cost (USD)</span>
          <Input
            type="number"
            min="0"
            step="0.1"
            title="Observed spend in US dollars."
            placeholder="e.g. 300.00"
            value={actualCostInput}
            onChange={(event) => setActualCostInput(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Confidence (0 to 1)</span>
          <Input
            type="number"
            min="0"
            max="1"
            step="0.01"
            title="0 means no confidence, 1 means fully confident."
            placeholder="e.g. 0.85"
            value={confidenceInput}
            onChange={(event) => setConfidenceInput(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Manifestation status</span>
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            title="How much of the idea is proven in real use."
            value={manifestationStatus}
            onChange={(event) =>
              setManifestationStatus(event.target.value as "none" | "partial" | "validated")
            }
          >
            <option value="none">Not validated</option>
            <option value="partial">Partially validated</option>
            <option value="validated">Validated</option>
          </select>
        </label>
      </div>
      <p className="text-xs text-muted-foreground">
        Tip: use the same USD assumptions on each update so trend lines stay meaningful.
      </p>
      <div className="flex items-center gap-3">
        <Button onClick={save} disabled={saveState === "saving"}>
          {saveState === "saving" ? "Saving..." : "Save Progress"}
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
