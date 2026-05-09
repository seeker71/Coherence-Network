// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug mindtouch-wiki-in-a-box --target-lang de --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "MindTouch Wiki-in-a-Box — MediaWiki PHP in eine C# generische Dokumentschicht portiert",description: "Mitbegründer und Senior Architect bei MindTouch (Mar 2005 – Jan 2007). Die Wikipedia/MediaWiki PHP-Codebasis wurde in eine C# generische Dokumentschicht neu geordnet – Wiki-Engine ist nicht mehr schwer codiert, um Enzyklopädie-Seiten zu kodieren, aber das Dokument-Substrat könnte jede Art von strukturiertem kollaborativem Wissen geautorisiert werden. Die Form, die, zwanzig Jahre später, das Vision-Kb des Coherence Network noch verwendet.",
  },breadcrumbName: "MindTouch · Wiki-in-a-Box",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(140 35% 14%) 50%, hsl(40 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Arbeit · MindTouch Inc. · Mar 2005 – Jan 2007 · Mitbegründer, Senior Architect",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "MindTouch — Wiki-in-a-Box",
    welcome: (
      <p>
        Co-Founder and Senior Architect at MindTouch. The
        load-bearing piece of architecture: take the{" "}
        <Link href="https://en.wikipedia.org/wiki/MediaWiki" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          MediaWiki
        </Link>
        {" "}PHP codebase — the engine that runs Wikipedia — and
        re-architect it into a <strong>C# generic document layer</strong>.
        The wiki engine, no longer hard-coded to encyclopedia pages,
        becomes the document substrate any kind of structured
        collaborative knowledge can be authored against. A "wiki in a
        box" any organisation could deploy and shape into their own
        knowledge ecosystem.
      </p>
    ),
  },
  facts: [
    {label: "Er",value: "MindTouch Inc. · März 2005 – Januar 2007 · 1 Jahr 11 Monate · Co-Founder, Senior Architect" },
    {label: "Substrat",value: "C# / .NET (mit Mono für Cross-Platform) · Portierung von PHP — Sprachänderung mit Typ-Safety + LSP-Stil strukturelle Rigour" },
    {label: "Quelle vor",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/MediaWiki" target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            MediaWiki
          </Link>
          {" "}— the PHP engine powering Wikipedia, Wikimedia, and
          thousands of corporate wikis. The full feature surface
          (templates, parser, history, namespaces, permissions) had
          to land in the new substrate.
        </>
      ),
    },
    {label: "Allgemeines",
      value: (
        <>
          What MediaWiki encoded as "Wikipedia article" became, in
          the MindTouch port, an arbitrary <em>document</em>: a typed
          tree of content with versioned history, structured edits,
          and the wiki authoring conventions as one of many possible
          authoring modes.
        </>
      ),
    },
    {label: "Linie nach vorne",
      value: (
        <>
          The "structured-document substrate any community can shape"
          conviction reappears in the{" "}
          <Link href="/vision" className="hover:text-primary">vision-kb</Link>
          's Karpathy LLM Wiki pattern (concept files at{" "}
          <code className="text-foreground/80">docs/vision-kb/concepts/{`{id}`}.md</code>
          {" "}with INDEX hierarchy, cross-refs, and inline visuals)
          and in the{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">Coherence-Network</Link>
          's living relational graph, where every entity is editable
          through a Refine doorway.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Warum ein Hafen und nicht ein aus-scratch rewrite",
    body: (
      <p>
        MediaWiki had earned its complexity. Years of wiki-community
        practice — templates, parser quirks, namespace conventions,
        permission models, history representation — were encoded in
        the PHP. A from-scratch C# wiki would have re-discovered most
        of it in the second year and still missed the subtleties
        wikipedians had quietly stabilised. The port preserved the
        knowledge baked into the PHP while letting the substrate{" "}
        <em>around</em> the engine become typed, modular, and
        composable. C# was the host; MediaWiki's design wisdom was the
        seed.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Von der Wikipedia-Engine bis zur Dokumentenplattform",
      body: (
        <>
          <p>
            Wikipedia is one of MediaWiki's <em>users</em>, not its
            architecture. The engine knows how to render wiki text,
            track edits, manage namespaces, resolve templates, and
            store history; it doesn't care whether the content is
            encyclopedia articles, internal documentation, customer
            knowledge bases, or scientific protocols. The MindTouch
            port made that latent generalisation explicit by porting
            the engine into C# while collapsing the
            "encyclopedia-article" surface into one specialisation of
            a generic <strong>document</strong> primitive.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 340" className="w-full h-auto" role="img" aria-labelledby="mt-arch-title">
              <title id="mt-arch-title">MindTouch C# generic document layer</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* Top: clients */}
                <rect x="60" y="20" width="600" height="44" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(140 60% 60%)" />
                <text x="80" y="42" fill="hsl(140 80% 80%)" fontSize="13">Clients · web UI · API consumers · authoring tools</text>
                <text x="80" y="58" fill="hsl(140 50% 70%)" fontSize="10">enterprise wikis · documentation portals · KB sites · custom verticals</text>

                <line x1="360" y1="64" x2="360" y2="80" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />

                {/* Middle: generic document layer */}
                <rect x="60" y="80" width="600" height="120" rx="10" fill="hsl(140 35% 16%)" stroke="hsl(140 80% 60%)" strokeWidth="2" />
                <text x="80" y="106" fill="hsl(140 90% 85%)" fontSize="14" fontWeight="500">Generic document layer · C# / .NET</text>
                <text x="80" y="124" fill="hsl(140 60% 75%)" fontSize="11">document model — versioned · structured · permissioned · transactional</text>
                <text x="80" y="140" fill="hsl(140 60% 75%)" fontSize="11">parser surface — wiki text · structured nodes · custom DSLs (pluggable)</text>
                <text x="80" y="156" fill="hsl(140 60% 75%)" fontSize="11">history — every change attributed · diffable · revertible · branchable</text>
                <text x="80" y="172" fill="hsl(140 60% 75%)" fontSize="11">templates · namespaces · macros — preserved from MediaWiki</text>
                <text x="80" y="188" fill="hsl(140 60% 75%)" fontSize="11">extension points — plug in domain-specific document kinds without forking</text>

                <line x1="240" y1="200" x2="240" y2="220" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />
                <line x1="480" y1="200" x2="480" y2="220" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />

                {/* Bottom: source PHP / target storage */}
                <rect x="60" y="220" width="280" height="100" rx="10" fill="hsl(220 25% 16%)" stroke="hsl(40 70% 55%)" strokeDasharray="3,3" />
                <text x="80" y="246" fill="hsl(40 90% 80%)" fontSize="13">Source · MediaWiki PHP</text>
                <text x="80" y="264" fill="hsl(40 50% 70%)" fontSize="10">design wisdom: parser quirks, namespaces,</text>
                <text x="80" y="278" fill="hsl(40 50% 70%)" fontSize="10">templates, history model, permissions</text>
                <text x="80" y="296" fill="hsl(40 50% 70%)" fontSize="10">years of wiki-community-stabilised behaviour</text>
                <text x="80" y="310" fill="hsl(40 60% 75%)" fontSize="10" fontStyle="italic">⤷ ported, not re-derived</text>

                <rect x="380" y="220" width="280" height="100" rx="10" fill="hsl(220 25% 16%)" stroke="hsl(195 60% 55%)" />
                <text x="400" y="246" fill="hsl(195 80% 80%)" fontSize="13">Storage · SQL · structured</text>
                <text x="400" y="264" fill="hsl(195 50% 70%)" fontSize="10">page tree · revision graph</text>
                <text x="400" y="278" fill="hsl(195 50% 70%)" fontSize="10">attachment store · search index</text>
                <text x="400" y="296" fill="hsl(195 50% 70%)" fontSize="10">structured metadata · attribute index</text>
                <text x="400" y="310" fill="hsl(195 60% 75%)" fontSize="10" fontStyle="italic">⤷ deployable in a box</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The architectural shape. MediaWiki's design wisdom is the
              source upstream (left); the C# generic document layer is
              the load-bearing middle; storage on the right is the
              "in a box" deployable artifact.
            </figcaption>
          </figure>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Was bedeutet 'in einer Kiste'",heading: "Ein Wiki jeder Organisation kann Gastgeber",
      body: (
        <>
          <p>
            Wikipedia ran on Wikimedia infrastructure. Most other
            wikis in 2005 either ran on shared MediaWiki hosting or
            were artisanal one-off installs. The MindTouch product
            shape: a single deployable artifact — runtime, document
            layer, web UI, admin tools, all in one — that any
            organisation could install on a server they controlled
            and start authoring against. A wiki, in a box.
          </p>
          <p>
            The deeper conviction the product encoded:{" "}
            <em>knowledge sovereignty</em>. An organisation's
            knowledge belongs in their own infrastructure, with their
            own permission models, their own retention policies, their
            own back-ups. The wiki engine generalised becomes the
            substrate any community uses to make its knowing visible
            to itself, on its own terms. That conviction lives now in
            the Coherence Network's "every cell tends its own flame"
            posture — the same shape, twenty years later, expressed in
            a different medium.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Was die Vision voranbringt",
      body: (
        <>
          <p>
            The{" "}
            <Link href="/vision" className="text-primary hover:underline">
              Coherence Network's vision-kb
            </Link>
            {" "}— "Living Collective Knowledge Base" with concept
            files at{" "}
            <code className="text-foreground/80">docs/vision-kb/concepts/{`{id}`}.md</code>
            , INDEX hierarchy, cross-refs (<code className="text-foreground/80">→ lc-xxx, lc-yyy</code>),
            inline visuals (<code className="text-foreground/80">{`![caption](visuals:prompt)`}</code>),
            sync to graph DB — is structurally a wiki. Karpathy's "LLM
            Wiki" pattern named it as a fresh idea in 2024, but the
            shape is exactly what MindTouch's wiki-in-a-box port
            committed to in 2005:
          </p>
          <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
            <li>
              <strong>Structured documents over free-form
              prose.</strong> Each concept file has frontmatter,
              cross-refs, schema. Each MindTouch document had typed
              fields, namespaces, templates.
            </li>
            <li>
              <strong>Versioned, attributed history.</strong> Git
              tracks every concept-file change with commit verbs;
              MindTouch tracked every wiki edit with revision attribution.
              Different storage, same conviction.
            </li>
            <li>
              <strong>Cross-link as first-class structure.</strong>{" "}
              Wiki [[link]] syntax expressed reference; vision-kb
              cross-refs do the same with{" "}
              <code className="text-foreground/80">→ lc-xxx</code>
              {" "}and the network paints them with their edge-type
              spectrum hue.
            </li>
            <li>
              <strong>Sync into a queryable graph.</strong> MindTouch
              indexed structured metadata into a relational store;
              the vision-kb syncs concept content + analogous-to edges
              into Neo4j via{" "}
              <code className="text-foreground/80">scripts/sync_kb_to_db.py</code>
              .
            </li>
          </ul>
          <p>
            The 2005 port and the 2026 KB are the same architectural
            posture in different substrates. Once you've built one
            generic document layer, the conviction stays — it just
            finds new substrates to express itself through.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <p>
      Company:{" "}
      <Link href="https://en.wikipedia.org/wiki/MindTouch" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        MindTouch on Wikipedia
      </Link>
      {" · "}
      Source upstream:{" "}
      <Link href="https://en.wikipedia.org/wiki/MediaWiki" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        MediaWiki
      </Link>
      . Source code is internal to MindTouch; what lives here is the
      architectural shape and the design conviction. Urs is invited
      to refine technical detail through the Refine doorway below.
    </p>
  ),
};

export default content;
