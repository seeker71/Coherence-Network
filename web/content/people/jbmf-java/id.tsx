// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug jbmf-java --target-lang id --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "JBMF - Port BMF Java (2000)",description: "Penerapan kedua dari BMF - port Java menargetkan Jasmin JVM bytecode. Panji Kompailer JBMF (R) muncul pada bagian atas dari setiap contoh sumber BML dalam arsip: sistem ini sudah dibooton melalui Java pada saat berkas-berkas tersebut ditulis.",
  },breadcrumbName: "JBMF - Java BMF Port",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(195 40% 14%) 60%, hsl(140 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Pekerjaan",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "JBMF - Java BMF Port",
    welcome: (
      <p>
        The Java port of <Link href="/people/bmf-grammar" className="text-primary hover:underline">BMF</Link>
        {" "}— second implementation of the parser, targeting the JVM
        instead of native C++. Compiles to{" "}
        <Link href="https://en.wikipedia.org/wiki/Jasmin_(software)" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          Jasmin
        </Link>
        {" "}JVM assembly. Every BML source file in the archive carries{" "}
        <code className="text-foreground/80">Compiler: JBMF (R) Compiler</code>
        {" "}in its header — by the time those files were typed, the
        system was already bootstrapping itself through Java.
      </p>
    ),
  },
  facts: [
    {label: "Tahun",value: "2000" },
    {label: "Substrat",value: "Java" },
    {label: "Suster VM",
      value: (
        <>
          <Link href="/people/bmcpu-vm" className="hover:text-primary">BMCPU</Link>
          {" "}— the C++/COM Win32 host. Same parser; different substrate.
        </>
      ),
    },
    {label: "Drives",
      value: (
        <>
          Compiles{" "}
          <Link href="/people/bml-language" className="hover:text-primary">BML</Link>
          {" "}source to executable artifacts on the JVM. Header banner
          on every <code className="text-foreground/80">.bml</code> file.
        </>
      ),
    },
    {label: "Ancetri",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/Jasmin_(software)" target="_blank" rel="noopener noreferrer" className="hover:text-primary">
            Jasmin
          </Link>
          {" "}— the JVM-bytecode assembler that made it tractable to
          generate verifier-clean class files in 2000.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Mengapa pelabuhan kedua penting",
    body: (
      <p>
        A language with one implementation is a project. A language
        with two implementations on different substrates is{" "}
        <em>portable architecture</em>. JBMF demonstrated that BML's
        semantics — including the speculation, the choose-and-undo,
        the four-ancestor synthesis — translated cleanly across
        substrates. Same parser, different VM. Same source files,
        same banner, different runtime.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Dua substles, satu parser",
      body: (
        <>
          <p>
            BMF's grammar is described in BML; the parser itself can
            be implemented anywhere there's a host language. The 2000
            project shipped two: one in C++ (
            <Link href="/people/bmcpu-vm" className="text-primary hover:underline">
              BMCPU
            </Link>
            ) targeting Win32 + COM, and one in Java (JBMF) targeting
            the JVM. The grammar source file{" "}
            <code className="text-foreground/80">BMF-grammar.bml</code>{" "}
            was the same for both.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 240" className="w-full h-auto" role="img" aria-labelledby="jbmf-substrates-title">
              <title id="jbmf-substrates-title">JBMF / BMCPU substrate split</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13">
                {/* Top: shared source */}
                <rect x="240" y="20" width="240" height="50" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(38 70% 55%)" />
                <text x="360" y="42" fill="hsl(40 90% 80%)" textAnchor="middle" fontSize="14">.bml source files</text>
                <text x="360" y="60" fill="hsl(40 50% 70%)" textAnchor="middle" fontSize="11">single grammar · single AST · single semantics</text>

                {/* Branches down */}
                <line x1="320" y1="70" x2="180" y2="120" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />
                <line x1="400" y1="70" x2="540" y2="120" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />

                {/* Left: BMCPU C++ */}
                <rect x="60" y="120" width="240" height="80" rx="10" fill="hsl(220 25% 16%)" stroke="hsl(20 70% 60%)" />
                <text x="180" y="146" fill="hsl(20 80% 80%)" textAnchor="middle" fontSize="14">BMCPU</text>
                <text x="180" y="166" fill="hsl(20 60% 75%)" textAnchor="middle" fontSize="11">C++ · Win32 · COM</text>
                <text x="180" y="184" fill="hsl(20 40% 65%)" textAnchor="middle" fontSize="10">DEFINE_GUID · BMVM_STATE.byMode</text>

                {/* Right: JBMF Java */}
                <rect x="420" y="120" width="240" height="80" rx="10" fill="hsl(220 25% 16%)" stroke="hsl(140 50% 55%)" />
                <text x="540" y="146" fill="hsl(140 70% 80%)" textAnchor="middle" fontSize="14">JBMF</text>
                <text x="540" y="166" fill="hsl(140 50% 75%)" textAnchor="middle" fontSize="11">Java · Jasmin JVM bytecode</text>
                <text x="540" y="184" fill="hsl(140 35% 65%)" textAnchor="middle" fontSize="10">substrate-portable · cross-OS</text>

                <text x="360" y="225" fill="hsl(220 30% 65%)" textAnchor="middle" fontSize="11" fontStyle="italic">
                  one BMF · two substrates · same speculation semantics
                </text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The two-implementation pattern. The grammar lives once;
              the host substrate is a port concern.
            </figcaption>
          </figure>
          <p>
            The same conviction shows up across the network now. The
            Coherence Network's API speaks JSON over HTTP; clients are
            web (TypeScript), CLI (Node + Python wrapper), and direct
            graph access (Cypher). The interface is the contract; the
            host substrate is incidental. JBMF was the first time that
            posture was load-bearing in a system this body shipped.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Banner",heading: "Kompailer JBMF (R)",
      body: (
        <>
          <p>
            Open any{" "}
            <code className="text-foreground/80">.bml</code> file in{" "}
            <code className="text-foreground/80">companion/source-samples/</code>{" "}
            and the eight-line header is the same:
          </p>
          <pre className="text-[11px] leading-5 bg-background/60 border border-border/40 rounded-lg p-4 overflow-x-auto font-mono">
{`// Name:     Cut.bml
// Author:   Urs C. Muff
// Email:    muff@colorado.edu
// Date:     11-Apr-2000
// Platform: BML Virtual Machine
// Compiler: JBMF (R) Compiler`}
          </pre>
          <p>
            <code className="text-foreground/80">Platform: BML Virtual Machine</code>
            {" "}and{" "}
            <code className="text-foreground/80">Compiler: JBMF (R) Compiler</code>
            {" "}— the file announces what runtime expects it and what
            compiler produced its bytecode. By April 2000 (the date on
            the Cut primitive) the system was self-aware enough to
            stamp every source file with its compilation lineage.
            That's the maturity-mark of a working language: the
            banner stops being aspirational and starts being a fact.
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
      . The JBMF.exe binary itself lives in the larger 139 MB Angelic
      archive (off-repo, on disk) — see{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/EXTERNAL.md"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        EXTERNAL.md
      </Link>
      {" "}for the cluster map.
    </p>
  ),
};

export default content;
