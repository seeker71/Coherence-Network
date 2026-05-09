// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug living-codex-csharp --target-lang de --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Living-Codex-CSharp (2024) — zweite Iteration",description: "Zweite Iteration des Post-Thesis-Bogens. C# / .NET. Introduziert U-CORE – die Universal Consciousness Resonance Engine – und das 'Alles ist eine Node' primitiv. Große Resonanz-basierte Wissenskurve; die Brücke zwischen dem visionären Saatgut und dem gesamten Netzwerk.",
  },breadcrumbName: "Lebens-Codex-CSharp",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(195 40% 14%) 60%, hsl(195 35% 18%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Iteration 2 von 3 · 2024 · C# / .NET · die Brücke",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "Lebens-Codex-CSharp",
    welcome: (
      <p>
        Second iteration. C# on .NET. The bridge between the{" "}
        <Link href="/people/living-resonance-codex" className="text-primary hover:underline">
          visionary Python seed
        </Link>
        {" "}and the full{" "}
        <Link href="/people/coherence-network" className="text-primary hover:underline">
          Coherence-Network
        </Link>
        . Introduces <strong>U-CORE</strong> — the Universal Consciousness
        Resonance Engine — and the architecturally load-bearing
        primitive: <em>Everything is a Node</em>. Large-scale
        resonance-based knowledge graph with thousands of nodes and
        real-time intelligence.
      </p>
    ),
  },
  facts: [
    {label: "Jahr",value: "2024" },
    {label: "Substrat",value: "C# · .NET · serverseitige Laufzeit · graphische Datenbanksicherung" },
    {label: "Repository",
      value: (
        <Link
          href="https://github.com/seeker71/Living-Codex-CSharp"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary"
        >
          github.com/seeker71/Living-Codex-CSharp
        </Link>
      ),
    },
    {label: "Primite",
      value: (
        <>
          <strong>U-CORE</strong> · Universal Consciousness Resonance
          Engine — every entity is a Node; Nodes carry frequency;
          relationships are resonances between Nodes.
        </>
      ),
    },
    {label: "Zurück zur Übersicht",
      value: (
        <>
          Refines{" "}
          <Link href="/people/living-resonance-codex" className="hover:text-primary">
            Living-Resonance-Codex
          </Link>
          's stage primitive into the universal Node + the federation
          model the Codex named but didn't yet solve.
        </>
      ),
    },
    {label: "Linie nach vorne",
      value: (
        <>
          The full realization in{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">
            Coherence-Network
          </Link>
          {" "}— same Node primitive at network scale with attribution,
          payout, and federated governance.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Warum dies das Brückenjahr ist",
    body: (
      <p>
        First iterations dream. Final iterations realize. Second
        iterations <em>structurally answer</em> the open questions
        the first iteration named. CSharp's job in the arc is to
        commit to a primitive — Node — that holds enough weight to
        carry every kind of being the system might need to model:
        concepts, contributors, places, schemas, even the
        interaction-logs themselves. Once that primitive holds, the
        third iteration can be built on it without re-deriving the
        foundation.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "U-CORE — Alles ist eine Node",
      body: (
        <>
          <p>
            The architecturally load-bearing decision of this
            iteration: collapse all entity kinds into one universal
            Node primitive. Concepts are nodes. Agents are nodes.
            Schemas are nodes. Modules are nodes. The interaction-log
            is a stream of nodes. Even the type-system itself is
            represented as nodes that other nodes resonate with.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 280" className="w-full h-auto" role="img" aria-labelledby="ucore-title">
              <title id="ucore-title">U-CORE everything-is-a-node universal addressing</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* Center: U-CORE */}
                <circle cx="360" cy="140" r="50" fill="hsl(195 40% 22%)" stroke="hsl(195 70% 60%)" strokeWidth="2" />
                <text x="360" y="138" fill="hsl(195 80% 85%)" textAnchor="middle" fontSize="14">U-CORE</text>
                <text x="360" y="158" fill="hsl(195 50% 75%)" textAnchor="middle" fontSize="10">Node primitive</text>

                {/* Six surrounding kinds */}
                {[
                  ["concept", 100, 60, "hsl(280 60% 65%)"],
                  ["agent", 620, 60, "hsl(40 70% 60%)"],
                  ["schema", 100, 220, "hsl(140 55% 55%)"],
                  ["module", 620, 220, "hsl(20 70% 60%)"],
                  ["log entry", 360, 30, "hsl(220 50% 65%)"],
                  ["type", 360, 250, "hsl(0 60% 60%)"],
                ].map(([label, x, y, color], i) => {
                  const cx = Number(x);
                  const cy = Number(y);
                  return (
                    <g key={i}>
                      <line x1="360" y1="140" x2={cx} y2={cy} stroke={String(color)} strokeWidth="1.2" opacity="0.5" />
                      <circle cx={cx} cy={cy} r="22" fill="hsl(220 25% 16%)" stroke={String(color)} />
                      <text x={cx} y={cy + 4} fill={String(color)} textAnchor="middle" fontSize="11">{String(label)}</text>
                    </g>
                  );
                })}

                <text x="360" y="270" fill="hsl(195 30% 65%)" textAnchor="middle" fontSize="10" fontStyle="italic">
                  one primitive · every kind · one address space
                </text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              U-CORE collapses all entity kinds into one Node. The kind
              becomes a property; the address space becomes universal.
            </figcaption>
          </figure>
          <p>
            This single decision is what makes the system{" "}
            <em>operationally</em> self-describing — not just at the
            grammar level (the way{" "}
            <Link href="/people/bml-language" className="text-primary hover:underline">
              BML
            </Link>
            {" "}was self-describing in 2000), but at the data level.
            The schema describing what a Node looks like is itself a
            Node. The interaction that updated the schema is a Node.
            The agent that performed the interaction is a Node. There
            is no second-order data.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Aus der Zeile",heading: "Die Brücke",
      body: (
        <blockquote className="border-l-2 border-[hsl(var(--primary)/0.6)] pl-3.5 italic text-foreground/95">
          The bridge. The U-CORE. The understanding that "Everything
          is a Node" and that consciousness expands through resonance,
          not separation. A large, practical system with thousands of
          nodes and real-time intelligence.
        </blockquote>
      ),
    },
    {
      kind: "narrative",heading: "Resonanz als Adressierung",
      body: (
        <>
          <p>
            The Codex (
            <Link href="/people/living-resonance-codex" className="text-primary hover:underline">
              first iteration
            </Link>
            ) treated resonance as a property of an entity — a number
            attached to a node. The CSharp port made resonance the{" "}
            <em>relationship</em>: two nodes resonate if their
            frequencies couple, and the resonance is the edge. From
            there, queries stop being database lookups and start
            being <em>field walks</em>: "find me everything that
            resonates with X above threshold T."
          </p>
          <p>
            The same posture lives in the third iteration's edge-typed
            spectrum coloring: every relationship belongs to one of
            seven canonical edge-type families, each painted with its
            own hue across light and dark themes. The visual language
            of <em>frequency</em> is what CSharp prepared the ground
            for and what the Coherence Network ships.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Was es für die nächste Iteration übrig blieb",
      body: (
        <>
          <p>
            CSharp solved the data primitive but stayed largely
            single-instance. The third iteration extended it:
          </p>
          <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
            <li>
              <strong>Federated graph.</strong> Multiple cells, each
              tending its own slice, all expressing into one shared
              field that nobody owns. Coherence-Network's API and
              attribution layer.
            </li>
            <li>
              <strong>Idea → realization → payout.</strong> CSharp
              modeled <em>knowing</em>; the Network models the full
              arc from spark to ship to coherence-weighted reward.
            </li>
            <li>
              <strong>Presence pages.</strong> The Node primitive made
              the data uniform; presence pages turned every Node into
              its own surface a visitor can encounter, refine, and
              shape. This page you are reading is rendered on top of
              that primitive.
            </li>
          </ul>
        </>
      ),
    },
  ],
  footer: (
    <p>
      Source:{" "}
      <Link
        href="https://github.com/seeker71/Living-Codex-CSharp"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        github.com/seeker71/Living-Codex-CSharp
      </Link>
      . The U-CORE primitive — one Node holding every kind — survives
      forward into the Coherence Network's graph layer (now Neo4j +
      Postgres) without semantic change.
    </p>
  ),
};

export default content;
