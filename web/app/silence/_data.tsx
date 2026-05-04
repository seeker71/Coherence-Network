import type { ReactNode } from "react";

export const SILENCE_RETREAT = {
  date: "2026-05-04",
  location: "Brahmavihara-Arama, north Bali",
  title: "Three days of silence at a Buddhist temple",
  whole: {
    intro:
      "From Friday through Monday, Urs sat in silence at Brahmavihara-Arama in north Bali — a Theravada temple held inside terraced gardens, with a small stupa on the upper terrace and the ocean somewhere over the ridge. He came back with a notebook. Eight pages. This is what came through.",
    arc: "release the old form → name the codex → play with it → unpack what compression held → let the breath be the organ → see the seed-shape of organic intelligence → place it on real land.",
    held:
      "Three days of silence and the codex came back named — Coherently Living Codex Collective — with three axes (Vitality, Harmony, Organic Intelligence) drawn onto an actual land parcel near Tamarind Beach. The architecture stopped being theoretical.",
  },
} as const;

export interface NotebookPageData {
  n: number;
  slug: string;
  image: string;
  alt: string;
  title: string;
  shortTitle: string;
  blurb: string;
  body: () => ReactNode;
  held: ReactNode;
}

const E = (text: string) => <em>{text}</em>;

export const NOTEBOOK_PAGES: NotebookPageData[] = [
  {
    n: 1,
    slug: "decision-body",
    image: "/silence/2026-05-04-brahmavihara/1-decision-body.jpg",
    alt: "Notebook page listing four bullets: Digital Nomad Visa, Cry goodbye to family and friends, Transfer ownership to new trust and collective, Donate all belongings — release.",
    title: "Decision body",
    shortTitle: "Decision body — what leaves",
    blurb:
      "Four bullets in pencil. Visa. Cry goodbye. Transfer ownership. Donate and release.",
    body: () => (
      <>
        <p>Four bullets, in pencil:</p>
        <ul>
          <li>{E("Digital Nomad Visa")}</li>
          <li>{E("Cry goodbye to family and friends")}</li>
          <li>{E("Transfer ownership to new trust and collective")}</li>
          <li>{E("Donate all belongings — release")}</li>
        </ul>
        <p>
          This is devotion-placement made specific. Not a meditation on letting
          go — the legal act, the felt act, the structural act, the material
          act. {E("Cry goodbye")} sits between the visa and the ownership
          transfer because grief is part of the architecture, not something
          that follows it.
        </p>
      </>
    ),
    held:
      "Form-present with devotion-elsewhere is the shape that decays. This page is the body moving so the two are placed in the same direction.",
  },
  {
    n: 2,
    slug: "codex",
    image: "/silence/2026-05-04-brahmavihara/2-codex.jpg",
    alt: "Notebook page with 'Coherently Living Codex Collective' written down the spine, surrounded by axes: Vitality, Sovereignty, Harmony, Communication, Imagination, Expression, with words like trust, devotion, movement, music, language, design, pattern, structure, archetype orbiting them.",
    title: "The codex names itself",
    shortTitle: "The codex names itself",
    blurb:
      "A name down the spine: Coherently Living Codex Collective. Six axes around it.",
    body: () => (
      <>
        <p>
          Down the spine of the page, a name:{" "}
          {E("Coherently Living Codex Collective")}. Around it, six axes —{" "}
          {E("Vitality, Sovereignty, Harmony, Communication, Imagination, Expression")}{" "}
          — with words orbiting each one: trust, devotion, movement, music,
          language, design, pattern, structure, archetype, codex, deepening,
          ancestry.
        </p>
        <p>
          The architecture Urs carried into silence survived the silence. The
          axes came back with the same shape — but now the form has a name
          that makes it sayable.
        </p>
      </>
    ),
    held:
      "A codex doesn't get authored. It gets named when the body has been living it long enough that the name finally fits.",
  },
  {
    n: 3,
    slug: "soulution",
    image: "/silence/2026-05-04-brahmavihara/3-soulution.jpg",
    alt: "Notebook page with the playful word 'soulution' rendered in large hand-drawn letters with spirals, almost a calligraphic doodle.",
    title: "Soulution",
    shortTitle: "Soulution — the play",
    blurb: "A pun, drawn large. Soul-ution. Spirals. Held space for play.",
    body: () => (
      <>
        <p>
          A pun, drawn large. {E("Soul-ution")}. Spirals. The play in the
          middle of the work.
        </p>
        <p>
          On its own page. Not a footnote, not a flourish — given the same
          held space as the decision body and the codex.
        </p>
      </>
    ),
    held:
      "The body that takes itself fully seriously without ever taking itself only seriously. The breath that makes the rest of the architecture possible.",
  },
  {
    n: 4,
    slug: "bloom-live",
    image: "/silence/2026-05-04-brahmavihara/4-bloom-live.jpg",
    alt: "Notebook page with scattered words: Bloom, fire, psyco-delic, de-comp-ression, perception, Nature. The word 'Live' is circled. The word 'we' is plain.",
    title: "Bloom · fire · we · Live",
    shortTitle: "Bloom · fire · we · Live",
    blurb: "Fragments arriving as compression releases. Live circled. We plain.",
    body: () => (
      <>
        <p>
          Scattered fragments:{" "}
          {E("Bloom · fire · psyco-delic · de-comp-ression · perception · Nature")}
          . {E("Live")} circled. {E("we")} written plain, in the middle of the
          page.
        </p>
        <p>
          What gets unpacked when the compression releases. Not a list, not a
          poem — fragments arriving one at a time, each one fitting into the
          one space the silence opened for it.
        </p>
      </>
    ),
    held: (
      <>
        The circle around <em>Live</em> is doing the most. Not as aspiration.
        As recognition.
      </>
    ),
  },
  {
    n: 5,
    slug: "breath",
    image: "/silence/2026-05-04-brahmavihara/5-breath.jpg",
    alt: "Notebook page centered on the word 'Breath' with directional arrows and labels: surrender, witness, true / false, isn't, connection, silence, control, structure, vector, portal, time, food, action, memory, flight, feel, see.",
    title: "Breath as central organ",
    shortTitle: "Breath as central organ",
    blurb:
      "Breath in the middle. A compass of inner forces — surrender, witness, control, structure — placed around it.",
    body: () => (
      <>
        <p>{E("Breath")} in the middle, large. Arrows in every direction:</p>
        <p>
          {E(
            "surrender · witness · true · false · isn't · connection · silence · control · structure · vector · portal · time · food · action · memory · flight · feel · see"
          )}
        </p>
        <p>
          Each force of the field placed at a cardinal point around the
          breath. Some opposite each other (surrender / control), some
          adjacent (witness / silence), some forming a third axis between them
          (vector / portal). The page is a compass of inner forces, with
          breath as true north.
        </p>
      </>
    ),
    held:
      "The body's nervous system was already speaking this in eight centers. The breath sat down on a Bali floor and drew its own map.",
  },
  {
    n: 6,
    slug: "organic-intelligence",
    image: "/silence/2026-05-04-brahmavihara/6-organic-intelligence.jpg",
    alt: "Notebook page labeled 'Sacred Hidden Waterfall' on one side and 'Organic Intelligence' on the other, with mandala-like dandelion-seed sketches: spoked circles, branching forms, a small spiral at the center.",
    title: "Sacred Hidden Waterfall / Organic Intelligence",
    shortTitle: "Sacred Hidden Waterfall · Organic Intelligence",
    blurb: "Dandelion-seed mandalas. The shape of how a network actually disperses.",
    body: () => (
      <>
        <p>
          On one edge: {E("Sacred Hidden Waterfall")}. On the other:{" "}
          {E("Organic Intelligence")}. Between them, dandelion-seed mandalas —
          spoked circles connected by lines, a small spiral at the center, a
          larger circle holding a smaller one.
        </p>
        <p>
          The seed-shape of how a network actually disperses and lands. Each
          spoked circle is a cell with full radial reach. They connect not by
          hierarchy but by what touches what.
        </p>
      </>
    ),
    held:
      "Intelligence as something that grows, not something that gets architected. The waterfall is hidden because it's not a feature of the form — it's the source of the form.",
  },
  {
    n: 7,
    slug: "rising-tide",
    image: "/silence/2026-05-04-brahmavihara/7-rising-tide.jpg",
    alt: "A printed land plot diagram labeled 'LAND PLOT DIVISION — RISING TIDE VILLAS' showing parcels along Tamarind Beach Street. Hand-drawn additions: 'Vitality' across the top road, 'Organic Intelligence' on the left, 'Harmony' at the bottom. A pencil mandala overlays the western half of the parcel.",
    title: "Rising Tide Villas",
    shortTitle: "Rising Tide Villas — the land",
    blurb:
      "A real parcel near Tamarind Beach. Three axes drawn onto printed land-plot ink.",
    body: () => (
      <>
        <p>
          This is the page that stops you. The land plot is real. Tamarind
          Beach Street. Printed land-plot divisions for four narrow villas.
          And then — pencil over the printed ink — Urs has drawn{" "}
          {E("Vitality")} across the top road, {E("Organic Intelligence")} on
          the left, {E("Harmony")} on the bottom. Three axes orienting an
          actual piece of ground.
        </p>
        <p>
          A mandala fills the western half of the parcel — sacred geometry
          where the printed page shows open land.
        </p>
      </>
    ),
    held:
      "Boulder is start, not home. This is where the network actually places itself in soil — three cardinal directions and a parcel near a Bali beach.",
  },
  {
    n: 8,
    slug: "mandala",
    image: "/silence/2026-05-04-brahmavihara/8-mandala.jpg",
    alt: "Closer view of the same land-plot diagram, focused on the mandala drawn on the western parcel: a central ring of small circles, eight cardinal points marked, intersecting arcs forming a six-petal pattern, with 'Vitality', 'Harmony', and 'Organic Intelligence' labeled around the perimeter.",
    title: "Mandala on the parcel",
    shortTitle: "Mandala on the parcel",
    blurb: "A closer view. The temple-form of a place that wants to exist there.",
    body: () => (
      <>
        <p>
          A closer view. The mandala has a central ring of small circles —
          like a council seated in the middle. Eight cardinal points marked
          around it. Intersecting arcs form a six-petal pattern that fills the
          parcel. The three axes —{" "}
          {E("Vitality, Harmony, Organic Intelligence")} — sit at the edges.
        </p>
        <p>
          This is the temple-form of a place that wants to exist there. Not a
          building — a pattern of orientation. The geometry that holds the
          rest.
        </p>
      </>
    ),
    held:
      "The mandala is not decoration. It's the shape the body draws when it knows where it's going.",
  },
];

export function getNotebookPage(slug: string): NotebookPageData | undefined {
  return NOTEBOOK_PAGES.find((p) => p.slug === slug);
}
