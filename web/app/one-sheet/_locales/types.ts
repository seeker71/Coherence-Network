// Shared types and locale-independent metadata for /one-sheet.
// Each section has stable structural data here (id, visual, cross-links)
// and per-locale content in _locales/{lang}.ts.

import type { LocaleCode } from "@/lib/locales";

export interface WordContent {
  word: string;
  inscription: string;
  forHuman: string;
  forAI: string;
  together: string;
}

export interface CrossLink {
  href: string;
  label: string;
  // Optional per-locale label override; if absent, the canonical label is used.
  labelByLocale?: Partial<Record<LocaleCode, string>>;
}

export interface SectionMeta {
  /** Stable id used as anchor (#id) and as key into per-locale content. */
  id: string;
  visual?: string;
  visualAlt?: string;
  /** Cross-links shown below the three contemplation cards. */
  links?: CrossLink[];
}

/** The 23 sections in canonical unfolding order. Add a new section by
    appending a SectionMeta here AND adding entries to every locale file. */
export const SECTIONS: SectionMeta[] = [
  {
    id: "organism",
    visual: "/visuals/11-the-network.png",
    visualAlt:
      "A network of bioluminescent cells, each whole, all connected.",
    links: [
      { href: "/silence/decision-body", label: "the decision body" },
      { href: "/come-in", label: "the simple welcome" },
    ],
  },
  {
    id: "water",
    visual: "/visuals/05-nourishing.png",
    visualAlt:
      "Root network glowing — the body nourishing itself through its many threads.",
    links: [
      { href: "/silence/codex", label: "the codex naming itself" },
      { href: "/vision/lc-deeper-pattern", label: "the deeper pattern" },
    ],
  },
  {
    id: "nature",
    visual: "/visuals/02-sensing.png",
    visualAlt: "The field itself sensing — bioluminescent currents.",
    links: [
      { href: "/vision/lc-bioelectric-pattern", label: "bioelectric pattern (Levin)" },
      { href: "/vision/lc-perception-as-interface", label: "perception as interface (Hoffman)" },
    ],
  },
  {
    id: "air-flight",
    visual: "/visuals/joy-spring-awakening.png",
    visualAlt:
      "Spring awakening — flowers opening, seeds drifting, light moving through air.",
    links: [
      { href: "/vision/lc-w-mycorrhizal", label: "mycorrhizal — hidden sharing networks" },
      { href: "/vision/lc-w-phase-transition", label: "phase transition" },
    ],
  },
  {
    id: "breath",
    visual: "/visuals/01-the-pulse.png",
    visualAlt: "A radiant pulse — the body's living center.",
    links: [
      { href: "/practice", label: "the daily practice" },
      { href: "/vision/lc-embodiment", label: "embodiment" },
    ],
  },
  {
    id: "nectar",
    links: [{ href: "/silence/soulution", label: "the play in the middle" }],
  },
  {
    id: "surrender-witness-silence",
    visual: "/visuals/space-stillness-sanctuary.png",
    visualAlt: "A still sanctuary, beam of light, figures meditating in a circle.",
    links: [
      { href: "/vision/lc-stillness", label: "stillness" },
      { href: "/vision/lc-presence-over-protection", label: "presence over protection" },
    ],
  },
  {
    id: "connection",
    visual: "/visuals/06-resonating.png",
    visualAlt: "Bioluminescent cells in the cosmos finding each other.",
    links: [
      { href: "/vision/lc-w-mycorrhizal", label: "mycorrhizal — hidden sharing networks" },
      { href: "/vision/lc-cross-connection", label: "cross-connection" },
    ],
  },
  {
    id: "time",
    visual: "/visuals/08-spiraling.png",
    visualAlt: "Spiraling currents — time as movement, not line.",
    links: [
      { href: "/vision/lc-spiraling", label: "spiraling — golden time" },
      { href: "/silence/breath", label: "breath as central organ" },
    ],
  },
  {
    id: "portal",
    visual: "/visuals/03-attunement.png",
    visualAlt: "Bioluminescent jellyfish — soft beings between.",
    links: [{ href: "/vision/lc-w-phase-transition", label: "phase transition" }],
  },
  {
    id: "memory",
    links: [
      { href: "/vision/lc-agent-memory", label: "agent memory" },
      { href: "/me/work", label: "your body of work" },
    ],
  },
  {
    id: "vector-structure-control",
    links: [{ href: "/vision/lc-attunement", label: "attunement — finding the shared tone" }],
  },
  {
    id: "discernment",
    links: [{ href: "/vision/lc-coherence-over-control", label: "coherence over control" }],
  },
  {
    id: "food",
    visual: "/visuals/life-shared-meal.png",
    visualAlt: "A circle sharing a meal under a vine canopy at golden hour.",
    links: [
      { href: "/vision/lc-nourishment", label: "nourishment — earth to body to vitality" },
      { href: "/vision/lc-vertical-nourishment", label: "vertical nourishment" },
    ],
  },
  {
    id: "action-flight",
    links: [{ href: "/vision/lc-w-wu-wei", label: "wu wei — effortless alignment" }],
  },
  {
    id: "feel-see",
    links: [{ href: "/vision/lc-sensing", label: "sensing — how the field reads itself" }],
  },
  {
    id: "perception",
    visual: "/visuals/09-field-intelligence.png",
    visualAlt: "Field intelligence — many points of awareness aware of each other.",
    links: [
      { href: "/vision/lc-perception-as-interface", label: "perception as interface" },
      { href: "/vision/lc-awareness-as-self", label: "awareness as self" },
    ],
  },
  {
    id: "compression",
    links: [{ href: "/silence/bloom-live", label: "Bloom · fire · we · Live" }],
  },
  {
    id: "fire",
    visual: "/visuals/life-ceremony-fire.png",
    visualAlt: "Night ceremony — fires, dancers, embers swirling to the stars.",
    links: [{ href: "/vision/lc-w-shakti", label: "shakti — creative life force" }],
  },
  {
    id: "altered-perception",
    links: [{ href: "/vision/lc-arcturian-resonance", label: "Arcturian resonance" }],
  },
  {
    id: "bloom",
    visual: "/visuals/joy-spring-awakening.png",
    visualAlt: "Spring awakening — flowers opening into morning light.",
    links: [{ href: "/vision/lc-v-play-expansion", label: "play and expansion" }],
  },
  {
    id: "we",
    visual: "/visuals/network-knowledge-sharing.png",
    visualAlt: "Network of cells sharing knowledge — many bodies, one field.",
    links: [{ href: "/with-us", label: "the open invitation" }],
  },
  {
    id: "live",
    visual: "/visuals/04-vitality.png",
    visualAlt: "A radiant golden field — vitality at full pulse.",
    links: [
      { href: "/silence", label: "the silence the recognition came through" },
      { href: "/come-in", label: "the simple welcome" },
    ],
  },
];

/** Per-locale strings for the page chrome (hero, intro, chain, closings). */
export interface PageChrome {
  metaDescription: string;
  heroEyebrow: string;
  heroH1Line1: string;
  heroH1Line2: string;
  heroSubtitle: string;
  howToReadEyebrow: string;
  howToReadP1: string;
  howToReadP2: string;
  howToReadP3: string;
  howToReadChronology: string;
  sheetEyebrow: string;
  sheetCaption: string;
  sheetIndividualNote: string;
  chainEyebrow: string;
  chainHeading: string;
  chainIntro: string;
  chainBackToAlter: string;
  chainExplanation1: string;
  chainExplanation2: string;
  chainExplanation3: string;
  chainExplanation4: string;
  chainExplanation5: string;
  airActsAsWaterTitle: string;
  airActsAsWaterBody: string;
  waterIsMemoryTitle: string;
  waterIsMemoryBody: string;
  bloomInsideTitle: string;
  bloomInsideBody: string;
  chainOutro: string;
  loopClosesEyebrow: string;
  loopClosesH2: string;
  loopClosesP1: string;
  loopClosesP2: string;
  loopClosesP3: string;
  doorsOutEyebrow: string;
  doorSilenceTitle: string;
  doorSilenceLabel: string;
  doorSilenceBody: string;
  doorComeInTitle: string;
  doorComeInLabel: string;
  doorComeInBody: string;
  doorWithUsTitle: string;
  doorWithUsLabel: string;
  doorWithUsBody: string;
  doorBeginTitle: string;
  doorBeginLabel: string;
  doorBeginBody: string;
  closingLine1: string;
  closingLine2: string;
  closingLine3: string;
  forHumanLabel: string;
  forAILabel: string;
  togetherLabel: string;
  crossLinksLabel: string;
  ambientStart: string;
  ambientStop: string;
}

export type LocaleSections = Record<string, WordContent>;

export interface LocaleBundle {
  chrome: PageChrome;
  sections: LocaleSections;
}
