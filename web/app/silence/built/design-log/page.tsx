import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import { loadPublicWebConfig } from "@/lib/app-config";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "Brahmavihara Living Compound",
  description:
    "A warm Bali retreat compound proposal based on the Brahmavihara sketch, Balinese compound principles, climate intelligence, and organic vitality.",
  openGraph: {
    title: "Brahmavihara Living Compound",
    description:
      "A buildable six-month Bali retreat concept: corner nest clusters, central garden, shared edge rooms, service spine, native compound logic, and modern organic flow.",
    url: `${_WEB_UI}/silence/built/design-log`,
    images: [
      {
        url: "/silence/2026-05-04-brahmavihara/presentation/coherent-native-flow-board.png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Brahmavihara Living Compound",
    description:
      "A buildable Bali retreat compound based on the Brahmavihara sketch.",
    images: [
      "/silence/2026-05-04-brahmavihara/presentation/coherent-native-flow-board.png",
    ],
  },
};

const SOURCE_BASE = "/silence/2026-05-04-brahmavihara";
const PRESENTATION_BOARD = `${SOURCE_BASE}/presentation/coherent-native-flow-board.png`;

const facts = [
  ["Site idea", "living compound"],
  ["Budget target", "USD 250,000"],
  ["Build target", "6 months"],
  ["Sleeping", "corner nests"],
  ["Commons", "4 edge rooms"],
] as const;

const designRules = [
  {
    title: "The natah-like center is the social lung",
    body: "The central ring acts like an open garden court: a breathing pause between sleep, food, work, bathing, service, and ceremony.",
  },
  {
    title: "The corner forms are the nests",
    body: "The four corner shapes become protected private nest clusters. Each can hold paired sleeping rooms or one generous suite under a deep, breathable roof.",
  },
  {
    title: "The dark dots are anchors",
    body: "The heavy marks become lantern piers, shoe-off thresholds, and entry anchors. They give the field weight, rhythm, and night orientation.",
  },
  {
    title: "The edges are common rooms",
    body: "The four edge bands become shared pavilions for meals, meditation, movement, and stillness, each facing the center and filtering out to the garden.",
  },
  {
    title: "The built edge carries service",
    body: "The rectilinear lower edge carries toilets, laundry, kitchen, storage, maintenance access, and staff logic so the organic field stays calm.",
  },
] as const;

const nativePrinciples = [
  [
    "Tri Hita Karana",
    "People, nature, and spirit are held through daily movement, shade, garden, craft, and care rather than surface decoration.",
  ],
  [
    "Natah center",
    "An open central court gives the compound breath, orientation, gathering, and ceremony.",
  ],
  [
    "Bale logic",
    "Separate pavilions carry different roles so the place feels like a living compound, not one large building.",
  ],
  [
    "Layered thresholds",
    "Arrival, shoes, washing, shade, garden, room, and bed each have a clear transition.",
  ],
  [
    "Porous boundary",
    "Walls, planting, screens, and gates filter air and attention instead of sealing the site shut.",
  ],
] as const;

const climateMoves = [
  ["Shade first", "Deep roofs, planted edges, and filtered light reduce heat before mechanical cooling is needed."],
  ["Breathable rooms", "High-low screened openings, ridge vents, and porous woven layers let rooms dry after humid nights."],
  ["Raised dry layer", "Bedrooms, cushions, linens, and electronics sit on timber platforms above splash and surface water."],
  ["Soft wind control", "Planting, shutters, and angled screens soften gusts without closing the rooms into boxes."],
  ["Visible water routes", "Roof edges drain to rain chains, gravel trenches, planted pockets, or overflow swales that can be inspected and cleaned."],
  ["Maintenance rhythm", "Bamboo, thatch, screens, gutters, bedding, and mats are detailed as replaceable parts with places to dry and repair.",
  ],
] as const;

const vitalityMoves = [
  ["Vitality", "The upper axis becomes arrival energy, morning light, movement, and first contact with the central garden."],
  ["Harmony", "The lower axis holds commons, food, repair, and practical life so the symbolic field stays grounded."],
  ["Organic Intelligence", "The cross-axis carries water, air, planting, service access, and the quiet intelligence of maintenance."],
] as const;

const materialLogic = [
  ["Bamboo", "main ribs, rafters, handrails, screens", "light, local, fast, repairable"],
  ["Alang-alang or sirap", "deep roof planes and soft acoustic cover", "cool in heat, quiet in rain"],
  ["Paras / lava stone", "thresholds, wet paths, seats, drain edges", "non-slip, grounded, washable"],
  ["Reclaimed timber", "raised floors, decks, bed platforms", "warm underfoot, patchable"],
  ["Gedeg / woven panels", "screens, privacy, drying zones", "breathable and human"],
  ["Dense planting", "garden pockets, privacy, food, cooling", "part of the architecture"],
] as const;

const budget = [
  ["Ground, drainage, water, biofilter", "$35k"],
  ["Covered loop and central council", "$48k"],
  ["Four edge commons", "$48k"],
  ["Four corner nest clusters", "$78k"],
  ["Wet spine, laundry, storage", "$26k"],
  ["Planting, furniture, contingency", "$15k"],
] as const;

const pathMoments = [
  {
    time: "Arrival",
    body: "You enter through the practical built edge, drop wet shoes under cover, then step from service edge into the planted field.",
  },
  {
    time: "Weather shift",
    body: "The compound adjusts without closing down. People can cook, wash, gather, write, and reach bed while air, water, and shade keep moving through the garden.",
  },
  {
    time: "Morning",
    body: "The corner nests open toward private planting pockets. The edge rooms wake up one by one for tea, movement, meditation, and quiet work.",
  },
  {
    time: "Night",
    body: "The dark node anchors become low lantern points. The plan reads by glow, roof edge, planting, and sound of water.",
  },
] as const;

function Section({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mt-20">
      <p className="text-xs uppercase tracking-[0.22em] text-amber-700 dark:text-amber-300/85">
        {eyebrow}
      </p>
      <h2 className="mt-3 max-w-4xl text-3xl font-light tracking-tight text-stone-950 dark:text-stone-100 sm:text-4xl">
        {title}
      </h2>
      {children}
    </section>
  );
}

function FactStrip() {
  return (
    <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      {facts.map(([label, value]) => (
        <div
          key={label}
          className="border-l border-stone-300/70 bg-white/45 px-4 py-3 dark:border-stone-700 dark:bg-stone-950/20"
        >
          <p className="text-xs uppercase tracking-[0.18em] text-stone-500 dark:text-stone-400">
            {label}
          </p>
          <p className="mt-2 text-lg font-light text-stone-950 dark:text-stone-100">
            {value}
          </p>
        </div>
      ))}
    </div>
  );
}

function MasterPlan() {
  return (
    <figure className="overflow-hidden rounded-lg border border-stone-300/70 bg-[#f6edda] shadow-sm dark:border-stone-700">
      <svg
        viewBox="0 0 1000 760"
        role="img"
        aria-labelledby="master-plan-title master-plan-desc"
        className="h-auto w-full"
      >
        <title id="master-plan-title">Brahmavihara compound masterplan</title>
        <desc id="master-plan-desc">
          A sketch-faithful living compound with a symmetrical central flow
          field, four corner nest clusters, edge pavilions for meals,
          meditation, movement, and stillness, dark node anchors, a service
          spine, and visible climate paths.
        </desc>
        <defs>
          <pattern
            id="fan-hatch"
            width="10"
            height="10"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(35)"
          >
            <line x1="0" y1="0" x2="0" y2="10" stroke="#71624e" />
          </pattern>
        </defs>

        <rect width="1000" height="760" fill="#f6edda" />
        <path
          d="M172 78 L812 64 L850 642 L146 654 Z"
          fill="#fff8e7"
          stroke="#342820"
          strokeWidth="4"
        />

        <g fill="none" stroke="#6f9b95" strokeWidth="12" opacity="0.24">
          <path d="M194 100 C164 252 166 454 188 626" />
          <path d="M804 92 C838 260 834 452 806 620" />
          <path d="M190 624 C342 668 560 670 808 620" />
          <path d="M194 340 C284 306 396 302 500 340 C604 302 716 306 806 340" />
        </g>

        <g fill="#d9bd79" stroke="#342820" strokeWidth="2.4">
          <path d="M172 78 A150 150 0 0 1 322 228 L172 228 Z" />
          <path d="M812 64 A150 150 0 0 0 662 214 L812 214 Z" />
          <path d="M146 654 A158 158 0 0 0 304 496 L304 654 Z" />
          <path d="M850 642 A158 158 0 0 1 692 484 L850 484 Z" />
        </g>
        <g fill="url(#fan-hatch)" opacity="0.5" stroke="#342820" strokeWidth="1.2">
          <path d="M172 78 A150 150 0 0 1 322 228 L172 228 Z" />
          <path d="M812 64 A150 150 0 0 0 662 214 L812 214 Z" />
          <path d="M146 654 A158 158 0 0 0 304 496 L304 654 Z" />
          <path d="M850 642 A158 158 0 0 1 692 484 L850 484 Z" />
        </g>

        <g fill="#f2dfb8" stroke="#342820" strokeWidth="2.4">
          <path d="M360 104 C436 84 558 82 638 104 L620 166 C548 150 452 150 374 170 Z" />
          <path d="M734 236 C790 284 796 392 742 452 L682 424 C716 374 714 306 678 252 Z" />
          <path d="M648 586 C558 618 440 618 350 586 L320 654 C438 690 562 690 680 654 Z" />
          <path d="M266 236 C210 284 204 392 258 452 L318 424 C284 374 286 306 322 252 Z" />
        </g>
        <g fill="#342820" fontSize="18" fontFamily="var(--font-serif), Georgia, serif">
          <text x="500" y="132" textAnchor="middle">meditation</text>
          <text x="736" y="346" textAnchor="middle">meals</text>
          <text x="500" y="644" textAnchor="middle">movement</text>
          <text x="264" y="346" textAnchor="middle">stillness</text>
        </g>

        <g fill="#fff8e7" stroke="#342820" strokeWidth="1.8">
          <rect x="198" y="146" width="76" height="42" rx="9" />
          <rect x="704" y="136" width="76" height="42" rx="9" />
          <rect x="196" y="552" width="78" height="44" rx="9" />
          <rect x="706" y="540" width="78" height="44" rx="9" />
        </g>
        <g fill="#342820" fontSize="15" fontWeight="700">
          <text x="236" y="128" textAnchor="middle">corner nest</text>
          <text x="742" y="118" textAnchor="middle">corner nest</text>
          <text x="236" y="534" textAnchor="middle">corner nest</text>
          <text x="746" y="522" textAnchor="middle">corner nest</text>
        </g>

        <path
          d="M500 112 C646 112 768 214 768 340 C768 466 646 568 500 568 C354 568 232 466 232 340 C232 214 354 112 500 112 Z"
          fill="none"
          stroke="#c7a66d"
          strokeWidth="22"
          opacity="0.55"
        />
        <path
          d="M500 140 C626 140 730 230 730 340 C730 450 626 540 500 540 C374 540 270 450 270 340 C270 230 374 140 500 140 Z"
          fill="none"
          stroke="#332820"
          strokeWidth="2.5"
          strokeDasharray="8 9"
          opacity="0.58"
        />
        <circle cx="500" cy="340" r="88" fill="#fff4dc" stroke="#342820" strokeWidth="3" />
        <circle cx="500" cy="340" r="55" fill="#e8d5ae" stroke="#6b5b46" strokeWidth="2" />
        <circle cx="500" cy="340" r="30" fill="none" stroke="#342820" strokeWidth="2" strokeDasharray="4 5" />
        <circle cx="500" cy="340" r="8" fill="#342820" />
        <text x="500" y="452" textAnchor="middle" fill="#342820" fontSize="21" fontFamily="var(--font-serif), Georgia, serif">
          council garden
        </text>

        <g fill="none" stroke="#342820" strokeWidth="2" opacity="0.5">
          <path d="M500 132 L500 252" />
          <path d="M500 428 L500 626" />
          <path d="M264 340 L412 340" />
          <path d="M588 340 L736 340" />
          <path d="M236 166 L438 278" />
          <path d="M742 156 L562 278" />
          <path d="M746 562 L562 402" />
          <path d="M236 574 L438 402" />
        </g>

        <g fill="none" stroke="#342820" strokeWidth="2" opacity="0.38">
          <path d="M324 164 C388 248 430 292 500 340 C570 292 612 248 676 164" />
          <path d="M676 164 C626 258 610 302 748 340 C610 378 626 422 676 516" />
          <path d="M676 516 C612 432 570 388 500 340 C430 388 388 432 324 516" />
          <path d="M324 516 C374 422 390 378 252 340 C390 302 374 258 324 164" />
        </g>
        <g fill="#342820">
          <circle cx="500" cy="150" r="9" />
          <circle cx="736" cy="340" r="9" />
          <circle cx="500" cy="626" r="9" />
          <circle cx="264" cy="340" r="9" />
          <circle cx="236" cy="166" r="8" />
          <circle cx="742" cy="156" r="8" />
          <circle cx="746" cy="562" r="8" />
          <circle cx="236" cy="574" r="8" />
        </g>

        <g fill="#ebdabc" stroke="#342820" strokeWidth="2">
          <path d="M872 238 L946 236 L946 526 L862 540 Z" />
          {["WC", "WC", "laundry", "store"].map((label, index) => (
            <g key={`${label}-${index}`}>
              <rect x="882" y={266 + index * 52} width="48" height="32" rx="4" />
              <text x="906" y={286 + index * 52} textAnchor="middle" fill="#342820" fontSize="12">
                {label}
              </text>
            </g>
          ))}
          <text x="906" y="558" textAnchor="middle" fill="#342820" fontSize="14" fontFamily="var(--font-serif), Georgia, serif">
            service
          </text>
        </g>

        <g fill="none" stroke="#5d8c86" strokeWidth="5" opacity="0.7">
          <path d="M222 176 C306 238 382 278 446 318" />
          <path d="M778 176 C694 238 618 278 554 318" />
          <path d="M222 504 C306 442 382 402 446 362" />
          <path d="M778 504 C694 442 618 402 554 362" />
        </g>

        <g fill="#342820" fontFamily="var(--font-serif), Georgia, serif">
          <text x="452" y="46" fontSize="30">Vitality</text>
          <text x="430" y="736" fontSize="30">Harmony</text>
          <text transform="translate(64 462) rotate(-90)" fontSize="28">
            Organic Intelligence
          </text>
        </g>
      </svg>
      <figcaption className="border-t border-stone-300/70 bg-white/65 px-4 py-3 text-xs leading-relaxed text-stone-700 dark:border-stone-700 dark:bg-stone-950/35 dark:text-stone-300">
        Diagrammatic key: the corner forms become private nest clusters; the
        four edges become common rooms for meditation, meals, movement, and
        stillness; the dark nodes hold thresholds; the center stays open.
      </figcaption>
    </figure>
  );
}

function PresentationBoard() {
  return (
    <figure className="mt-8 overflow-hidden rounded-lg border border-stone-300/70 bg-white/65 shadow-sm dark:border-stone-700 dark:bg-stone-950/30">
      <Image
        src={PRESENTATION_BOARD}
        alt="Architectural presentation board for the Brahmavihara living compound, showing a sketch-faithful top-down plan, bird's-eye roof field, Balinese threshold, edge common rooms, corner nest, and climate construction details."
        width={1680}
        height={960}
        className="h-auto w-full"
        sizes="100vw"
        priority
      />
      <figcaption className="border-t border-stone-300/70 px-4 py-3 text-sm leading-relaxed text-stone-700 dark:border-stone-700 dark:text-stone-300">
        Coherent design direction: the original star/delta field becomes a
        warm Balinese-inspired compound, with private corner nests, common edge
        rooms for meals, meditation, movement, and stillness, a central council
        court, a practical service edge, and modern organic flow.
      </figcaption>
    </figure>
  );
}

function ClimateLoopSection() {
  return (
    <figure className="overflow-hidden rounded-lg border border-stone-300/70 bg-[#f6edda] shadow-sm dark:border-stone-700">
      <svg
        viewBox="0 0 980 430"
        role="img"
        aria-labelledby="climate-loop-title climate-loop-desc"
        className="h-auto w-full"
      >
        <title id="climate-loop-title">Climate intelligent living loop section</title>
        <desc id="climate-loop-desc">
          Section through two roof bays showing shade, ventilation, raised dry
          rooms, washable thresholds, covered path, and planted cooling edges.
        </desc>
        <defs>
          <pattern
            id="roof-lines"
            width="10"
            height="10"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(18)"
          >
            <line x1="0" y1="0" x2="0" y2="10" stroke="#8a7353" />
          </pattern>
        </defs>
        <rect width="980" height="430" fill="#f6edda" />
        <g stroke="#6d95a3" strokeWidth="3" opacity="0.52">
          {[74, 150, 226, 760, 836, 912].map((x) => (
            <path key={x} d={`M${x} 42 L${x - 46} 116`} />
          ))}
        </g>
        <path
          d="M70 206 L278 82 L490 206 L702 82 L910 206"
          fill="none"
          stroke="#342820"
          strokeWidth="26"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M82 204 L278 86 L490 206 L702 86 L898 204 L808 204 C730 164 656 164 578 212 L402 212 C324 164 250 164 172 204 Z"
          fill="url(#roof-lines)"
          stroke="#f6edda"
          strokeWidth="3"
        />
        <path d="M164 204 L164 320 M490 204 L490 320 M816 204 L816 320" stroke="#5b4938" strokeWidth="8" />
        <rect x="146" y="286" width="688" height="42" rx="7" fill="#cda86d" stroke="#342820" strokeWidth="2" />
        <rect x="250" y="236" width="166" height="48" rx="7" fill="#fff7e5" stroke="#342820" strokeWidth="2" />
        <rect x="458" y="236" width="118" height="48" rx="7" fill="#ead8b7" stroke="#342820" strokeWidth="2" />
        <rect x="616" y="236" width="104" height="48" rx="7" fill="#fff7e5" stroke="#342820" strokeWidth="2" />
        <text x="333" y="266" textAnchor="middle" fill="#342820" fontSize="15">sleep</text>
        <text x="517" y="266" textAnchor="middle" fill="#342820" fontSize="15">covered loop</text>
        <text x="668" y="266" textAnchor="middle" fill="#342820" fontSize="15">store</text>
        <path d="M114 214 L114 304 M866 214 L866 304" stroke="#5d8c86" strokeWidth="3" strokeDasharray="5 7" />
        <path d="M92 336 C226 300 336 318 468 342 C592 364 738 350 906 318" fill="none" stroke="#6d95a3" strokeWidth="20" opacity="0.28" />
        <path d="M80 346 C144 316 196 318 244 340" fill="none" stroke="#8fa26a" strokeWidth="15" opacity="0.72" />
        <path d="M742 344 C804 316 858 314 914 330" fill="none" stroke="#8fa26a" strokeWidth="15" opacity="0.72" />
        <circle cx="114" cy="318" r="8" fill="#5d8c86" />
        <circle cx="866" cy="318" r="8" fill="#5d8c86" />
        <text x="490" y="388" textAnchor="middle" fill="#342820" fontSize="21" fontFamily="var(--font-serif), Georgia, serif">
          shade, breeze, dry edges, planting, and repair work as one system
        </text>
      </svg>
      <figcaption className="border-t border-stone-300/70 bg-white/65 px-4 py-3 text-xs leading-relaxed text-stone-700 dark:border-stone-700 dark:bg-stone-950/35 dark:text-stone-300">
        Climate logic: deep roofs create generous shade, raised floors keep
        sleep dry, the loop stays comfortable, air can move through the rooms,
        and water has a visible garden path around the building.
      </figcaption>
    </figure>
  );
}

function DetailModules() {
  const modules = [
    {
      title: "Corner nest shell",
      text: "the corner hatch becomes a private sleeping shell: protected, breathable, raised, and tucked into planting",
      drawing: (
        <g>
          <path d="M40 40 A172 172 0 0 1 212 168 L40 168 Z" fill="#e6c98d" stroke="#332820" strokeWidth="3" />
          {[66, 94, 122, 150].map((x) => (
            <path key={x} d={`M42 168 Q${x} 82 212 40`} fill="none" stroke="#6f604c" strokeWidth="1.4" opacity="0.68" />
          ))}
          <rect x="72" y="118" width="88" height="34" rx="8" fill="#fff8e7" stroke="#332820" strokeWidth="2.4" />
          <circle cx="176" cy="154" r="7" fill="#332820" />
        </g>
      ),
    },
    {
      title: "Node threshold",
      text: "a dark anchor becomes lantern, shoe-off edge, room marker, night orientation, and energetic pulse point",
      drawing: (
        <g>
          <circle cx="126" cy="56" r="16" fill="#332820" />
          <circle cx="126" cy="56" r="5" fill="#f3cd68" />
          <rect x="58" y="116" width="136" height="36" rx="8" fill="#d1ad70" stroke="#332820" strokeWidth="3" />
          <path d="M78 116 C94 88 158 88 174 116" fill="none" stroke="#332820" strokeWidth="3" />
        </g>
      ),
    },
    {
      title: "Edge common bay",
      text: "the side bands become open shared rooms for meals, meditation, movement, and stillness",
      drawing: (
        <g>
          <path d="M42 76 C90 48 162 48 210 76 L196 144 C150 124 102 124 56 144 Z" fill="#d8c49c" stroke="#332820" strokeWidth="3" />
          <path d="M72 110 C104 94 148 94 180 110" fill="none" stroke="#5d8c86" strokeWidth="8" opacity="0.65" />
          <circle cx="92" cy="122" r="10" fill="#fff8e7" stroke="#332820" strokeWidth="2" />
          <circle cx="126" cy="116" r="10" fill="#fff8e7" stroke="#332820" strokeWidth="2" />
          <circle cx="160" cy="122" r="10" fill="#fff8e7" stroke="#332820" strokeWidth="2" />
        </g>
      ),
    },
  ] as const;

  return (
    <div className="mt-7 grid gap-4 lg:grid-cols-3">
      {modules.map((module) => (
        <figure
          key={module.title}
          className="overflow-hidden rounded-lg border border-stone-300/70 bg-[#f6edda] dark:border-stone-700"
        >
          <svg viewBox="0 0 252 190" className="h-auto w-full" role="img">
            <rect width="252" height="190" fill="#f6edda" />
            {module.drawing}
          </svg>
          <figcaption className="border-t border-stone-300/70 bg-white/65 px-4 py-3 dark:border-stone-700 dark:bg-stone-950/35">
            <h3 className="text-lg font-medium text-stone-950 dark:text-stone-100">
              {module.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
              {module.text}
            </p>
          </figcaption>
        </figure>
      ))}
    </div>
  );
}

export default function SilenceBuiltDesignLogPage() {
  return (
    <main id="main-content" className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
      <p className="text-xs uppercase tracking-widest text-muted-foreground">
        <Link
          href="/silence/built"
          className="text-muted-foreground/80 hover:text-amber-500"
        >
          &larr; Built silence
        </Link>{" "}
        · living compound · 2026-05-04
      </p>

      <section className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(360px,0.72fr)] lg:items-start">
        <div>
          <p className="text-sm uppercase tracking-[0.18em] text-amber-700 dark:text-amber-300/85">
            Schematic proposal
          </p>
          <h1 className="mt-4 max-w-4xl text-5xl font-light tracking-tight text-stone-950 dark:text-stone-100 sm:text-6xl">
            Brahmavihara Living Compound
          </h1>
          <p className="mt-7 max-w-3xl text-xl leading-relaxed text-stone-700 dark:text-stone-300">
            The Brahmavihara sketch becomes a living compound: a natah-like
            council garden, private corner nest clusters, edge rooms for meals,
            meditation, movement, and stillness, layered thresholds, and a
            practical service spine woven into modern organic flow.
          </p>
          <FactStrip />
        </div>

        <figure className="overflow-hidden rounded-lg border border-stone-300/70 bg-stone-950 shadow-sm dark:border-stone-700">
          <Image
            src={`${SOURCE_BASE}/8-mandala.jpg`}
            alt="Original Brahmavihara pencil sketch with central ring, dark nodes, pointed delta forms, fan hatch pockets, and the Vitality, Harmony, and Organic Intelligence axes."
            width={4000}
            height={2252}
            className="h-auto w-full"
            sizes="(max-width: 1024px) 100vw, 34vw"
            priority
          />
          <figcaption className="bg-white px-4 py-3 text-xs leading-relaxed text-stone-700 dark:bg-stone-950 dark:text-stone-300">
            Reference sketch: central ring, dark anchors, pointed delta forms,
            fan-hatched pockets, the lower built edge, and the three axes.
          </figcaption>
        </figure>
      </section>

      <Section
        eyebrow="Design direction"
        title="Sketch fidelity first, then place-native architecture."
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          The strongest direction keeps the original star geometry visible: the
          corner forms become private nests, the edge bands become shared
          rooms, the black nodes become thresholds, and the lower-right built
          edge becomes the practical service spine. Balinese compound logic
          gives those marks a livable body.
        </p>
        <PresentationBoard />
      </Section>

      <Section
        eyebrow="One idea"
        title="The original drawing becomes a compound, not a style collage."
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          The diagram below is only the reading key. The architecture should
          feel less like icons on a page and more like a warm field of related
          places: open center, separate rooms, threshold sequence, shaded
          edges, air movement, garden intelligence, and the high-vitality
          rhythm of people living close to craft and climate.
        </p>
        <div className="mt-8">
          <MasterPlan />
        </div>
      </Section>

      <Section
        eyebrow="Native principles"
        title="Balinese compound intelligence gives the sketch a body without costume."
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          The references are principles, not costume. The design borrows the
          compound wisdom of open center, specific pavilions, filtered
          thresholds, porous boundaries, raised floors, and craft materials,
          then lets the Brahmavihara sketch set the exact form, proportion, and
          flow.
        </p>
        <div className="mt-7 grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {nativePrinciples.map(([title, body]) => (
            <div
              key={title}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-lg font-medium text-stone-950 dark:text-stone-100">
                {title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Sketch to architecture"
        title="The marks become repeatable construction modules."
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          Each mark has a job, and each job becomes part of the drawing package:
          corner nest, anchor threshold, edge common bay, covered loop, central
          council court, and service spine.
        </p>
        <DetailModules />
        <div className="mt-7 grid gap-4 lg:grid-cols-5">
          {designRules.map((rule) => (
            <div
              key={rule.title}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-lg font-medium text-stone-950 dark:text-stone-100">
                {rule.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {rule.body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Climate" title="Livable here means shade, breath, dry edges, and repair.">
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          Climate is not the theme; it is the discipline underneath the beauty.
          The rooms need shade before cooling, breeze before fans, drying paths
          before mold, and drainage that can be seen, cleaned, and repaired.
        </p>
        <div className="mt-8">
          <ClimateLoopSection />
        </div>
        <div className="mt-7 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {climateMoves.map(([title, body]) => (
            <div
              key={title}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-lg font-medium text-stone-950 dark:text-stone-100">
                {title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Flow"
        title="Everyday movement is obvious and calm."
      >
        <div className="mt-7 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {pathMoments.map((moment) => (
            <div
              key={moment.time}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-xl font-light text-stone-950 dark:text-stone-100">
                {moment.time}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {moment.body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Vitality"
        title="The three original axes become living currents."
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          High-frequency design here means coherence you can feel: clear
          orientation, warm thresholds, rhythmic nodes, living water, breathable
          rooms, and a plan that helps the body soften instead of forcing it to
          decode a shape.
        </p>
        <div className="mt-7 grid gap-4 md:grid-cols-3">
          {vitalityMoves.map(([title, body]) => (
            <div
              key={title}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <h3 className="text-xl font-light text-stone-950 dark:text-stone-100">
                {title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Material" title="Warm materials, chosen for climate and repair.">
        <div className="mt-7 overflow-hidden rounded-lg border border-stone-300/70 dark:border-stone-700">
          {materialLogic.map(([material, use, reason]) => (
            <div
              key={material}
              className="grid gap-2 border-b border-stone-300/60 bg-white/55 px-4 py-4 last:border-b-0 dark:border-stone-700 dark:bg-stone-950/25 md:grid-cols-[0.7fr_1.3fr_1fr]"
            >
              <p className="font-medium text-stone-950 dark:text-stone-100">
                {material}
              </p>
              <p className="text-sm text-stone-700 dark:text-stone-300">{use}</p>
              <p className="text-sm text-amber-800 dark:text-amber-300">{reason}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Cost"
        title="USD 250,000 is handled through disciplined priorities."
      >
        <p className="mt-5 max-w-4xl text-base leading-relaxed text-stone-700 dark:text-stone-300">
          The budget prioritizes things that make the place survive use:
          ground, shade, roof, covered paths, service rooms, storage, and
          repairable corner nest clusters. Vitality comes from disciplined
          construction, not ornament.
        </p>
        <div className="mt-7 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {budget.map(([label, amount]) => (
            <div
              key={label}
              className="rounded-lg border border-stone-300/70 bg-white/60 p-5 dark:border-stone-700 dark:bg-stone-950/30"
            >
              <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-300">
                {label}
              </p>
              <p className="mt-3 text-2xl font-light text-stone-950 dark:text-stone-100">
                {amount}
              </p>
            </div>
          ))}
        </div>
      </Section>

      <section className="mt-20 rounded-lg border border-amber-500/35 bg-amber-500/10 p-6 text-sm leading-relaxed text-stone-800 dark:text-stone-200">
        <h2 className="text-2xl font-light tracking-tight text-stone-950 dark:text-stone-100">
          Schematic package
        </h2>
        <p className="mt-4 max-w-4xl">
          The presentation package centers on a dimensioned masterplan, one
          corner nest bay at scale, one climate section, one wet-room detail,
          one area schedule, and a Bali builder pricing outline.
        </p>
      </section>
    </main>
  );
}
