// Interactive recipe-card composer for the Transmission Recipes page.
"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Clipboard, Link2, RotateCcw, Sparkles, Wand2 } from "lucide-react";

type RecipeField =
  | "source"
  | "observed"
  | "observerLens"
  | "recipe"
  | "transposedInto"
  | "payload"
  | "proofMode"
  | "claimBoundary"
  | "nextEmbodiment";

type ComposerCard = Record<RecipeField, string>;

type Starter = {
  title: string;
  promise: string;
  card: ComposerCard;
};

type Spark = {
  label: string;
  field: RecipeField;
  value: string;
};

const emptyCard: ComposerCard = {
  source: "",
  observed: "",
  observerLens: "",
  recipe: "",
  transposedInto: "",
  payload: "",
  proofMode: "",
  claimBoundary: "",
  nextEmbodiment: "",
};

const storageKey = "coherence.transmissionRecipe.card.v1";

const fields: Array<{ id: RecipeField; label: string; placeholder: string; rows?: number }> = [
  {
    id: "source",
    label: "source",
    placeholder: "a song, outage, teaching, video, spec, body practice, conversation",
  },
  {
    id: "observed",
    label: "observed",
    placeholder: "sequence, rhythm, rupture, gesture, repeated phrase, body state",
    rows: 3,
  },
  {
    id: "observerLens",
    label: "observer lens",
    placeholder: "engineer + dancer, facilitator + witness, strategist + boundary keeper",
  },
  {
    id: "recipe",
    label: "recipe",
    placeholder: "arrive -> notice -> intensify -> release -> integrate",
    rows: 2,
  },
  {
    id: "transposedInto",
    label: "transposed into",
    placeholder: "incident review, onboarding, workshop, governance, healing practice",
  },
  {
    id: "payload",
    label: "payload",
    placeholder: "the artifact someone can actually run",
    rows: 2,
  },
  {
    id: "proofMode",
    label: "proof mode",
    placeholder: "behavior changes, test passes, retention, repeat rupture absent, state shift",
    rows: 2,
  },
  {
    id: "claimBoundary",
    label: "claim boundary",
    placeholder: "what this is not claiming",
    rows: 2,
  },
  {
    id: "nextEmbodiment",
    label: "next embodiment",
    placeholder: "one real place to run it this week",
    rows: 2,
  },
];

const starters: Starter[] = [
  {
    title: "Repair Wake",
    promise: "Turn a failure into one repaired future habit.",
    card: {
      source: "a failed deploy where a hidden dependency was trusted without a witness",
      observed: "alert fatigue, unclear owner, fast patch, repeated surprise, quiet shame afterward",
      observerLens: "reliability engineer + grief steward",
      recipe: "rupture -> witness -> name what died -> repair smallest contract -> change one future habit",
      transposedInto: "engineering incident review",
      payload: "The Repair Wake",
      proofMode: "prevention task completed; repeat incident absent for 30 days; owner explicit",
      claimBoundary: "organizational repair practice, not therapy or clinical trauma work",
      nextEmbodiment: "run after the next near-miss, not only after a severe outage",
    },
  },
  {
    title: "Dance Onboarding",
    promise: "Turn a song arc into a first-run experience.",
    card: {
      source: "an ecstatic dance track with arrival, pulse, invitation, build, release, and return",
      observed: "the body understands the arc before the mind explains the arc",
      observerLens: "product designer + dancer",
      recipe: "arrive -> entrain -> choose -> intensify -> release -> integrate",
      transposedInto: "first-run product onboarding",
      payload: "a seven-minute entry flow from live source to first recipe card",
      proofMode: "first recipe created; user can explain the system; user returns to the artifact",
      claimBoundary: "design analogy; no measured entrainment claim",
      nextEmbodiment: "prototype the flow on one page before making it a product surface",
    },
  },
  {
    title: "Metric Spellbreaker",
    promise: "Turn measurement pressure into a clearer decision.",
    card: {
      source: "measurement and observer teachings held as strategy metaphor",
      observed: "what gets measured becomes visible; what is unmeasured becomes easier to sacrifice",
      observerLens: "strategy steward + claim-boundary keeper",
      recipe: "possibility field -> metric choice -> behavior collapse -> hidden cost -> counter-metric",
      transposedInto: "KPI design",
      payload: "Metric Spellbreaker canvas",
      proofMode: "fewer metric-induced harms; clearer tradeoffs; review catches distortions",
      claimBoundary: "quantum language is metaphor here, not physics proof",
      nextEmbodiment: "run before adopting any growth, reach, impact, or productivity metric",
    },
  },
];

const sparks: Spark[] = [
  {
    label: "Song -> workshop",
    field: "source",
    value: "a song whose build, drop, silence, and return teach how a group changes state",
  },
  {
    label: "Video -> proof page",
    field: "observed",
    value: "wide shot gives context, close-up carries claim, still frame lets proof rest long enough to inspect",
  },
  {
    label: "Practice -> product",
    field: "observerLens",
    value: "embodiment facilitator + product designer",
  },
  {
    label: "Spec -> ceremony",
    field: "recipe",
    value: "intention -> constraints -> smallest test -> witnessed run -> proof note -> next breath",
  },
  {
    label: "Create a real artifact",
    field: "payload",
    value: "a one-page field kit someone can run with a group this week",
  },
  {
    label: "Bound the claim",
    field: "claimBoundary",
    value: "this is a practice analogy; it supports attention and does not replace domain expertise or consent",
  },
];

function formatCard(card: ComposerCard): string {
  return [
    `source: ${card.source}`,
    `observed: ${card.observed}`,
    `observer lens: ${card.observerLens}`,
    `recipe: ${card.recipe}`,
    `transposed into: ${card.transposedInto}`,
    `payload: ${card.payload}`,
    `proof mode: ${card.proofMode}`,
    `claim boundary: ${card.claimBoundary}`,
    `next embodiment: ${card.nextEmbodiment}`,
  ].join("\n");
}

function hasCardContent(card: ComposerCard): boolean {
  return fields.some((field) => card[field.id].trim());
}

function encodeCard(card: ComposerCard): string {
  const json = JSON.stringify(card);
  return btoa(unescape(encodeURIComponent(json)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function decodeCard(value: string | null): ComposerCard | null {
  if (!value) return null;
  try {
    const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const parsed = JSON.parse(decodeURIComponent(escape(atob(padded)))) as Partial<ComposerCard>;
    return fields.reduce<ComposerCard>(
      (acc, field) => ({
        ...acc,
        [field.id]: typeof parsed[field.id] === "string" ? parsed[field.id] : "",
      }),
      { ...emptyCard },
    );
  } catch {
    return null;
  }
}

async function writeClipboard(text: string): Promise<boolean> {
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard API unavailable");
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    const copied = document.execCommand("copy");
    textarea.remove();
    return copied;
  }
}

function completeness(card: ComposerCard): number {
  const filled = fields.filter((field) => card[field.id].trim()).length;
  return Math.round((filled / fields.length) * 100);
}

export function RecipeComposer() {
  const [card, setCard] = useState<ComposerCard>(emptyCard);
  const [copied, setCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [restored, setRestored] = useState<"url" | "local" | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const formatted = useMemo(() => formatCard(card), [card]);
  const completion = completeness(card);
  const hasContent = hasCardContent(card);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sharedCard = decodeCard(params.get("recipe"));
    if (sharedCard) {
      setCard(sharedCard);
      setRestored("url");
      setHydrated(true);
      return;
    }

    const savedCard = decodeCard(window.localStorage.getItem(storageKey));
    if (savedCard) {
      setCard(savedCard);
      setRestored("local");
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (hasContent) {
      window.localStorage.setItem(storageKey, encodeCard(card));
    } else {
      window.localStorage.removeItem(storageKey);
    }
  }, [card, hasContent, hydrated]);

  function updateField(field: RecipeField, value: string) {
    setCard((current) => ({ ...current, [field]: value }));
    setCopied(false);
    setLinkCopied(false);
  }

  function applySpark(spark: Spark) {
    setCard((current) => {
      const existing = current[spark.field].trim();
      return {
        ...current,
        [spark.field]: existing ? `${existing}; ${spark.value}` : spark.value,
      };
    });
    setCopied(false);
    setLinkCopied(false);
    setRestored(null);
  }

  async function copyCard() {
    if (!formatted.trim()) return;
    const copiedToClipboard = await writeClipboard(formatted);
    setCopied(copiedToClipboard);
    setLinkCopied(false);
  }

  async function copyShareLink() {
    if (!hasContent) return;
    const url = new URL(window.location.href);
    url.searchParams.set("recipe", encodeCard(card));
    url.hash = "composer";
    const copiedToClipboard = await writeClipboard(url.toString());
    setLinkCopied(copiedToClipboard);
    setCopied(false);
  }

  function clearCard() {
    setCard(emptyCard);
    setCopied(false);
    setLinkCopied(false);
    setRestored(null);
    window.localStorage.removeItem(storageKey);
    const url = new URL(window.location.href);
    url.searchParams.delete("recipe");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }

  return (
    <section id="composer" className="border-y border-stone-800/35 bg-stone-950/35">
      <div className="mx-auto grid max-w-6xl gap-8 px-6 py-16 md:grid-cols-[0.95fr_1.05fr] md:py-24">
        <div className="space-y-6">
          <div className="space-y-4">
            <p className="text-sm uppercase tracking-[0.24em] text-violet-300/70">Make one now</p>
            <h2 className="text-3xl font-extralight text-stone-100 md:text-4xl">Give the pattern a handle.</h2>
            <p className="leading-relaxed text-stone-400">
              Choose a live source, sign the lens, and leave with a card that can move into the world.
            </p>
          </div>

          <div className="grid gap-3 rounded-lg border border-violet-500/20 bg-violet-500/5 p-4 text-sm text-stone-300">
            <div className="flex items-center gap-2 text-violet-200">
              <Sparkles className="h-4 w-4" aria-hidden="true" />
              <span className="font-medium">Three-minute play path</span>
            </div>
            <ol className="grid gap-2 sm:grid-cols-3">
              <li className="rounded-md border border-stone-800/60 bg-stone-950/35 p-3">
                <span className="block text-xs uppercase tracking-[0.16em] text-stone-500">1. Pick</span>
                Start with a card below.
              </li>
              <li className="rounded-md border border-stone-800/60 bg-stone-950/35 p-3">
                <span className="block text-xs uppercase tracking-[0.16em] text-stone-500">2. Bend</span>
                Change one field to fit your real source.
              </li>
              <li className="rounded-md border border-stone-800/60 bg-stone-950/35 p-3">
                <span className="block text-xs uppercase tracking-[0.16em] text-stone-500">3. Move</span>
                Copy it, share it, or run it this week.
              </li>
            </ol>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            {starters.map((starter) => (
              <button
                key={starter.title}
                type="button"
                onClick={() => {
                  setCard(starter.card);
                  setCopied(false);
                  setLinkCopied(false);
                  setRestored(null);
                }}
                className="flex min-h-[88px] flex-col items-start justify-center gap-2 rounded-lg border border-stone-800/70 bg-stone-900/40 px-3 py-3 text-left text-sm text-stone-300 transition-colors hover:border-violet-500/35 hover:text-violet-200"
              >
                <span className="inline-flex items-center gap-2 font-medium text-stone-100">
                  <Wand2 className="h-4 w-4 text-violet-300/70" aria-hidden="true" />
                  {starter.title}
                </span>
                <span className="text-xs leading-relaxed text-stone-500">{starter.promise}</span>
              </button>
            ))}
          </div>

          <div className="space-y-3 rounded-lg border border-stone-800/60 bg-stone-900/25 p-4">
            <div>
              <h3 className="text-sm font-medium text-stone-200">Spark buttons</h3>
              <p className="mt-1 text-xs leading-relaxed text-stone-500">
                Use these when the blank field feels too open. Each one drops a usable phrase into one part of the card.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {sparks.map((spark) => (
                <button
                  key={`${spark.field}-${spark.label}`}
                  type="button"
                  onClick={() => applySpark(spark)}
                  className="rounded-lg border border-stone-800/70 bg-stone-950/40 px-3 py-2 text-xs text-stone-300 transition-colors hover:border-amber-500/35 hover:text-amber-200"
                >
                  {spark.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-lg border border-stone-800/60 bg-stone-900/25 p-4">
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs uppercase tracking-[0.18em] text-stone-500">Card coherence</span>
              <span className="text-sm text-stone-300">{completion}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-stone-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-400 via-teal-300 to-violet-300 transition-all"
                style={{ width: `${completion}%` }}
              />
            </div>
            <p className="mt-3 text-xs leading-relaxed text-stone-500">
              {restored === "url"
                ? "Opened from a shared link. Edits now save in this browser."
                : restored === "local"
                  ? "Restored from this browser. Share link only moves the card when you copy it."
                  : hasContent
                    ? "Saved in this browser. Share link carries this card text in the URL."
                    : "Drafts save in this browser once a field has content."}
            </p>
          </div>
        </div>

        <div className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {fields.map((field) => (
              <label key={field.id} className={field.rows && field.rows > 2 ? "sm:col-span-2" : ""}>
                <span className="mb-1.5 block text-xs uppercase tracking-[0.16em] text-stone-500">{field.label}</span>
                <textarea
                  value={card[field.id]}
                  onChange={(event) => updateField(field.id, event.target.value)}
                  rows={field.rows ?? 1}
                  placeholder={field.placeholder}
                  className="block min-h-11 w-full resize-y rounded-lg border border-stone-800/70 bg-stone-950/55 px-3 py-2 text-sm leading-relaxed text-stone-200 outline-none transition-colors placeholder:text-stone-700 focus:border-amber-400/45"
                />
              </label>
            ))}
          </div>

          <div className="rounded-lg border border-teal-500/20 bg-teal-500/5 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-lg font-light text-stone-100">Recipe card</h3>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={clearCard}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-stone-800/70 bg-stone-950/40 text-stone-400 transition-colors hover:border-amber-500/35 hover:text-amber-200"
                  aria-label="Clear recipe card"
                >
                  <RotateCcw className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  onClick={copyShareLink}
                  disabled={!hasContent}
                  className="inline-flex h-10 items-center gap-2 rounded-lg border border-violet-500/25 bg-violet-500/10 px-3 text-sm font-medium text-violet-200 transition-colors hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:border-stone-800 disabled:bg-stone-950/40 disabled:text-stone-600"
                >
                  {linkCopied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Link2 className="h-4 w-4" aria-hidden="true" />}
                  {linkCopied ? "Link copied" : "Share link"}
                </button>
                <button
                  type="button"
                  onClick={copyCard}
                  className="inline-flex h-10 items-center gap-2 rounded-lg border border-teal-500/25 bg-teal-500/10 px-3 text-sm font-medium text-teal-200 transition-colors hover:bg-teal-500/20"
                >
                  {copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Clipboard className="h-4 w-4" aria-hidden="true" />}
                  {copied ? "Copied" : "Copy"}
                </button>
              </div>
            </div>
            <pre className="mt-4 max-h-[360px] overflow-auto whitespace-pre-wrap rounded-lg border border-stone-800/70 bg-stone-950/60 p-4 text-xs leading-relaxed text-stone-300">
              {formatted}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
