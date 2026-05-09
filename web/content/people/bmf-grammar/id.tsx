// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug bmf-grammar --target-lang id --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "BMF - Bentuk Model Backtracking (2000)",description: "Lapisan parser tesis 2000 Gluorg- Muff. BNF ditambah dengan elemen eksekusi: ketika aturan cocok, kode kebakaran. Tata bahasa itu sendiri dapat dieksekusi BML - sistem menjelaskan tata bahasa sendiri dalam bahasanya sendiri.",
  },breadcrumbName: "BMF - Bentuk Model Backtracking",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(195 35% 14%) 60%, hsl(180 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Bekerja",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "BMF - Bentuk Model Backtracking",
    welcome: (
      <p>
        BNF augmented with execution. When a rule matches, code fires.
        Expressions are tagged and placed on a structured stack each
        rule transforms into the target language's object model. The
        grammar file <code className="text-foreground/80">BMF-grammar.bml</code>{" "}
        is itself written in <Link href="/people/bml-language" className="text-primary hover:underline">BML</Link>
        {" "}— banner reads <code className="text-foreground/80">Digi4Fun (R) BMF 1.0 Alpha 1</code>.
      </p>
    ),
  },
  facts: [
    {label: "Tahun",value: "2000" },
    {label: "Implementasi",value: "C + + top-down recursive- turunan parser dengan backtracking stack" },
    {label: "Grammar",
      value: (
        <>
          Self-describing — the grammar of BMF is written in{" "}
          <Link href="/people/bml-language" className="hover:text-primary">BML</Link>
          {" "}(see <code className="text-foreground/80">companion/source-samples/BMF-grammar.bml</code> in the archive)
        </>
      ),
    },
    {label: "Trio",
      value: (
        <>
          BMF (parser) · BMA (
          <Link href="/people/bmcpu-vm" className="hover:text-primary">assembler / BMCPU</Link>
          ) · BMO (object model) — the three-tech split named in
          <code className="text-foreground/80"> bml-search-algorithms.txt</code>
        </>
      ),
    },
    {label: "Ancetri",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/Backus%E2%80%93Naur_form" target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            BNF
          </Link>
          {" "}(Backus 1959 · Naur 1960) · executable grammar concept anticipated yacc/bison
        </>
      ),
    },
    {label: "Arsip Publik",
      value: (
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/BMF-grammar.bml"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary"
        >
          companion/source-samples/BMF-grammar.bml
        </Link>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Apa sebenarnya BMF",
    body: (
      <p>
        Parser is the first noun. <em>Executable grammar</em> is the
        second. BMF rules don't <em>describe</em> a parse tree — they{" "}
        <em>build</em> one as they go, with code firing on every
        successful match and a stack standing ready to undo every
        side effect on failure. The grammar is alive at parse time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "BMF / BMA / BMO - pembagian tiga-tech",
      body: (
        <>
          <p>
            The applied paper{" "}
            <code className="text-foreground/80">bml-search-algorithms.txt</code>
            {" "}names the three-tech split that holds the system together.
            Each technology owns one altitude:
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 220" className="w-full h-auto" role="img" aria-labelledby="bmf-trio-title">
              <title id="bmf-trio-title">BMF / BMA / BMO trio</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13">
                <g>
                  <rect x="40" y="60" width="180" height="100" rx="12" fill="hsl(195 30% 18%)" stroke="hsl(195 60% 55%)" />
                  <text x="130" y="92" fill="hsl(195 80% 80%)" fontSize="15" textAnchor="middle">BMF</text>
                  <text x="130" y="112" fill="hsl(195 60% 70%)" fontSize="11" textAnchor="middle">parser · grammar</text>
                  <text x="130" y="128" fill="hsl(195 40% 65%)" fontSize="10" textAnchor="middle">"how do I read this?"</text>
                  <text x="130" y="144" fill="hsl(195 40% 65%)" fontSize="10" textAnchor="middle">choose · backtrack</text>
                </g>
                <g>
                  <rect x="270" y="60" width="180" height="100" rx="12" fill="hsl(35 30% 18%)" stroke="hsl(38 70% 55%)" />
                  <text x="360" y="92" fill="hsl(40 90% 80%)" fontSize="15" textAnchor="middle">BMA</text>
                  <text x="360" y="112" fill="hsl(40 60% 70%)" fontSize="11" textAnchor="middle">assembly · execution</text>
                  <text x="360" y="128" fill="hsl(40 40% 65%)" fontSize="10" textAnchor="middle">"how do I run this?"</text>
                  <text x="360" y="144" fill="hsl(40 40% 65%)" fontSize="10" textAnchor="middle">DO · UNDO modes</text>
                </g>
                <g>
                  <rect x="500" y="60" width="180" height="100" rx="12" fill="hsl(280 30% 18%)" stroke="hsl(280 50% 60%)" />
                  <text x="590" y="92" fill="hsl(280 80% 82%)" fontSize="15" textAnchor="middle">BMO</text>
                  <text x="590" y="112" fill="hsl(280 60% 75%)" fontSize="11" textAnchor="middle">objects · memory</text>
                  <text x="590" y="128" fill="hsl(280 40% 70%)" fontSize="10" textAnchor="middle">"what holds state?"</text>
                  <text x="590" y="144" fill="hsl(280 40% 70%)" fontSize="10" textAnchor="middle">tagging · delegation</text>
                </g>
                {/* Connecting lines */}
                <line x1="220" y1="110" x2="270" y2="110" stroke="hsl(220 30% 60%)" strokeWidth="1.5" strokeDasharray="3,3" />
                <line x1="450" y1="110" x2="500" y2="110" stroke="hsl(220 30% 60%)" strokeWidth="1.5" strokeDasharray="3,3" />
                <text x="360" y="195" fill="hsl(220 25% 65%)" fontSize="11" textAnchor="middle" fontStyle="italic">
                  three nouns, one breath: read · run · hold
                </text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The BMF/BMA/BMO trio. Read, run, hold — three nouns, one
              breath. The parser fires code that emits assembly that
              instantiates objects.
            </figcaption>
          </figure>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Sumber header BMF.bml",heading: "Tata bahasa menyatakan dirinya di BML",
      body: (
        <>
          <p>
            Here is the actual top of{" "}
            <code className="text-foreground/80">BMF-grammar.bml</code>{" "}
            from the 2000 archive — the file that defines the BMF
            grammar in BML:
          </p>
          <pre className="text-[11px] leading-5 bg-background/60 border border-border/40 rounded-lg p-4 overflow-x-auto font-mono">
{`// Name:     BMF.bml
// Author:   Urs C. Muff
// Date:     11-Apr-2000
// Platform: BML Virtual Machine
// Compiler: JBMF (R) Compiler

package BMF;
import BMF.primitive.*;

class BMF [public] : Application {
   const String DefaultBMFSyntax = "BMF.library.BMF";

   section [class, public] {
      String m_strDefaultConfigFile = "BMF.cfg";
      String m_strConfigFile = m_strDefaultConfigFile;
   }

   section [class, public] {
      bool m_bDebug = true;
   }

   section [public] {
      void Main( String[] hArgs ) { HandleArgs( hArgs ); }
   }
}`}
          </pre>
          <p>
            <code className="text-foreground/80">class BMF [public] : Application</code>
            {" "}— BMF is a class in BML, inheriting from{" "}
            <code className="text-foreground/80">Application</code>.{" "}
            <code className="text-foreground/80">section [class, public]</code>{" "}
            is Smalltalk-style category-pane visibility expressed as
            BML syntax. The compiler that compiled this file is named
            in the header: <code className="text-foreground/80">JBMF (R)</code>
            {" "}— the{" "}
            <Link href="/people/jbmf-java" className="text-primary hover:underline">
              Java port
            </Link>
            . The system was already self-bootstrapped at the moment
            this comment was typed.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Pilih, backtrack, batalkan",
      body: (
        <>
          <p>
            BMF rules are not pure recognizers. Each rule's right-hand
            side carries action code that fires on a match. Expressions
            on the parse stack are tagged so an action can lift the
            value of any subexpression by name. When a rule fails
            mid-way through — say, the third alternative of a{" "}
            <code className="text-foreground/80">choose</code>{" "}
            block doesn't match — the runtime walks back through every
            tagged stack entry and{" "}
            <strong>undoes the side effects each action introduced</strong>
            , then tries the next alternative.
          </p>
          <p>
            The same shape recurs three times in the system. At the
            parser level it's grammar backtracking. At the BMA
            (
            <Link href="/people/bmcpu-vm" className="text-primary hover:underline">
              BMCPU
            </Link>
            ) level it's the <code className="text-foreground/80">DO</code>/
            <code className="text-foreground/80">UNDO</code> mode flag —
            every assembly instruction has a forward and a reverse
            semantics. At the language level (
            <Link href="/people/bml-language" className="text-primary hover:underline">
              BML
            </Link>
            ) it's <code className="text-foreground/80">choose</code> /{" "}
            <code className="text-foreground/80">Cut</code> /{" "}
            <code className="text-foreground/80">Fail</code> /{" "}
            <code className="text-foreground/80">MultiMatch</code>.{" "}
            The unwinding pattern threads through every layer.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Nama permainan BNF",heading: "Bentuk Muff",
      body: (
        <p>
          The acronym is a deliberate pun. <strong>BMF</strong> reads
          publicly as Backtracking Model Form; reads privately, in the
          team, as <em>Bjorg-Muff Form</em>, with the same cadence as{" "}
          BNF (Backus-Naur Form). Backus and Naur described grammars
          that machines could parse; Bjorg and Muff described grammars
          that machines could parse <em>and</em> execute <em>and</em>{" "}
          undo. Same prefix, one octave up.
        </p>
      ),
    },
  ],
  footer: (
    <p>
      Source archive:{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/tree/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        master-thesis-2000/companion/source-samples/
      </Link>
      {" "}— BMF-grammar.bml, BMF-includes.bml, container-Rule.bml,
      primitive-Cut.bml. The published thesis lives one folder up at{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/backtracking-model-languages.txt"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        backtracking-model-languages.txt
      </Link>
      .
    </p>
  ),
};

export default content;
