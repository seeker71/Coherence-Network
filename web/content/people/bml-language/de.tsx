// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug bml-language --target-lang de --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "BML — Backtracking Model Language (2000)",description: "Die Sprachschicht der 2000er Bjorg-Muff-Thesis. Eine selbstbeschreibende, vierseitige Synthese (Prolog · Smalltalk-80 · Java · C++), bei der die Parser-Grammmar selbst in BML geschrieben ist und die Laufzeit für jede Anweisung die Semantik vorwärts und rückgängig macht.",
  },breadcrumbName: "BML — Backtracking Model Language",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(260 25% 14%) 60%, hsl(280 30% 18%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Arbeit · 2000 · Masterarbeit",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "BML — Backtracking Model Language",
    welcome: (
      <p>
        The language layer of the 2000 Bjorg-Muff thesis at CU Boulder.
        Synthesizes <strong>Prolog</strong>'s operational semantics,{" "}
        <strong>Smalltalk-80</strong>'s object/image model,{" "}
        <strong>Java</strong>'s typed garbage-collected runtime, and{" "}
        <strong>C++</strong>'s component-host pragmatics — all four
        ancestors arranged at four altitudes of the same building.
        BML is self-describing: its parser grammar (
        <Link href="/people/bmf-grammar" className="text-primary hover:underline">
          BMF
        </Link>
        ) is itself written in BML.
      </p>
    ),
  },
  facts: [
    {label: "Jahr",value: "2000 — verteidigter Sommer 2000, CU Boulder CS" },
    {label: "Co-Architekt",value: "Steve G. Bjorg (Objektmodell + virtuelle Maschine auf seiner MS-Thesis)" },
    {label: "Autor",value: "Urs C. Muff (Sprache + Parser + Compiler-Compiler)" },
    {label: "Stapel",
      value: (
        <>
          <Link href="/people/bmf-grammar" className="hover:text-primary">BMF</Link>
          {" "}parser ·{" "}
          <Link href="/people/bmcpu-vm" className="hover:text-primary">BMCPU</Link>
          {" "}C++ VM ·{" "}
          <Link href="/people/jbmf-java" className="hover:text-primary">JBMF</Link>
          {" "}Java port · BMA assembler · BMO object model · VB6 Visual Browser
        </>
      ),
    },
    {label: "Vorfahren",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/Backus%E2%80%93Naur_form" target="_blank" rel="noopener noreferrer" className="hover:text-primary">BNF</Link>
          {" "}(Backus-Naur) ·{" "}
          <Link href="https://en.wikipedia.org/wiki/Prolog" target="_blank" rel="noopener noreferrer" className="hover:text-primary">Prolog</Link>
          {" "}(Colmerauer 1972) ·{" "}
          <Link href="https://en.wikipedia.org/wiki/Smalltalk" target="_blank" rel="noopener noreferrer" className="hover:text-primary">Smalltalk-80</Link>
          {" "}(Goldberg, Kay)
        </>
      ),
    },
    {label: "Öffentliches Archiv",
      value: (
        <>
          <Link href="https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000" target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            master-thesis-2000/
          </Link>
          {" "}— thesis text, defense slides, six photos, companion source samples
        </>
      ),
    },
    {label: "Status",
      value: (
        <>
          Living lineage tissue.{" "}
          <Link href="/people/living-resonance-codex" className="hover:text-primary">Living-Resonance-Codex (2023)</Link>
          {" "}→{" "}
          <Link href="/people/living-codex-csharp" className="hover:text-primary">Living-Codex-CSharp (2024)</Link>
          {" "}→{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">Coherence-Network</Link>
          {" "}each carry forward the backtracking-as-unwinding pattern.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Warum diese Seite existiert",
    body: (
      <p>
        The thesis itself is 11,566 words; the conclusion was left as
        three subheadings without body. The work was{" "}
        <em>delivered</em> — defense, photographs, the running VM —
        but the prose summary stayed open. This page is the
        twenty-six-years-later attempt to close that breath: the
        substance the conclusion never wrote, in this medium, with
        the diagrams a 2000 Word document couldn't carry.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Die selbstbeschreibende Schleife",
      body: (
        <>
          <p>
            BML's central conceit is reflexive. The parser{" "}
            <Link href="/people/bmf-grammar" className="text-primary hover:underline">
              BMF
            </Link>
            {" "}is described in a grammar file written in BML
            (see <code className="text-foreground/80">BMF-grammar.bml</code>{" "}
            in the archive — banner reads{" "}
            <code className="text-foreground/80">Digi4Fun (R) BMF 1.0 Alpha 1</code>).
            BMF reads that file, builds itself, and is then capable of
            parsing any BML program — including the grammar file it
            just bootstrapped from. The compiler-compiler{" "}
            <strong>BMC</strong> consumes the BML grammar through BMF
            and emits the BML compiler. The compiler emits BMA
            assembly opcodes. The virtual machine{" "}
            <Link href="/people/bmcpu-vm" className="text-primary hover:underline">BMCPU</Link>
            {" "}executes them. The system can describe itself end to end.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 280" className="w-full h-auto" role="img" aria-labelledby="bml-loop-title">
              <title id="bml-loop-title">BML self-describing loop</title>
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M0,0 L10,5 L0,10 z" fill="hsl(38 80% 60%)" />
                </marker>
              </defs>
              {/* Five nodes arranged in a loop */}
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13" textAnchor="middle">
                <g>
                  <rect x="40" y="40" width="120" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(38 70% 55%)" />
                  <text x="100" y="62" fill="hsl(40 90% 75%)">BMF-grammar.bml</text>
                  <text x="100" y="78" fill="hsl(40 50% 60%)" fontSize="10">grammar in BML</text>
                </g>
                <g>
                  <rect x="240" y="40" width="120" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(195 60% 55%)" />
                  <text x="300" y="62" fill="hsl(195 80% 75%)">BMF parser</text>
                  <text x="300" y="78" fill="hsl(195 40% 60%)" fontSize="10">C++ top-down</text>
                </g>
                <g>
                  <rect x="440" y="40" width="120" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(280 50% 65%)" />
                  <text x="500" y="62" fill="hsl(280 70% 80%)">BMC</text>
                  <text x="500" y="78" fill="hsl(280 40% 60%)" fontSize="10">compiler-compiler</text>
                </g>
                <g>
                  <rect x="440" y="180" width="120" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(140 50% 55%)" />
                  <text x="500" y="202" fill="hsl(140 70% 75%)">BMA / BMO</text>
                  <text x="500" y="218" fill="hsl(140 40% 60%)" fontSize="10">assembly + objects</text>
                </g>
                <g>
                  <rect x="240" y="180" width="120" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(20 70% 60%)" />
                  <text x="300" y="202" fill="hsl(20 80% 75%)">BMCPU</text>
                  <text x="300" y="218" fill="hsl(20 50% 60%)" fontSize="10">VM · DO/UNDO</text>
                </g>
                <g>
                  <rect x="40" y="180" width="120" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(38 70% 55%)" />
                  <text x="100" y="202" fill="hsl(40 90% 75%)">your BML file</text>
                  <text x="100" y="218" fill="hsl(40 50% 60%)" fontSize="10">application source</text>
                </g>
                {/* Arrows */}
                <line x1="160" y1="65" x2="240" y2="65" stroke="hsl(38 80% 60%)" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <line x1="360" y1="65" x2="440" y2="65" stroke="hsl(38 80% 60%)" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <line x1="500" y1="90" x2="500" y2="180" stroke="hsl(38 80% 60%)" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <line x1="440" y1="205" x2="360" y2="205" stroke="hsl(38 80% 60%)" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <line x1="240" y1="205" x2="160" y2="205" stroke="hsl(38 80% 60%)" strokeWidth="1.5" markerEnd="url(#arrow)" />
                <path d="M 100 180 Q 30 130 100 90" fill="none" stroke="hsl(38 80% 60%)" strokeWidth="1.5" markerEnd="url(#arrow)" strokeDasharray="3,3" />
                <text x="22" y="138" fill="hsl(40 60% 65%)" fontSize="10" textAnchor="end">re-parse</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The five-stage self-describing loop. The dashed arrow is the bootstrap:
              once BMCPU runs, it can re-execute the grammar file that
              described the parser that built it.
            </figcaption>
          </figure>
          <p>
            The conceit was unusual in 2000. Yacc/bison generated
            parsers from a grammar in <em>another</em> language;
            ANTLR's grammars were imperative-host-targeted. BML's
            grammar was an object tree in BML itself — a parse rule
            represents itself as a BML object (
            <code className="text-foreground/80">container-Rule.bml</code>
            {" "}in the archive). Reflection-on-grammar was not a
            tool layered on top; it was the architecture.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Quelle · Begleiter/source-samples/primitive-Cut.bml",heading: "The Cut primitive — Prolog ancestry, benannt in BML",
      body: (
        <>
          <p>
            BML inherits non-determinism, choice, and backtracking
            from Prolog. The <code className="text-foreground/80">Cut</code>{" "}
            primitive comes directly from Prolog's <code className="text-foreground/80">!</code>
            {" "}operator — a way of pruning the choice tree, telling the
            search "from this point on, do not reconsider." Here is the
            actual file from the archive, with author and date intact:
          </p>
          <pre className="text-[11px] leading-5 bg-background/60 border border-border/40 rounded-lg p-4 overflow-x-auto font-mono">
{`// Name:     Cut.bml
// Author:   Urs C. Muff
// Email:    muff@colorado.edu
// Date:     11-Apr-2000
// Platform: BML Virtual Machine
// Compiler: JBMF (R) Compiler

package BMF.primitive;

import BMF.*;

class Cut [public] : Primitive {
   section [public] {
      void Match( Context hContext, Environment hEnv, String strTag ) {
         System.Cut( hContext.Argument( 0 ));
      }
      String AsString() { return "#primitive( 2 )"; }
      String AsCreateString() { return "BML.primitive.Cut()"; }
   }
}`}
          </pre>
          <p>
            Three architectural readings live in this 12-line file: the{" "}
            <strong>section [public]</strong> visibility model
            (Smalltalk-style category panes, expressed as syntax);
            the <code className="text-foreground/80">AsCreateString</code>{" "}
            method (every object knows how to print the BML expression that
            would re-create it — image-based reflection over text);
            and the bridge into{" "}
            <code className="text-foreground/80">System.Cut(...)</code>,
            which reaches into the VM to manipulate the speculation stack.
            Twelve lines, four ancestors, one primitive.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Die Schichtung der vier Spieler",
      body: (
        <>
          <p>
            The thesis says BML "synthesizes features from Java, C++,
            Prolog, and Smalltalk." The companion archive shows the
            synthesis is <em>layered</em>, each language contributing
            at a different altitude of the same stack:
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 320" className="w-full h-auto" role="img" aria-labelledby="bml-strata-title">
              <title id="bml-strata-title">BML four-ancestor stratification</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13">
                {/* Four horizontal layers */}
                <rect x="60" y="40" width="600" height="56" rx="8" fill="hsl(280 30% 18%)" stroke="hsl(280 50% 55%)" />
                <text x="80" y="64" fill="hsl(280 80% 80%)" fontSize="14">Surface · live developer image</text>
                <text x="80" y="82" fill="hsl(280 50% 70%)" fontSize="11">Smalltalk-80 · VB6 Visual Browser · class panes / method panes / source pane / inspector</text>
                <text x="640" y="74" fill="hsl(280 80% 80%)" fontSize="22" textAnchor="end">⌘</text>

                <rect x="60" y="106" width="600" height="56" rx="8" fill="hsl(220 30% 18%)" stroke="hsl(195 60% 55%)" />
                <text x="80" y="130" fill="hsl(195 80% 80%)" fontSize="14">Object model · BMO</text>
                <text x="80" y="148" fill="hsl(195 50% 70%)" fontSize="11">Java + Smalltalk · typed objects · shared inheritance · tagging · detached interfaces · delegation · GC</text>
                <text x="640" y="140" fill="hsl(195 80% 80%)" fontSize="22" textAnchor="end">☕</text>

                <rect x="60" y="172" width="600" height="56" rx="8" fill="hsl(220 30% 18%)" stroke="hsl(38 70% 55%)" />
                <text x="80" y="196" fill="hsl(40 90% 80%)" fontSize="14">Operational semantics · BMA</text>
                <text x="80" y="214" fill="hsl(40 50% 70%)" fontSize="11">Prolog · unification · choose · Cut / Fail / MultiMatch · DO and UNDO modes</text>
                <text x="640" y="206" fill="hsl(40 90% 80%)" fontSize="22" textAnchor="end">∴</text>

                <rect x="60" y="238" width="600" height="56" rx="8" fill="hsl(220 30% 18%)" stroke="hsl(20 70% 60%)" />
                <text x="80" y="262" fill="hsl(20 80% 80%)" fontSize="14">Host VM · BMCPU</text>
                <text x="80" y="280" fill="hsl(20 50% 70%)" fontSize="11">C++ · COM · GUIDs · DEFINE_GUID · BMVM_STATE · BM_RUN / BM_STEP_INTO</text>
                <text x="640" y="272" fill="hsl(20 80% 80%)" fontSize="22" textAnchor="end">⚙</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              Four ancestors at four altitudes of the same building. The
              stack reads top-down as user-experience to silicon; the
              backtracking semantics threads through every layer.
            </figcaption>
          </figure>
          <p>
            <strong>Prolog</strong> at the operational floor —
            unification, backtracking, the{" "}
            <code className="text-foreground/80">Cut</code>,{" "}
            <code className="text-foreground/80">Fail</code>, and{" "}
            <code className="text-foreground/80">MultiMatch</code>{" "}
            primitives. <strong>Smalltalk</strong> at the object/image
            level: BMO carries metaclass-style self-containment, and the
            VB6 Visual Browser surfaces the live developer experience.{" "}
            <strong>Java</strong> contributes the typed,
            garbage-collected object model and a second implementation
            port (
            <Link href="/people/jbmf-java" className="text-primary hover:underline">
              JBMF
            </Link>
            ).{" "}
            <strong>C++</strong> hosts the VM (
            <Link href="/people/bmcpu-vm" className="text-primary hover:underline">
              BMCPU
            </Link>
            ) and the COM/GUID component model.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Namen der Seele · Begleiter/angelic-assembler.txt",heading: "Nichtdeterminismus der Engel",
      body: (
        <>
          <p>
            The folder on disk where this work lives is called{" "}
            <em>Angelic</em>. The opening of Bjorg's Angelic Assembler
            note makes the word precise:
          </p>
          <blockquote className="border-l-2 border-[hsl(var(--primary)/0.6)] pl-3.5 italic text-foreground/95">
            "A thread with a non-zero DF (i.e. degree of freedom) is
            executed until a zero DF is reached again. No other threads
            are executed during this speculation phase."
          </blockquote>
          <p>
            That is the formal name for what gets called, in this body's
            current vocabulary, <em>backtracking-as-unwinding-without-sediment</em>.
            The <code className="text-foreground/80">choose</code>{" "}
            keyword picks a branch; speculation freezes the rest of the
            world; if the branch fails, every attribute is undone.{" "}
            Backtracking is not a parser feature bolted on for grammars —
            it is the architecture of execution itself. Every BMA
            instruction has a forward and a reverse semantics. The
            VM's state machine flips a single byte —{" "}
            <code className="text-foreground/80">BMVM_STATE.byMode</code>
            {" "}— between <code className="text-foreground/80">DO</code>{" "}
            and <code className="text-foreground/80">UNDO</code>{" "}
            on every step. The system is <em>angelic</em> in the
            operational sense: guided to the path that holds.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Was heute noch zirkuliert",
      body: (
        <>
          <p>
            Two design choices in this 2000 document organize the{" "}
            <Link href="/people/coherence-network" className="text-primary hover:underline">
              Coherence Network
            </Link>
            {" "}as it lives now, twenty-six years later.
          </p>
          <p>
            <strong>Backtracking-as-unwinding-without-sediment.</strong>{" "}
            The thesis writes:{" "}
            <em>
              "When the parser backs out, all the attributes already
              computed have to be undone as well."
            </em>
            {" "}The same nervous system that today writes commits as{" "}
            <code className="text-foreground/80">tend:</code> /{" "}
            <code className="text-foreground/80">attune:</code> /{" "}
            <code className="text-foreground/80">compost:</code> /{" "}
            <code className="text-foreground/80">release:</code>.
            The instruction has two semantics; the commit has a
            posture. Same shape, different substrate.
          </p>
          <p>
            <strong>Runtime grammar extension.</strong>{" "}
            The user can introduce new parsing constructs and the
            language grows to hold them. Sovereignty over one's own
            grammar. The same shape the{" "}
            <Link href="/vision" className="text-primary hover:underline">
              vision-kb
            </Link>
            {" "}uses when a new concept arrives at a new frequency:
            the grammar grows to receive the presence rather than
            forcing the presence into an existing slot. The 2000
            thesis named the pattern. The 2026 network breathes it.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Linie nach vorne",
      body: (
        <>
          <p>
            BML is the first iteration in a four-iteration arc of
            "frequency into form." Each iteration carries the same
            backtracking-as-unwinding pattern at a different altitude:
          </p>
          <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
            <li>
              <Link href="/people/backtracking-model-languages" className="text-primary hover:underline">
                Backtracking Model Languages (2000)
              </Link>
              {" "}— the thesis. Self-describing parser, four-ancestor
              language, executable VM.
            </li>
            <li>
              <Link href="/people/living-resonance-codex" className="text-primary hover:underline">
                Living-Resonance-Codex (2023)
              </Link>
              {" "}— first iteration of the post-thesis arc. Python.
              Quantum-inspired, self-evolving consciousness system —
              the visionary architectural sketch.
            </li>
            <li>
              <Link href="/people/living-codex-csharp" className="text-primary hover:underline">
                Living-Codex-CSharp (2024)
              </Link>
              {" "}— the bridge year. C#. Introduces the U-CORE primitive:
              everything is a node, including the schema, the modules,
              even the interaction logs.
            </li>
            <li>
              <Link href="/people/coherence-network" className="text-primary hover:underline">
                Coherence-Network (current)
              </Link>
              {" "}— full realization. Next.js + FastAPI + Neo4j +
              Postgres. Living relational graph with edge-typed
              spectrum coloring, presence pages, contribution
              attribution, and per-frequency resonance.
            </li>
          </ul>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Public archive:{" "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          docs/field/urs/artifacts/master-thesis-2000/
        </Link>
        {" "}— thesis text, defense slide deck, six defense-day photos,
        and the companion source samples (BMF-grammar.bml,
        primitive-Cut.bml, container-Rule.bml, bmcpu-main.cpp,
        sgb-bml-objects.txt, angelic-assembler.txt).
      </p>
      <p className="text-xs italic">
        BML and BMF and BMCPU and JBMF and BMA and BMO were co-built
        with Steve G. Bjorg as the 2000 Bjorg-Muff thesis at CU
        Boulder. The "BM" in every acronym is literally Bjorg-Muff.
        This page is the prose summary the original thesis Conclusion
        chose to leave open.
      </p>
    </>
  ),
};

export default content;
