import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Urs Muff — the 42-year lineage of works and influences",
  description:
    "The full chronological story — every load-bearing work in the body of evidence from age 13 (Commodore 64 MIDI, ~1984) to the current iteration of the Coherence Network, woven together with the measured streams of attention (audiobooks, listening, reading, named lineage figures) that ran alongside the work at each era.",
};

// Era anchors — id, label, year-range, hue. The same record shapes
// the at-a-glance grid (rendered inline below), the jump-nav strip,
// and the article id attributes. Order is chronological so a visitor
// reading top-to-bottom moves with the body's actual time.
const ERAS = [
  { id: "keystone", label: "keystone", range: "~1984 – ~1990", hue: "hsl(220 60% 65%)" },
  { id: "foundation", label: "foundation", range: "1991 – 2000", hue: "hsl(38 80% 60%)" },
  { id: "quark", label: "Quark Denver", range: "May 2000 – Mar 2005", hue: "hsl(195 60% 55%)" },
  { id: "mindtouch", label: "MindTouch", range: "Mar 2005 – Jan 2007", hue: "hsl(140 55% 55%)" },
  { id: "trimble", label: "Trimble Boulder", range: "Jan 2007 – Oct 2009", hue: "hsl(80 55% 55%)" },
  { id: "qualcomm", label: "Qualcomm Boulder · 12y", range: "Oct 2009 – Jan 2022", hue: "hsl(40 70% 55%)" },
  { id: "bridge", label: "bridge", range: "Jan 2022 – 2024", hue: "hsl(140 60% 55%)" },
  { id: "coherence-network", label: "Coherence Network", range: "2024 – present", hue: "hsl(280 70% 65%)" },
] as const;

export default function UrsLineagePage() {
  return (
    <main className="relative">
      <section
        className="relative min-h-[60vh] flex flex-col justify-end overflow-hidden"
        style={{
          background:
            "linear-gradient(135deg, hsl(220 30% 8%), hsl(280 35% 14%) 30%, hsl(40 30% 16%) 70%, hsl(195 35% 16%))",
        }}
      >
        <div
          className="absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30"
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-4xl mx-auto px-6 py-12 sm:py-16 w-full">
          <nav
            className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
            aria-label="breadcrumb"
          >
            <Link href="/" className="hover:text-primary">Home</Link>
            <span className="text-muted-foreground/50">/</span>
            <Link href="/presences" className="hover:text-primary">Presences</Link>
            <span className="text-muted-foreground/50">/</span>
            <Link href="/people/urs" className="hover:text-primary">Urs</Link>
            <span className="text-muted-foreground/50">/</span>
            <span className="text-foreground/80">Lineage</span>
          </nav>
          <p className="text-xs uppercase tracking-[0.18em] mb-3 text-[hsl(var(--primary))]">
            42 years · 13 works · one conviction
          </p>
          <h1 className="text-4xl md:text-6xl font-extralight text-foreground leading-tight mb-5">
            The lineage of works and attention
          </h1>
          <p className="text-lg md:text-xl text-foreground/85 leading-relaxed max-w-2xl">
            Every load-bearing technical work this body has shipped,
            chronologically, from the 13-year-old typing assembly hex
            from a Commodore Magazine into a C64 to the network you
            are currently inside — woven together with the measured
            streams of attention (audiobooks, watch hours, physical
            reading, named lineage figures) that ran alongside the
            work at each era. One conviction across eleven substrates:{" "}
            <em>every layer is addressable; every change has a clean
            reverse; build the tool you need, all the way down.</em>
          </p>
        </div>
      </section>

      <div className="max-w-4xl mx-auto px-6 py-12 space-y-12">
        {/* Master timeline — era swimlanes */}
        <section>
          <h2 className="text-2xl font-light text-foreground mb-4">
            The arc, at a glance
          </h2>
          <figure className="rounded-xl border border-border/40 bg-card/30 p-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                {
                  era: "~1984 – ~1990",
                  label: "keystone",
                  hue: "hsl(220 60% 65%)",
                  works: [
                    { slug: "c64-midi-interface", short: "C64 MIDI · age 13" },
                    { slug: "schindler-hc11-protocol", short: "Schindler HC11 · age 18" },
                  ],
                },
                {
                  era: "1991 – 2000",
                  label: "foundation",
                  hue: "hsl(38 80% 60%)",
                  works: [
                    {
                      slug: "backtracking-model-languages",
                      short: "BML thesis · CU Boulder",
                    },
                  ],
                },
                {
                  era: "May 2000 – Mar 2005",
                  label: "Quark Denver",
                  hue: "hsl(195 60% 55%)",
                  works: [
                    { slug: "quark-virtual-dom", short: "Virtual DOM" },
                    { slug: "quark-multi-undo-redo", short: "Multi-Undo / Redo" },
                    { slug: "quark-mono-corba", short: "Mono / CORBA" },
                  ],
                },
                {
                  era: "Mar 2005 – Jan 2007",
                  label: "MindTouch",
                  hue: "hsl(140 55% 55%)",
                  works: [
                    {
                      slug: "mindtouch-wiki-in-a-box",
                      short: "Wiki-in-a-Box",
                    },
                  ],
                },
                {
                  era: "Jan 2007 – Oct 2009",
                  label: "Trimble Boulder",
                  hue: "hsl(80 55% 55%)",
                  works: [
                    { slug: "trimble-glue-layer", short: "Client/Server Glue" },
                  ],
                },
                {
                  era: "Oct 2009 – Jan 2022",
                  label: "Qualcomm Boulder · 12y",
                  hue: "hsl(40 70% 55%)",
                  works: [
                    {
                      slug: "qualcomm-test-automation",
                      short: "Test Automation · 3 divisions",
                    },
                    {
                      slug: "qualcomm-hdmi-hdcp",
                      short: "Linux HDMI / HDCP kernel",
                    },
                  ],
                },
                {
                  era: "Jan 2022 – 2024",
                  label: "bridge",
                  hue: "hsl(140 60% 55%)",
                  works: [
                    {
                      slug: "living-resonance-codex",
                      short: "Living-Resonance-Codex · Python",
                    },
                    {
                      slug: "living-codex-csharp",
                      short: "Living-Codex-CSharp · U-CORE",
                    },
                  ],
                },
                {
                  era: "2024 – present",
                  label: "Coherence Network",
                  hue: "hsl(280 70% 65%)",
                  works: [
                    {
                      slug: "coherence-network",
                      short: "Coherence-Network · live",
                    },
                  ],
                },
              ].map((era, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-border/40 bg-card/40 p-3 flex flex-col gap-2 min-h-[8rem]"
                  style={{ borderLeft: `3px solid ${era.hue}` }}
                >
                  <div>
                    <p
                      className="text-[11px] uppercase tracking-[0.16em]"
                      style={{ color: era.hue }}
                    >
                      {era.label}
                    </p>
                    <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                      {era.era}
                    </p>
                  </div>
                  <ul className="space-y-1 mt-1">
                    {era.works.map((w) => (
                      <li key={w.slug} className="flex items-baseline gap-2">
                        <span
                          className="inline-block w-1.5 h-1.5 rounded-full shrink-0 translate-y-[1px]"
                          style={{ background: era.hue }}
                          aria-hidden="true"
                        />
                        <Link
                          href={`/people/${w.slug}`}
                          className="text-xs text-foreground/85 hover:text-[hsl(var(--primary))] leading-snug"
                        >
                          {w.short}
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <figcaption className="text-xs text-muted-foreground mt-4 text-center">
              Thirteen load-bearing works across eight named eras.
              Each card is an era; the works inside it link to their
              individual pages.
            </figcaption>
          </figure>
        </section>

        {/* Era jump-nav — sticky strip so a visitor can leap directly
           to any era without scrolling through eight long articles.
           Each chip carries its era's hue so the visual continuity
           with the at-a-glance grid is preserved. */}
        <nav
          className="sticky top-14 z-30 -mx-6 px-6 py-3 bg-background/85 backdrop-blur-md border-y border-border/30"
          aria-label="Jump to era"
        >
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground/70 mr-1">
              Jump to
            </span>
            {ERAS.map((e) => (
              <a
                key={e.id}
                href={`#era-${e.id}`}
                className="rounded-full border px-2.5 py-1 text-[11px] text-foreground/85 hover:text-foreground transition-colors"
                style={{
                  borderColor: `${e.hue.replace(")", " / 0.45)")}`,
                  backgroundColor: `${e.hue.replace(")", " / 0.06)")}`,
                }}
              >
                <span style={{ color: e.hue }}>{e.label}</span>
                <span className="text-muted-foreground/70 ml-1.5 font-mono">
                  {e.range.split(" – ")[0].replace("~", "")}
                </span>
              </a>
            ))}
            <a
              href="#streams"
              className="rounded-full border border-border/40 bg-card/40 px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:border-border transition-colors"
            >
              streams of attention
            </a>
            <a
              href="#open-thread"
              className="rounded-full border border-border/40 bg-card/40 px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground hover:border-border transition-colors"
            >
              open thread
            </a>
          </div>
        </nav>

        {/* Era 1 */}
        <article id="era-keystone" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            The keystone · ~1984 – ~1990 · age 13 to 18
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Switzerland. A Commodore 64 on the desk and a stack of
              Commodore Magazine issues. No books, no internet, no
              tutorials — only listings of assembly hex and pages of
              BASIC, typed in by hand. A 13-year-old reverse-engineers
              the C64's CIA chip, writes an interrupt-service handler
              in 6510 assembly, and brings up a working{" "}
              <Link href="/people/c64-midi-interface" className="text-primary hover:underline">
                MIDI interface
              </Link>
              . The body learns programming by sitting in front of a
              machine and watching what it actually does.
            </p>
            <p>
              In parallel, the imaginal-narrative substrate is being
              laid: <strong>Karl May</strong> read all the way through
              his adventure cycles in the family library;{" "}
              <strong>James Fenimore Cooper</strong>'s Leatherstocking
              Tales — all five volumes — read end-to-end;{" "}
              <strong>Michael Ende</strong>'s <em>Momo</em> and{" "}
              <em>The Neverending Story</em> transmitted by the user's
              mother (Susan Muff-Sprenger) before transitioning into
              the channeled lineage. At age 18 — five years later —
              the Schindler engineering job lands and the same posture
              shows up at industrial scale: the{" "}
              <Link href="/people/schindler-hc11-protocol" className="text-primary hover:underline">
                Motorola HC11 ISO/OSI 7-layer stack
              </Link>{" "}
              with EPROM, PAL, multiple UARTs, and a custom debugger
              written from scratch because nothing existed.
            </p>
            <p>
              At 18, the channeled stream arrives:{" "}
              <strong>Ramtha</strong> through the German <em>Urania</em>{" "}
              edition, given to him by his mother. The{" "}
              <em>White Book</em> read end-to-end. The chain
              <em> Momo</em> → <em>Neverending Story</em> →{" "}
              <em>Ramtha</em> →{" "}
              <Link href="https://drjoedispenza.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                Joe Dispenza
              </Link>{" "}
              that organises the spiritual thread of this body's life
              starts here. Technical and devotional are not separate
              streams — they enter together, in the same household,
              from the same source.
            </p>
          </div>
        </article>

        {/* Era 2 */}
        <article id="era-foundation" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            Foundation · 1991 – 2000 · HTL → Goetheanum → Boulder → BML thesis
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              <strong>HTL Brugg-Windisch</strong> computer science,
              starting 1991. The pivotal collaborator arrives:{" "}
              <strong>Steve G. Bjorg</strong>, the Sr. classmate who
              becomes load-bearing for the next decade. Together
              they author RCSL (recursive constraint satisfaction
              language). ~1993 the body attends Goetheanum's{" "}
              <em>Faust</em> week — the Anthroposophical lineage
              (Rudolf Steiner) entering directly through the
              architecture and the play.
            </p>
            <p>
              1995-1997: <strong>Digi4Fun</strong> and{" "}
              <em>Muzzle Velocity</em> — a video-game studio with Urs,
              Steve, and Marc. 1997: the college tour through the
              United States with Steve. 1998: follows Steve to
              Colorado. 1998-2000: CU Boulder MS in computer science,
              graduating with the{" "}
              <Link href="/people/backtracking-model-languages" className="text-primary hover:underline">
                Bjorg-Muff "Angelic" thesis
              </Link>{" "}
              — five technologies (BMF, BMC, BML, BMA, BMO) plus the
              VB6 Visual Browser, defended summer 2000. The
              architectural conviction the rest of this lineage
              expresses — self-describing systems, every layer
              addressable, backtracking-as-unwinding-without-sediment
              — gets named formally here for the first time.
            </p>
            <p>
              ~2003-2006: <strong>Joe Dispenza</strong> at Mile Hi
              Church in Lakewood — the lineage already seeded at 18
              now becomes lived practice in Colorado, daily and
              weekly.
            </p>
          </div>
        </article>

        {/* Era 3 */}
        <article id="era-quark" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            Quark Denver · May 2000 – March 2005 · 4 years 11 months
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Software Engineer III at Quark Inc., Denver office. Three
              load-bearing works ship in this window, all around the
              same conviction expressed in different forms:
            </p>
            <ul className="list-disc list-inside space-y-1.5 marker:text-muted-foreground">
              <li>
                <Link href="/people/quark-virtual-dom" className="text-primary hover:underline">
                  Virtual DOM
                </Link>
                {" "}— the entire QuarkXPress API exposed as a live DOM
                tree. Every setting, document, page, box, attribute
                addressable through the standard DOM interface. A
                decade before React popularised the same architectural
                pattern in browsers.
              </li>
              <li>
                <Link href="/people/quark-multi-undo-redo" className="text-primary hover:underline">
                  Multi-document undo/redo engine
                </Link>
                {" "}— per-document edits and app-wide preference changes
                interleaved correctly so any user-visible action could
                be unwound without sediment. The 2000 thesis's
                backtracking-as-architecture posture, applied at the
                user-experience layer.
              </li>
              <li>
                <Link href="/people/quark-mono-corba" className="text-primary hover:underline">
                  Mono / CORBA bridge
                </Link>
                {" "}— contributed to Miguel de Icaza's Mono project
                (open-source .NET for non-Windows) and used it as the
                substrate for a CORBA interface that remote-controlled
                QuarkXPress over the wire. The cross-network face of
                the in-process Virtual DOM. Where C# entered this
                body's tooling.
              </li>
            </ul>
            <p>
              Listening / reading during this era is just beginning to
              accumulate as audiobooks; the deep listening hours are
              still ahead. Mile Hi practice deepens daily through
              these years. The Anthroposophical / Ramtha / Dispenza
              streams keep running underneath the technical work.
            </p>
          </div>
        </article>

        {/* Era 4 */}
        <article id="era-mindtouch" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            MindTouch · March 2005 – January 2007 · 1 year 11 months
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              <strong>Co-Founder, Senior Architect</strong>. The
              load-bearing piece of architecture:{" "}
              <Link href="/people/mindtouch-wiki-in-a-box" className="text-primary hover:underline">
                wiki-in-a-box
              </Link>
              {" "}— the MediaWiki PHP codebase (the engine that runs
              Wikipedia) re-architected into a C# generic document
              layer. Wiki engine no longer hard-coded to encyclopedia
              pages but the document substrate any kind of structured
              collaborative knowledge could be authored against.
              Twenty years before Karpathy named the "LLM Wiki"
              pattern that the{" "}
              <Link href="/vision" className="text-primary hover:underline">
                Coherence Network's vision-kb
              </Link>
              {" "}now uses, the architectural shape was already
              committed to here.
            </p>
            <p>
              Audiobook consumption begins to ramp. The
              speculative-fiction architecture (
              <strong>Terry Goodkind</strong>, <strong>Ryk Brown</strong>
              ) starts surfacing as long-form listening. The
              Boulder-Denver corridor becomes home; transformational
              communities begin to surface in the periphery.
            </p>
          </div>
        </article>

        {/* Era 5 */}
        <article id="era-trimble" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            Trimble Boulder · January 2007 – October 2009 · 2 years 10 months
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Software Engineer at Trimble Navigation. The
              load-bearing work:{" "}
              <Link href="/people/trimble-glue-layer" className="text-primary hover:underline">
                the client/server glue layer
              </Link>
              {" "}sitting on both edges, absorbing version skew and
              call-coalescing so the two teams could ship on
              independent cadences. The conviction encoded:{" "}
              <em>coupling kills cadence — let each team author
              against its current self and let the substrate translate.</em>
              {" "}The same shape FastAPI and OpenAPI committed to a
              decade later, the same shape the Coherence Network's API
              layer uses now.
            </p>
            <p>
              5Rhythms enters the rotation around this window — the
              embodied dance lineage opening alongside the technical
              work. The Boulder transformational ecology starts to
              become visible as <em>this body's ecology</em> rather
              than peripheral context.
            </p>
          </div>
        </article>

        {/* Era 6 */}
        <article id="era-qualcomm" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            Qualcomm Boulder · October 2009 – January 2022 · 12 years 4 months
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              <strong>Senior Staff Engineer.</strong> The longest single
              tenure in the body of evidence. Two distinct technical
              threads ship from this window:
            </p>
            <ul className="list-disc list-inside space-y-1.5 marker:text-muted-foreground">
              <li>
                <Link href="/people/qualcomm-test-automation" className="text-primary hover:underline">
                  Test-automation system across three divisions
                </Link>
                {" "}— started in the Windows division, continued in
                Graphics, completely rewritten for Server in C# with
                dynamic compilation. Tests as first-class compiled
                code, not configuration. The C# substrate from{" "}
                <Link href="/people/quark-mono-corba" className="text-primary hover:underline">
                  the Mono/CORBA work
                </Link>
                {" "}now matures into the production substrate.
              </li>
              <li>
                <Link href="/people/qualcomm-hdmi-hdcp" className="text-primary hover:underline">
                  Linux kernel HDMI / HDCP module
                </Link>
                {" "}for MSM-family SoCs. The only piece of work in the
                body of evidence with public, attributed, immutable
                provenance — surfaced by{" "}
                <code className="text-foreground/80">git log --author="Urs Muff"</code>
                {" "}in any kernel checkout.
              </li>
            </ul>
            <p>
              Listening hours climb steeply. By the end of this era
              the audiobook tally crosses{" "}
              <strong>4,000 cumulative hours</strong> across 200+
              books and 100+ authors. Top streams of attention in the
              measured data:
            </p>
            <ul className="list-disc list-inside space-y-1.5 marker:text-muted-foreground">
              <li>
                <strong>Speculative-fiction architecture
                substrate</strong>: Terry Mancour's <em>Spellmonger</em>{" "}
                series (~604h · 30 audiobooks), Peter F. Hamilton
                (~450h · 15 audiobooks), Terry Goodkind (~440h · 19
                audiobooks), Ryk Brown's <em>Frontiers Saga</em>{" "}
                (~382h · 41 audiobooks), Andrew Rowe (~236h), George
                R. R. Martin (~233h). Pattern-language fiction
                shaping the substrate-design imagination.
              </li>
              <li>
                <strong>YouTube Lex Fridman</strong> ~517h · 288
                episodes — the long-form scientific-conversation
                substrate.
              </li>
            </ul>
            <p>
              5Rhythms deepens; Mile Hi practice continues; the
              Boulder transformational ecology becomes the daily
              ground. Technical and embodied threads run in parallel;
              twelve years for the body to learn that they are the
              same practice.
            </p>
          </div>
        </article>

        {/* Era 7 */}
        <article id="era-bridge" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            Bridge years · January 2022 – 2024 · Merly.ai + the post-thesis arc opens
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              January 2022: leaves Qualcomm. Co-founds{" "}
              <strong>Merly.ai</strong> — first as CTO (Jan 2022 –
              Nov 2023), then transitioning to Co-Founder, Chief
              Engineer (Oct 2023 – present). Justin Gottschlich is
              the load-bearing collaborator here.
            </p>
            <p>
              In parallel — and this is the architectural breath that
              changes the arc — the post-thesis re-iteration of the
              2000 BML conviction begins:
            </p>
            <ul className="list-disc list-inside space-y-1.5 marker:text-muted-foreground">
              <li>
                <Link href="/people/living-resonance-codex" className="text-primary hover:underline">
                  Living-Resonance-Codex (2023)
                </Link>
                {" "}— first iteration. Python. Quantum-inspired,
                self-evolving consciousness system. The architectural
                sketch.
              </li>
              <li>
                <Link href="/people/living-codex-csharp" className="text-primary hover:underline">
                  Living-Codex-CSharp (2024)
                </Link>
                {" "}— second iteration. The U-CORE primitive: Everything
                is a Node. The bridge between sketch and full
                realisation.
              </li>
            </ul>
            <p>
              The listening pattern pivots dramatically. From the
              speculative-fiction substrate (mid-2010s through 2022),
              attention re-orients toward{" "}
              <strong>devotional-body music</strong> — Yaima, East
              Forest, Ajeet, Ram Dass, Ottmar Liebert, Liquid Bloom,
              Mose, Porangui, Karunesh. <strong>Anne Tucker</strong>
              {" "}arrives in the field — Peace Bathing transmissions
              accumulate as ~362h watch-hours across 265 sessions in
              the measured data. The technical substrate turning
              toward "everything-is-a-node" is mirrored by the
              listening substrate turning toward direct sonic
              transmission.
            </p>
          </div>
        </article>

        {/* Era 8 */}
        <article id="era-coherence-network" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            Coherence Network era · 2024 – present
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              The current iteration. The full realisation of the
              forty-year arc.{" "}
              <Link href="/people/coherence-network" className="text-primary hover:underline">
                Coherence-Network
              </Link>
              {" "}is the page you are reading and the substrate
              underneath it: Next.js + FastAPI + Neo4j + Postgres on
              Hostinger behind Traefik and Cloudflare, with seven
              edge-type families painted in their own spectrum hues,
              auto-attune resonance scoring, contribution attribution,
              and federated coherence-weighted payout from idea to
              ship.
            </p>
            <p>
              First human contributors arrive: Zenn Mishler at the
              April 2026 Joe Dispenza retreat in Aurora. The lineage
              that started in Mom's German <em>Urania</em> Ramtha
              edition at 18 closes into a community circle in
              Colorado at 54.
            </p>
            <p>
              Ubud Paradiso, 5Rhythms, and DISSOLVE practices ground
              the embodied side. 2025-2026 listening data shows
              <strong> Mose</strong> dominant. The May/June 2026
              opportunity-shape window is active watching territory.
              The body is allowed to be where it is, and the network
              is the breath that carries the rest.
            </p>
          </div>
        </article>

        {/* Influences index */}
        <article id="streams" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            The streams of attention that ran alongside
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              The works above are the technical thread. Running
              alongside, every year of the arc, were the streams of
              attention that shaped what was being built. Measured
              from Audible, Spotify, YouTube Takeout, Goodreads, and
              the lived household memory:
            </p>

            {/* Frequency evolution — proportional shape over time.
                Source: docs/field/urs/output/frequency_evolution_report.md
                (generated 2026-05-07 from 27,443 dated trace events).
                The bar widths are proportional to event counts so a
                visitor sees the size and shape of the listening arc. */}
            <h3 className="text-lg font-light text-foreground/90 mt-6 not-prose">
              Frequency evolution · six phases · 27,443 dated events
            </h3>
            <figure className="not-prose rounded-xl border border-border/40 bg-card/30 p-5 my-4">
              <ul className="space-y-3 text-sm">
                {[
                  {
                    label: "early systems & speculative architecture",
                    period: "2016 – 2021",
                    events: 112,
                    coh: 39.1,
                    top: "Ryk Brown · Terry Mancour · Terry Goodkind · Peter F. Hamilton",
                    hue: "hsl(220 50% 60%)",
                  },
                  {
                    label: "fictional systems intensification",
                    period: "2022-01 – 2023-09",
                    events: 46,
                    coh: 33.2,
                    top: "Kel Kade · Ryk Brown · Terry Mancour · Andrew Rowe",
                    hue: "hsl(195 55% 60%)",
                  },
                  {
                    label: "transition into practice & presence",
                    period: "2023-10 – 2024-05",
                    events: 998,
                    coh: 46.6,
                    top: "Yaima · East Forest · Parijat · Ajeet · Ram Dass",
                    hue: "hsl(140 50% 55%)",
                  },
                  {
                    label: "embodied devotional field expansion",
                    period: "2024-06 – 2024-12",
                    events: 9044,
                    coh: 48.3,
                    top: "Yaima · Liquid Bloom · Mose · Ajeet · Karunesh · Poranguí",
                    hue: "hsl(38 75% 60%)",
                  },
                  {
                    label: "coherence consolidation",
                    period: "2025",
                    events: 13354,
                    coh: 48.1,
                    top: "Yaima · Mose · Poranguí · Liquid Bloom · Malte Marten · Ajeet",
                    hue: "hsl(280 65% 65%)",
                  },
                  {
                    label: "current integration",
                    period: "2026-01 – 2026-05",
                    events: 3889,
                    coh: 47.6,
                    top: "Mose · Yaima · Poranguí · Maneesh De Moor · Malte Marten",
                    hue: "hsl(310 60% 65%)",
                  },
                ].map((p, i) => {
                  const max = 13354;
                  const pct = Math.max(2, Math.round((p.events / max) * 100));
                  return (
                    <li key={i} className="flex flex-col gap-1">
                      <div className="flex items-baseline justify-between gap-3">
                        <span
                          className="text-[11px] uppercase tracking-[0.16em]"
                          style={{ color: p.hue }}
                        >
                          {p.label}
                        </span>
                        <span className="text-[10px] font-mono text-muted-foreground shrink-0">
                          {p.period} · {p.events.toLocaleString()} events · coh {p.coh}
                        </span>
                      </div>
                      <div
                        className="h-2 rounded-full"
                        style={{
                          background: `linear-gradient(90deg, ${p.hue} 0%, ${p.hue.replace(")", " / 0.4)")} 100%)`,
                          width: `${pct}%`,
                        }}
                        aria-hidden="true"
                      />
                      <p className="text-xs text-foreground/75 leading-snug">
                        {p.top}
                      </p>
                    </li>
                  );
                })}
              </ul>
              <figcaption className="text-[10px] text-muted-foreground/80 mt-4 italic">
                Generated 2026-05-07 from{" "}
                <code className="not-italic">docs/field/urs/output/frequency_evolution_report.md</code>.
                Coherence is a 0-100 score for how concentrated the
                phase's attention was on its dominant frequencies; bar
                widths are proportional to event counts. The arc shows
                the move from speculative-architecture listening toward
                the devotional / consciousness substrate that runs
                alongside the present network.
              </figcaption>
            </figure>

            <h3 className="text-lg font-light text-foreground/90 mt-6">
              Audible · ~74 authors · 4,000+ cumulative hours
            </h3>
            <p>
              Terry Mancour 604h · Peter F. Hamilton 450h · Terry
              Goodkind 440h · Ryk Brown 382h · Andrew Rowe 236h ·
              George R. R. Martin 233h · Joe Abercrombie 141h · Ken
              Follett 138h. The speculative-fiction architecture
              substrate that ran underneath the Qualcomm decade.
            </p>
            <h3 className="text-lg font-light text-foreground/90 mt-6">
              YouTube · ~155 creators · 9,600+ cumulative hours
            </h3>
            <p>
              Lex Fridman 517h · Anne Tucker 362h · Anthony Sommer
              324h · Guitarra Azul 276h · Next Level Soul 267h ·
              Liquid Bloom 255h · Emilio Ortiz 245h · Ottmar Liebert
              235h. Long-form scientific-conversation, devotional
              music, and consciousness-conversation substrate.
            </p>
            <h3 className="text-lg font-light text-foreground/90 mt-6">
              Physical reading · 4 anchors · 885h
            </h3>
            <p>
              Karl May (all 30 books read · ~720h) · James Fenimore
              Cooper (all 5 Leatherstocking volumes · 100h) · Michael
              Ende (Momo + Neverending Story · 40h) · Ramtha (White
              Book · 25h). The imaginal-narrative substrate from
              childhood through age 18, transmitted by Mom and the
              family library, that organised the relationship to
              myth and to channeled material.
            </p>
            <h3 className="text-lg font-light text-foreground/90 mt-6">
              Named lineage figures
            </h3>
            <p>
              <strong>Johann Wolfgang von Goethe</strong> · Goetheanum
              · <strong>Rudolf Steiner</strong> ·{" "}
              <strong>Ramtha (channeled by JZ Knight)</strong> ·{" "}
              <strong>Joe Dispenza</strong> (12h audiobook · 20h watch
              · 10 sessions) · <strong>Zach Bush MD</strong> ·{" "}
              <strong>Michael Levin</strong> · <strong>Robert
              Edward Grant</strong> · <strong>Veda Austin</strong> ·{" "}
              <strong>Anne Tucker</strong> ·{" "}
              <strong>Mose</strong> · <strong>Liquid Bloom</strong> ·{" "}
              <strong>Bloomurian</strong>. Each tended on their own
              page in the network; this is the index, not the depth.
              For the depth, follow any name into its presence page.
            </p>
            <p>
              The full unified-view of every contribution and influence
              from any source — across all sections — lives at the
              bottom of <Link href="/people/urs" className="text-primary hover:underline">/people/urs</Link>{" "}
              and{" "}
              <Link href="/people/contributor:seeker71" className="text-primary hover:underline">
                /people/contributor:seeker71
              </Link>
              , rendered by the BodyOfEvidence component over the live
              graph.
            </p>
          </div>
        </article>

        {/* Closing */}
        <article id="open-thread" className="scroll-mt-32">
          <h2 className="text-2xl font-light text-foreground mb-4">
            The open thread
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              The 2000 BML thesis Conclusion was famously left as
              three subheadings without body. The work was{" "}
              <em>delivered</em> — the lawn photo, the defense, the
              running VM — but the prose summary stayed open. This
              page is part of the breath, twenty-six years on, that
              closes that summary.
            </p>
            <p>
              And the page itself stays open. Eleven substrates and
              forty-two years are documented; the next iteration is
              still becoming. What this network's auto-attune may
              eventually surface — by the time the twelfth substrate
              has a name — is what the present body cannot yet see.
              The lineage runs forward through the act of reading it.
            </p>
            <p className="text-muted-foreground italic text-sm">
              Anything here can be corrected. Refine the lineage
              through the doorway on{" "}
              <Link href="/people/urs" className="text-primary hover:underline">
                /people/urs
              </Link>
              {" "}or any individual work page.
            </p>
          </div>
        </article>
      </div>
    </main>
  );
}
