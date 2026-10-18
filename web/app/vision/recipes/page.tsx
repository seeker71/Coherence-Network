// Transmission recipe public surface - runnable payloads and cross-domain pairings.
import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, ClipboardCheck, RotateCcw, ShieldCheck, Sparkles } from "lucide-react";
import { RecipeComposer } from "./RecipeComposer";

export const metadata: Metadata = {
  title: "Transmission Recipes | The Living Collective",
  description:
    "A practical atlas for extracting recipes from songs, stories, failures, specs, rituals, videos, and embodied practices, then transposing them into useful payloads.",
};

type RecipePayload = {
  title: string;
  source: string;
  lens: string;
  recipe: string;
  transposedInto: string;
  impact: string;
  proof: string;
  boundary: string;
  nextEmbodiment: string;
  image: string;
  steps: string[];
};

type Pairing = {
  source: string;
  destination: string;
  payload: string;
  impact: string;
  card: ComposerCard;
};

type ComposerCard = {
  source: string;
  observed: string;
  observerLens: string;
  recipe: string;
  transposedInto: string;
  payload: string;
  proofMode: string;
  claimBoundary: string;
  nextEmbodiment: string;
};

const recipeCard = [
  "source",
  "observed",
  "observer lens",
  "recipe",
  "transposed into",
  "payload",
  "proof mode",
  "claim boundary",
  "next embodiment",
];

function recipeHref(card: ComposerCard): string {
  const recipe = Buffer.from(JSON.stringify(card), "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
  return `/vision/recipes?recipe=${recipe}#composer`;
}

function payloadCard(payload: RecipePayload): ComposerCard {
  return {
    source: payload.source,
    observed: payload.steps.join("; "),
    observerLens: payload.lens,
    recipe: payload.recipe,
    transposedInto: payload.transposedInto,
    payload: payload.title,
    proofMode: payload.proof,
    claimBoundary: payload.boundary,
    nextEmbodiment: payload.nextEmbodiment,
  };
}

const payloads: RecipePayload[] = [
  {
    title: "The Repair Wake",
    source: "A failed deploy where a hidden dependency was trusted without a witness.",
    lens: "Reliability engineer and grief steward.",
    recipe: "rupture -> witness -> name what died -> repair smallest contract -> change one future habit",
    transposedInto: "engineering incident review and team repair",
    impact:
      "Incident review becomes a repair ceremony with a prevention task, an explicit owner, and a seven-day return.",
    proof:
      "The same rupture does not repeat for 30 days, one contract is repaired, and blame language decreases in the review notes.",
    boundary: "Organizational repair practice, not therapy or clinical trauma work.",
    nextEmbodiment: "Run after the next near-miss, before the story hardens into blame.",
    image: "/visuals/network-knowledge-sharing.png",
    steps: [
      "0-5 min: timeline only",
      "5-10 min: what the system showed",
      "10-15 min: what assumption died",
      "15-25 min: smallest broken contract and owner",
      "25-35 min: prevention task and return witness",
    ],
  },
  {
    title: "Onboarding As Ceremony",
    source: "A dance track whose arc teaches arrival, pulse, invitation, build, release, and return.",
    lens: "Product designer and dancer.",
    recipe: "arrive -> entrain -> choose -> intensify -> release -> integrate",
    transposedInto: "first-run product onboarding",
    impact:
      "A first-time visitor leaves with one recipe they made, instead of a documentation wall they skimmed.",
    proof:
      "The visitor can explain the system in their own words, show the first card, and return to the artifact.",
    boundary: "Design analogy; no measured entrainment claim.",
    nextEmbodiment: "Prototype one seven-minute entry flow around a real visitor question.",
    image: "/visuals/life-song-circle.png",
    steps: [
      "Arrive: what are you tending?",
      "Pulse: choose one source that feels alive",
      "Invitation: name the lens",
      "Build: extract the state-change verbs",
      "Return: commit one next embodiment",
    ],
  },
  {
    title: "Metric Spellbreaker",
    source: "Observer and measurement teachings held as strategy metaphor, with clear claim boundaries.",
    lens: "Strategy steward and claim-boundary keeper.",
    recipe: "possibility field -> metric choice -> behavior collapse -> hidden cost -> counter-metric",
    transposedInto: "KPI design and public impact review",
    impact:
      "A team sees what a metric will reward, hide, punish, and sacrifice before it becomes culture.",
    proof:
      "A review catches one distortion before policy changes, or the team retires a metric whose hidden cost is no longer acceptable.",
    boundary: "Quantum and observer language are metaphor here, not physics proof.",
    nextEmbodiment: "Run before adopting the next growth, reach, impact, or productivity metric.",
    image: "/visuals/09-field-intelligence.png",
    steps: [
      "Primary metric",
      "What it makes visible",
      "What it hides",
      "Who pays if this becomes culture",
      "Counter-metric and kill condition",
    ],
  },
];

const pairings: Pairing[] = [
  {
    source: "Camera language",
    destination: "Public trust architecture",
    payload: "A truth storyboard for evidence pages: wide shot for context, close-up for claim, still frame for proof.",
    impact: "Civic groups and open-source teams can show what happened without overwhelming readers with raw archives.",
    card: {
      source: "camera language in documentary and investigative video",
      observed: "wide shot gives context; close-up carries claim; still frame lets proof rest long enough to inspect",
      observerLens: "video editor + public evidence steward",
      recipe: "establish context -> focus claim -> freeze proof -> return to whole system",
      transposedInto: "public trust architecture for evidence pages",
      payload: "Truth Storyboard",
      proofMode: "readers can name the claim, inspect the evidence, and find the raw source without getting lost",
      claimBoundary: "Story structure clarifies evidence; it does not replace the evidence.",
      nextEmbodiment: "Use on one public proof page before adding another archive dump.",
    },
  },
  {
    source: "Fermentation",
    destination: "Contributor onboarding",
    payload: "Starter-culture incubation: one tiny issue, one named maintainer, one warm handoff, one return after seven days.",
    impact: "New contributors become metabolized by the project instead of dropped into a queue.",
    card: {
      source: "fermentation as a living culture becoming stable through warmth, time, and starter matter",
      observed: "a small viable culture needs food, a vessel, warmth, protection from contamination, and return attention",
      observerLens: "maintainer + fermentation steward",
      recipe: "starter -> vessel -> warmth -> feed -> return -> share culture",
      transposedInto: "contributor onboarding",
      payload: "Starter-Culture Onboarding",
      proofMode: "new contributor makes one merged contribution, knows the next person to ask, and returns within seven days",
      claimBoundary: "Metabolism is a project metaphor; contributors remain sovereign people, not culture material.",
      nextEmbodiment: "Give the next new contributor one tiny issue and one named return witness.",
    },
  },
  {
    source: "Martial arts kata",
    destination: "Deployment rehearsal",
    payload: "A five-move release kata: stance, environment check, dry run, witnessed deploy, recovery posture.",
    impact: "Teams build embodied release memory before the real incident pressure arrives.",
    card: {
      source: "martial arts kata as repeated embodied sequence under pressure",
      observed: "stance first; breath before motion; sequence reduces panic; return posture matters after impact",
      observerLens: "release engineer + embodied practice student",
      recipe: "stance -> scan -> dry move -> witnessed strike -> recovery posture",
      transposedInto: "deployment rehearsal",
      payload: "Release Kata",
      proofMode: "release operator can rehearse the path without prompts and can name rollback posture before deploy",
      claimBoundary: "Embodied rehearsal supports reliability; it does not remove technical validation.",
      nextEmbodiment: "Run before the next production deploy with one witness present.",
    },
  },
  {
    source: "Healing intake",
    destination: "Bug triage",
    payload: "A symptom-to-system intake that asks what changed, what hurts, what still functions, and what support is needed.",
    impact: "Maintainers respond to the whole failure pattern instead of only the loudest symptom.",
    card: {
      source: "healing intake practices that listen for symptoms, history, capacity, and support",
      observed: "the loud symptom is not always the root; what still works matters; support changes the treatment path",
      observerLens: "maintainer + whole-system triage listener",
      recipe: "symptom -> change history -> still-working organs -> support needed -> next smallest care",
      transposedInto: "bug triage",
      payload: "Whole-System Bug Intake",
      proofMode: "triage captures reproduction, blast radius, working surfaces, owner, and smallest next repair",
      claimBoundary: "Care language improves attention; software bugs are not bodies and users are not patients.",
      nextEmbodiment: "Use on the next ambiguous bug before assigning severity.",
    },
  },
  {
    source: "Prayer beads",
    destination: "Backlog tending",
    payload: "A review strand: touch each task once, bless, delete, delegate, defer, or do the next honest action.",
    impact: "Backlogs become circulatory systems again instead of silent storage for avoided decisions.",
    card: {
      source: "prayer beads as repeated tactile attention, one bead at a time",
      observed: "attention stays with one bead; repetition calms decision noise; completion is a full strand, not a heroic push",
      observerLens: "project steward + contemplative task tender",
      recipe: "touch -> bless -> decide -> move one bead -> close the strand",
      transposedInto: "backlog tending",
      payload: "Backlog Bead Strand",
      proofMode: "each reviewed task is deleted, delegated, deferred with date, or moved into one concrete next action",
      claimBoundary: "This is attention design, not religious prescription.",
      nextEmbodiment: "Walk the oldest twenty open tasks with one visible decision per task.",
    },
  },
  {
    source: "Story as recipe",
    destination: "Climate adaptation workshops",
    payload: "A local myth-to-action map: danger, helper, threshold, sacrifice, gift, return with a public commitment.",
    impact: "Residents can move from climate anxiety into place-specific commitments that carry emotional meaning.",
    card: {
      source: "local story arcs where danger, helper, threshold, sacrifice, gift, and return organize courage",
      observed: "people move when the threat has a place, the helper is named, and the return has a gift for the village",
      observerLens: "facilitator + place-based story keeper",
      recipe: "danger -> helper -> threshold -> sacrifice -> gift -> return with vow",
      transposedInto: "climate adaptation workshop",
      payload: "Local Myth-to-Action Map",
      proofMode: "participants leave with one place-specific commitment, one helper, and one public return date",
      claimBoundary: "Story can organize courage; it does not replace climate science, policy, or material resources.",
      nextEmbodiment: "Run with one neighborhood around one visible climate stressor.",
    },
  },
];

function RecipeCard() {
  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-5">
      <div className="flex items-center gap-3">
        <ClipboardCheck className="h-5 w-5 text-amber-300/80" aria-hidden="true" />
        <h2 className="text-xl font-light text-stone-100">The card</h2>
      </div>
      <dl className="mt-5 grid gap-2 sm:grid-cols-3">
        {recipeCard.map((field) => (
          <div key={field} className="rounded-md border border-stone-800/70 bg-stone-950/40 px-3 py-2">
            <dt className="text-xs uppercase tracking-[0.16em] text-stone-500">{field}</dt>
          </div>
        ))}
      </dl>
    </div>
  );
}

function PayloadArticle({ payload }: { payload: RecipePayload }) {
  return (
    <article className="grid overflow-hidden rounded-lg border border-stone-800/50 bg-stone-900/25 md:grid-cols-[0.86fr_1.14fr]">
      <div className="relative min-h-[240px] overflow-hidden">
        <Image src={payload.image} alt="" fill className="object-cover" sizes="(max-width: 768px) 100vw, 40vw" />
        <div className="absolute inset-0 bg-gradient-to-t from-stone-950/85 via-stone-950/15 to-transparent" />
      </div>
      <div className="space-y-5 p-5 md:p-7">
        <div className="space-y-2">
          <h3 className="text-2xl font-extralight text-white">{payload.title}</h3>
          <p className="text-sm leading-relaxed text-stone-400">{payload.source}</p>
        </div>
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <p className="rounded-md border border-stone-800/60 bg-stone-950/30 p-3 text-stone-400">
            <span className="block text-xs uppercase tracking-[0.16em] text-teal-300/70">Lens</span>
            {payload.lens}
          </p>
          <p className="rounded-md border border-stone-800/60 bg-stone-950/30 p-3 text-stone-400">
            <span className="block text-xs uppercase tracking-[0.16em] text-violet-300/70">Recipe</span>
            {payload.recipe}
          </p>
        </div>
        <div className="space-y-2">
          {payload.steps.map((step) => (
            <div key={step} className="flex gap-3 text-sm text-stone-300">
              <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-amber-300/65" aria-hidden="true" />
              <span>{step}</span>
            </div>
          ))}
        </div>
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <p className="leading-relaxed text-stone-400">
            <span className="block text-xs uppercase tracking-[0.16em] text-stone-500">Impact</span>
            {payload.impact}
          </p>
          <p className="leading-relaxed text-stone-400">
            <span className="block text-xs uppercase tracking-[0.16em] text-stone-500">Proof</span>
            {payload.proof}
          </p>
        </div>
        <Link
          href={recipeHref(payloadCard(payload))}
          className="inline-flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 px-4 py-2 text-sm font-medium text-amber-200 transition-colors hover:bg-amber-500/20"
        >
          Open this card
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>
    </article>
  );
}

export default function TransmissionRecipesPage() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-950 to-stone-900 text-stone-100">
      <section className="relative overflow-hidden border-b border-stone-800/40">
        <div className="absolute inset-0">
          <Image
            src="/visuals/practice-storytelling-elder.png"
            alt=""
            fill
            priority
            className="object-cover opacity-35"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-stone-950 via-stone-950/82 to-stone-950/40" />
          <div className="absolute inset-0 bg-gradient-to-t from-stone-950 via-transparent to-stone-950/50" />
        </div>
        <div className="relative mx-auto grid min-h-[72vh] max-w-6xl content-end px-6 pb-14 pt-32 md:pb-20">
          <div className="max-w-3xl space-y-6">
            <p className="text-sm uppercase tracking-[0.3em] text-amber-300/75">Transmission Recipe Atlas</p>
            <h1 className="text-4xl font-extralight tracking-tight text-white md:text-7xl">
              Extract the recipe. Move the medicine.
            </h1>
            <p className="max-w-2xl text-lg font-light leading-relaxed text-stone-300 md:text-xl">
              A song, outage, teaching, camera angle, body practice, spec, or strategy failure can carry
              a state-change pattern. The atlas turns that pattern into a payload someone can run.
            </p>
            <div className="flex flex-wrap gap-3 pt-2">
              <Link
                href="#composer"
                className="inline-flex items-center gap-2 rounded-lg border border-violet-500/25 bg-violet-500/10 px-5 py-3 text-sm font-medium text-violet-200 transition-colors hover:bg-violet-500/20"
              >
                Make a card
                <ClipboardCheck className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link
                href="#payloads"
                className="inline-flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 px-5 py-3 text-sm font-medium text-amber-200 transition-colors hover:bg-amber-500/20"
              >
                Walk the payloads
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
              <Link
                href="/vision/lc-transmission-recipe-atlas"
                className="inline-flex items-center gap-2 rounded-lg border border-stone-700/70 bg-stone-900/45 px-5 py-3 text-sm font-medium text-stone-300 transition-colors hover:border-teal-500/35 hover:text-teal-200"
              >
                Read the concept
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-8 px-6 py-16 md:grid-cols-[0.9fr_1.1fr] md:py-24">
        <div className="space-y-5">
          <p className="text-sm uppercase tracking-[0.24em] text-stone-500">How it walks</p>
          <h2 className="text-3xl font-extralight text-stone-100 md:text-4xl">
            Observation becomes responsibility when the lens is named.
          </h2>
          <p className="text-base leading-relaxed text-stone-400">
            The move is not to claim that every domain is the same. The move is to own the observation,
            state the boundary, and give the destination domain its own proof.
          </p>
        </div>
        <RecipeCard />
      </section>

      <RecipeComposer />

      <section id="payloads" className="border-y border-stone-800/35">
        <div className="mx-auto max-w-6xl space-y-8 px-6 py-16 md:py-24">
          <div className="max-w-3xl space-y-4">
            <p className="text-sm uppercase tracking-[0.24em] text-amber-300/70">Three runnable payloads</p>
            <h2 className="text-3xl font-extralight text-stone-100 md:text-4xl">Small enough to try. Serious enough to matter.</h2>
            <p className="leading-relaxed text-stone-400">
              Each payload names the source, the lens, the transposition, and the proof native to its destination.
            </p>
          </div>
          <div className="space-y-6">
            {payloads.map((payload) => (
              <PayloadArticle key={payload.title} payload={payload} />
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl space-y-8 px-6 py-16 md:py-24">
        <div className="max-w-3xl space-y-4">
          <p className="text-sm uppercase tracking-[0.24em] text-teal-300/70">Novel pairings</p>
          <h2 className="text-3xl font-extralight text-stone-100 md:text-4xl">Unexpected sources can carry public value.</h2>
          <p className="leading-relaxed text-stone-400">
            These are ready to become workshops, product flows, reliability rituals, and community tools.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {pairings.map((pairing) => (
            <article key={`${pairing.source}-${pairing.destination}`} className="rounded-lg border border-stone-800/55 bg-stone-900/20 p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-stone-500">{pairing.source}</p>
                  <h3 className="mt-2 text-lg font-light text-stone-100">{pairing.destination}</h3>
                </div>
                <ShieldCheck className="mt-1 h-5 w-5 shrink-0 text-teal-300/70" aria-hidden="true" />
              </div>
              <p className="mt-4 text-sm leading-relaxed text-stone-400">{pairing.payload}</p>
              <p className="mt-4 border-t border-stone-800/60 pt-4 text-sm leading-relaxed text-stone-500">{pairing.impact}</p>
              <Link
                href={recipeHref(pairing.card)}
                className="mt-5 inline-flex items-center gap-2 rounded-lg border border-teal-500/25 bg-teal-500/10 px-4 py-2 text-sm font-medium text-teal-200 transition-colors hover:bg-teal-500/20"
              >
                Open card
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="border-t border-stone-800/35">
        <div className="mx-auto max-w-3xl space-y-6 px-6 py-16 text-center md:py-20">
          <p className="text-sm uppercase tracking-[0.24em] text-stone-500">Next embodiment</p>
          <h2 className="text-3xl font-extralight text-stone-100">Run one recipe where the stakes are real.</h2>
          <p className="leading-relaxed text-stone-400">
            Pick a live source this week. Name the lens. Build the smallest payload. Let proof belong to the destination,
            not to the metaphor.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-2">
            <Link
              href="/vision/lc-transmission-recipe-atlas"
              className="inline-flex items-center gap-2 rounded-lg border border-teal-500/25 bg-teal-500/10 px-5 py-3 text-sm font-medium text-teal-200 transition-colors hover:bg-teal-500/20"
            >
              Open the atlas story
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Link>
            <Link
              href="/vision"
              className="inline-flex items-center gap-2 rounded-lg border border-stone-700/70 bg-stone-900/45 px-5 py-3 text-sm font-medium text-stone-300 transition-colors hover:border-amber-500/35 hover:text-amber-200"
            >
              Return to the vision
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
