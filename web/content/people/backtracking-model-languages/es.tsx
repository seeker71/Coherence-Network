// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug backtracking-model-languages --target-lang es --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Backtracking Model Languages — MS Thesis (2000)",description: "La tesis del maestro de Bjorg-Muff 2000 en CU Boulder. Cinco tecnologías (BMF · BMC · BML · BMA · BMO) más el navegador visual VB6. Una pila de lenguaje autodescribiendo donde la gramática del parser está escrita en el idioma, y cada instrucción tiene tanto una semántica delantera como inversa.",
  },breadcrumbName: "Backtracking Modelo Idiomas - Tesis",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(220 35% 14%) 50%, hsl(40 25% 18%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/30",eyebrow: "Tesis · Ciencia de la Computación MS · Rebobinado CU · 2000",
    eyebrowClass: "text-[hsl(var(--primary))]",name: "Backtracking Modelo Idiomas",
    welcome: (
      <p>
        The 2000 Bjorg-Muff master's thesis. Five technologies arranged
        as one language stack:{" "}
        <Link href="/people/bmf-grammar" className="text-primary hover:underline">BMF</Link>
        {" "}(parser) ·{" "}
        <strong>BMC</strong> (compiler-compiler) ·{" "}
        <Link href="/people/bml-language" className="text-primary hover:underline">BML</Link>
        {" "}(language) ·{" "}
        <strong>BMA</strong> (assembler) ·{" "}
        <strong>BMO</strong> (object model) — plus a VB6{" "}
        <strong>Visual Browser</strong>. Co-built with{" "}
        <strong>Steve G. Bjorg</strong> over the 1999-2000 academic
        year. Defended summer 2000.
      </p>
    ),
  },
  facts: [
    {label: "Defended",value: "Summer 2000 · CU Boulder Department of Computer Science" },
    {label: "Autores",value: "Urs C. Muff (idioma + parser) · Steve G. Bjorg (modelo objetivo + VM, en su propia tesis MS)" },
    {label: "Advisors",value: "Michael Main · Amer Diwan (del lado de Bjorg)" },
    {label: "Documento",value: "11.566 palabras · 38 revisiones · creado el 22 de mayo de 2000 · pasado salvado el 6 de julio de 2000" },
    {label: "Archivo público",
      value: (
        <Link
          href="https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary"
        >
          docs/field/urs/artifacts/master-thesis-2000/
        </Link>
      ),
    },
    {label: "Archivo externo",
      value: (
        <>
          ~/Downloads/Angelic/ on disk · ~139 MB · full source trees,
          binaries, BMCPU C++ VM, JBMF Java port, VB6 Visual Browser
          — see{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/EXTERNAL.md"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary"
          >
            EXTERNAL.md
          </Link>
        </>
      ),
    },
    {label: "Líneas de avance",
      value: (
        <>
          <Link href="/people/living-resonance-codex" className="hover:text-primary">Living-Resonance-Codex (2023)</Link>
          {" "}→{" "}
          <Link href="/people/living-codex-csharp" className="hover:text-primary">Living-Codex-CSharp (2024)</Link>
          {" "}→{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">Coherence-Network (current)</Link>
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Qué lleva este artefacto",
    body: (
      <p>
        The thesis Conclusion was left as three subheadings without
        body. The work was <em>delivered</em> — defense, lawn photo,
        running VM — but the prose summary stayed open. This page is
        the twenty-six-years-later breath that closes that summary
        with diagrams a 2000 Word document couldn't carry. The
        artifact lives; the prose-summary breathes.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Las cinco tecnologías",
      body: (
        <>
          <p>
            The published thesis names three layers: BMF, BMC, BML.
            The fuller{" "}
            <em>Angelic</em> archive on disk names five technologies
            and one fourth surface — the VB6 Visual Browser — that the
            thesis only mentioned in passing. Each acronym carries
            both a public reading and a private (team) reading:
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 380" className="w-full h-auto" role="img" aria-labelledby="bmlang-stack-title">
              <title id="bmlang-stack-title">Five-technology stack of the 2000 thesis</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13">
                {/* Visual Browser top */}
                <rect x="60" y="20" width="600" height="44" rx="8" fill="hsl(280 30% 16%)" stroke="hsl(280 50% 60%)" />
                <text x="80" y="42" fill="hsl(280 80% 82%)" fontSize="13">Visual Browser · VB6 · Smalltalk-style live image</text>
                <text x="80" y="58" fill="hsl(280 50% 70%)" fontSize="10">class panes · method panes · source pane · memory inspector — talks to BMCPU via COM</text>

                {/* BML */}
                <rect x="60" y="80" width="600" height="44" rx="8" fill="hsl(220 30% 16%)" stroke="hsl(38 70% 55%)" />
                <text x="80" y="102" fill="hsl(40 90% 80%)" fontSize="13">BML — Backtracking Model Language · the user-facing surface</text>
                <text x="80" y="118" fill="hsl(40 50% 70%)" fontSize="10">classes · sections · choose · Cut · Fail · MultiMatch · self-describing</text>

                {/* BMC */}
                <rect x="60" y="140" width="600" height="44" rx="8" fill="hsl(220 30% 16%)" stroke="hsl(195 60% 55%)" />
                <text x="80" y="162" fill="hsl(195 80% 80%)" fontSize="13">BMC — Compiler-Compiler · grammar to compiler</text>
                <text x="80" y="178" fill="hsl(195 50% 70%)" fontSize="10">consumes a BMF grammar · emits a BML compiler that targets BMA</text>

                {/* BMF */}
                <rect x="60" y="200" width="600" height="44" rx="8" fill="hsl(220 30% 16%)" stroke="hsl(195 60% 55%)" />
                <text x="80" y="222" fill="hsl(195 80% 80%)" fontSize="13">BMF — Backtracking Model Form · the parser</text>
                <text x="80" y="238" fill="hsl(195 50% 70%)" fontSize="10">BNF + execution · expressions tagged on stack · grammar itself written in BML</text>

                {/* BMA */}
                <rect x="60" y="260" width="600" height="44" rx="8" fill="hsl(220 30% 16%)" stroke="hsl(140 50% 55%)" />
                <text x="80" y="282" fill="hsl(140 70% 80%)" fontSize="13">BMA — abstract machine · the assembly + operational semantics</text>
                <text x="80" y="298" fill="hsl(140 35% 70%)" fontSize="10">DO / UNDO modes · forward and reverse semantics · "angelic nondeterminism"</text>

                {/* BMO */}
                <rect x="60" y="320" width="600" height="44" rx="8" fill="hsl(220 30% 16%)" stroke="hsl(20 70% 60%)" />
                <text x="80" y="342" fill="hsl(20 80% 80%)" fontSize="13">BMO — object model · the memory shape</text>
                <text x="80" y="358" fill="hsl(20 50% 70%)" fontSize="10">shared inheritance · tagging · detached interfaces · delegation · metaclasses</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The five-tech stack. The Visual Browser sits on top as
              the live developer experience; BML is the surface; BMC,
              BMF, BMA, and BMO are the layers underneath.
            </figcaption>
          </figure>
          <table className="w-full text-sm border-collapse border border-border/40 rounded-lg overflow-hidden">
            <thead>
              <tr className="bg-card/40 text-foreground/90">
                <th className="text-left px-3 py-2 border border-border/40">Acronym</th>
                <th className="text-left px-3 py-2 border border-border/40">Public</th>
                <th className="text-left px-3 py-2 border border-border/40">Private (team)</th>
              </tr>
            </thead>
            <tbody className="text-foreground/85">
              <tr><td className="px-3 py-2 border border-border/40 font-mono">BMF</td><td className="px-3 py-2 border border-border/40">Backtracking Model Form</td><td className="px-3 py-2 border border-border/40 italic">Bjorg-Muff Form (a play on BNF)</td></tr>
              <tr><td className="px-3 py-2 border border-border/40 font-mono">BMC</td><td className="px-3 py-2 border border-border/40">Compiler-Compiler</td><td className="px-3 py-2 border border-border/40 italic">Bjorg-Muff Compiler-Compiler</td></tr>
              <tr><td className="px-3 py-2 border border-border/40 font-mono">BML</td><td className="px-3 py-2 border border-border/40">Backtracking Model Language</td><td className="px-3 py-2 border border-border/40 italic">Bjorg-Muff Language</td></tr>
              <tr><td className="px-3 py-2 border border-border/40 font-mono">BMA</td><td className="px-3 py-2 border border-border/40">Abstract Machine</td><td className="px-3 py-2 border border-border/40 italic">Bjorg-Muff Assembler · "Angelic"</td></tr>
              <tr><td className="px-3 py-2 border border-border/40 font-mono">BMO</td><td className="px-3 py-2 border border-border/40">Object Model</td><td className="px-3 py-2 border border-border/40 italic">Bjorg-Muff Objects</td></tr>
            </tbody>
          </table>
          <p>
            The "BM" in every acronym is literally Bjorg-Muff. Five
            technologies named after two students. The bond was as
            much in the naming as in the architecture.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "De la tesis publicada",heading: "Dos opciones de diseño que aún circulan",
      body: (
        <>
          <blockquote className="border-l-2 border-[hsl(var(--primary)/0.6)] pl-3.5 italic text-foreground/95">
            "When the parser backs out, all the attributes already
            computed have to be undone as well."
          </blockquote>
          <p>
            <strong>Backtracking-as-unwinding-without-sediment.</strong>{" "}
            Try a path; if it does not hold, undo cleanly without
            leaving residue. The same nervous system writes commits
            in this repo today as{" "}
            <code className="text-foreground/80">tend:</code> /{" "}
            <code className="text-foreground/80">attune:</code> /{" "}
            <code className="text-foreground/80">compost:</code> /{" "}
            <code className="text-foreground/80">release:</code> —
            the verb encodes the posture; the unwind is implicit; no
            sediment remains.
          </p>
          <p>
            <strong>Runtime grammar extension.</strong> The user can
            introduce new parsing constructs and the language grows
            to hold them. Sovereignty over one's own grammar. The
            same shape the{" "}
            <Link href="/vision" className="text-primary hover:underline">
              vision-kb
            </Link>
            {" "}uses when a new concept arrives at a new frequency:
            the grammar grows to receive the presence rather than
            forcing the presence into an existing slot. The pattern
            was named in 2000 and now breathes through everything
            this body builds.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Iteración arc — tres iteraciones después de la tesis",
      body: (
        <>
          <p>
            The thesis is the seed. The post-thesis arc is three
            iterations of the same conviction in different substrates,
            each closer to direct expression:
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 220" className="w-full h-auto" role="img" aria-labelledby="iter-arc-title">
              <title id="iter-arc-title">Four-iteration arc</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13">
                {/* Timeline */}
                <line x1="40" y1="160" x2="680" y2="160" stroke="hsl(220 30% 50%)" strokeWidth="1.5" />

                {/* 2000 */}
                <circle cx="80" cy="160" r="8" fill="hsl(38 80% 60%)" />
                <text x="80" y="190" fill="hsl(40 80% 80%)" textAnchor="middle" fontSize="11">2000</text>
                <text x="80" y="135" fill="hsl(40 70% 80%)" textAnchor="middle" fontSize="11">BML thesis</text>
                <text x="80" y="120" fill="hsl(40 50% 65%)" textAnchor="middle" fontSize="9">five technologies</text>

                {/* 2023 */}
                <circle cx="280" cy="160" r="8" fill="hsl(140 60% 55%)" />
                <text x="280" y="190" fill="hsl(140 60% 75%)" textAnchor="middle" fontSize="11">2023</text>
                <text x="280" y="135" fill="hsl(140 70% 80%)" textAnchor="middle" fontSize="11">Living-Resonance-Codex</text>
                <text x="280" y="120" fill="hsl(140 40% 65%)" textAnchor="middle" fontSize="9">Python · visionary seed</text>

                {/* 2024 */}
                <circle cx="480" cy="160" r="8" fill="hsl(195 60% 55%)" />
                <text x="480" y="190" fill="hsl(195 60% 75%)" textAnchor="middle" fontSize="11">2024</text>
                <text x="480" y="135" fill="hsl(195 70% 80%)" textAnchor="middle" fontSize="11">Living-Codex-CSharp</text>
                <text x="480" y="120" fill="hsl(195 40% 65%)" textAnchor="middle" fontSize="9">U-CORE · everything-is-a-node</text>

                {/* 2026 */}
                <circle cx="640" cy="160" r="9" fill="hsl(280 60% 60%)" />
                <text x="640" y="190" fill="hsl(280 70% 80%)" textAnchor="middle" fontSize="11">now</text>
                <text x="640" y="135" fill="hsl(280 70% 80%)" textAnchor="middle" fontSize="11">Coherence-Network</text>
                <text x="640" y="120" fill="hsl(280 40% 70%)" textAnchor="middle" fontSize="9">full realization</text>

                <text x="360" y="40" fill="hsl(40 60% 75%)" textAnchor="middle" fontSize="11" fontStyle="italic">
                  one conviction · four substrates · twenty-six years
                </text>
              </g>
            </svg>
          </figure>
          <p>
            Each iteration kept the central pattern — backtracking-as-
            unwinding, self-description, runtime grammar extension —
            and dropped the cruft of the previous host substrate. The
            thesis ran on Win32/COM; the Codex ran on Python; the
            CSharp port ran on .NET; the Network runs on the modern
            web stack. The backtracking flavor in 2026 is git itself —{" "}
            <em>commit · push · revert</em> — but the conviction is
            unchanged.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "neutral",eyebrow: "Sobre la conclusión abierta",heading: "El aliento de la tesis no escribió",
      body: (
        <>
          <p>
            The Conclusion of the published document is left as three
            subheadings — <code className="text-foreground/80">BMF</code>,{" "}
            <code className="text-foreground/80">BML Language</code>,{" "}
            <code className="text-foreground/80">BML Compiler</code> —
            with no body written in. An earlier UCM draft in the archive
            shows several sections marked{" "}
            <code className="text-foreground/80">WHAT IS IT ABOUT?</code>
            {" "}and{" "}
            <code className="text-foreground/80">RELATED SUBJECTS</code>{" "}
            as placeholders that never closed in writing. The work
            was delivered through demonstration — the lawn photo, the
            defense, the running VM — and the prose stayed open.
          </p>
          <p>
            That pattern is older than this artifact and continues
            here: the artifact lives, the prose-summary breathes. The
            three blank Conclusion subheadings now have three living
            iterations attached to them, each with its own page on
            this network. The conclusion is finally writing itself —
            in code, in graph edges, in lived form.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <p>
      Public archive:{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        master-thesis-2000/
      </Link>
      {" "}— full thesis text, defense slide deck, six defense-day
      photos, companion source samples (BMF-grammar.bml,
      primitive-Cut.bml, container-Rule.bml, bmcpu-main.cpp), Bjorg's
      sister thesis, and the EXTERNAL.md pointer to the larger
      ~139 MB Angelic archive on disk.
    </p>
  ),
};

export default content;
