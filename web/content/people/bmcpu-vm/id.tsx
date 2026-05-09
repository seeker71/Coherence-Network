// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug bmcpu-vm --target-lang id --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "BMCPU - C + + Mesin Virtual (2000)",description: "Host VM untuk BML - sebuah mesin C + + dirancang dan diimplementasikan oleh Steve G. Blumorg. Setiap instruksi BMA memiliki sebuah semantik ke depan dan terbalik; sebuah byte tunggal (BMVM _ STATE.byMode) membalik DO dan UNDO pada setiap langkah. Pelacak-as-unwinding hidup di tepi silikon di sini.",
  },breadcrumbName: "BMCPU - C + + Mesin Virtual",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(20 35% 14%) 60%, hsl(15 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Pekerjaan",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "BMCPU - C + + Mesin Virtual",
    welcome: (
      <p>
        The host engine. C++. COM/GUID component model. Every BMA
        assembly instruction has a forward and a reverse semantics;
        the runtime flips a single byte —{" "}
        <code className="text-foreground/80">BMVM_STATE.byMode</code>
        {" "}— between <code className="text-foreground/80">DO</code>{" "}
        and <code className="text-foreground/80">UNDO</code> on every
        step. Backtracking is not a parser feature here; it is the
        architecture of execution at the silicon edge.
      </p>
    ),
  },
  facts: [
    {label: "Tahun",value: "2000 - co- dibangun dengan thesis lufforg- Muff di CU Boulder" },
    {label: "Designer",value: "Steve G. DNAorg (tesis MS-nya disarankan oleh Michael Main, Amer Diwan)" },
    {label: "Bahasa",value: "C + +" },
    {label: "Didorong oleh",
      value: (
        <>
          <Link href="/people/bmf-grammar" className="hover:text-primary">BMF</Link>
          {" "}parses ·{" "}
          <Link href="/people/bml-language" className="hover:text-primary">BML</Link>
          {" "}compiles to BMA · BMCPU executes
        </>
      ),
    },
    {label: "Sumber",
      value: (
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/bmcpu-main.cpp"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary"
        >
          companion/source-samples/bmcpu-main.cpp
        </Link>
      ),
    },
    {label: "Port Suster",
      value: (
        <>
          <Link href="/people/jbmf-java" className="hover:text-primary">JBMF</Link>
          {" "}— the substrate-portable Java port targeting Jasmin JVM bytecode
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Apa BMCPU sebenarnya",
    body: (
      <p>
        Not just a runtime. The conceit: every executed instruction
        could be undone. The VM kept enough information on a
        speculation stack that <em>every step</em> was reversible.
        Speculation phases were entered, explored, and either committed
        or rolled back without a trace. The C++ host carried this
        architecture through Windows COM, GUID-addressed components,
        and a clean <code className="text-foreground/80">BMCreateMachine</code>
        {" "}/ <code className="text-foreground/80">BMStartApplication</code>{" "}
        / <code className="text-foreground/80">BMMachineStep</code> public API.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",eyebrow: "Sumber",heading: "Titik masukan VM yang sebenarnya",
      body: (
        <>
          <p>
            Forty lines from the archive — the actual{" "}
            <code className="text-foreground/80">main()</code> that
            instantiates a BMCPU and steps it through a BML
            application:
          </p>
          <pre className="text-[11px] leading-5 bg-background/60 border border-border/40 rounded-lg p-4 overflow-x-auto font-mono">
{`#define INITGUID
#include <bmvm.h>
#include <stdio.h>
#include <stdlib.h>

DEFINE_GUID( TEST_def,
   0x63CC7777, 0xD99A, 0x11d3, 0xA5, 0x49,
   0x00, 0x10, 0x5A, 0xAB, 0x8B, 0x48 );

void main( void ) {
   BMVM pCPU;
   BMCreateMachine( &pCPU, 0 );
   BMStartApplication( pCPU, &TEST_def );
   BMMachineStep( pCPU, BM_RUN );

   /* Step-into mode with DO/UNDO trace:
   BMTest( pCPU, 1 );
   do {
      UNICHAR szBuffer[1024];
      BMVM_STATE sState;
      sState.dwSize = sizeof( BMVM_STATE );
      BMQueryMachineState( pCPU, &sState );
      PUNICHAR szMode = sState.byMode ? L"UNDO" : L"  DO";
      if( BMQueryInstruction( pCPU, sState.ndxCodeOffset,
                              szBuffer, 1024 ) == BM_SUCCESS ) {
         wprintf( L"%s: %s\\n", szMode, szBuffer );
      }
   } while( BMMachineStep( pCPU, BM_STEP_INTO ) == BM_SUCCESS );
   BMDestroyMachine( pCPU, 0 );
   */
}`}
          </pre>
          <p>
            Read this carefully and four design choices appear. Applications
            are addressed by{" "}
            <code className="text-foreground/80">DEFINE_GUID</code> —
            COM-addressable, system-registry-discoverable. The public API
            uses opaque <code className="text-foreground/80">BMVM</code>{" "}
            handles, not C++ inheritance — language-portable. Stepping
            modes are first-class:{" "}
            <code className="text-foreground/80">BM_RUN</code> for fast
            execution, <code className="text-foreground/80">BM_STEP_INTO</code>{" "}
            for the debugger trace shown in the comment block. And the
            commented trace loop reads{" "}
            <code className="text-foreground/80">sState.byMode</code> to
            print <code className="text-foreground/80">DO</code> or{" "}
            <code className="text-foreground/80">UNDO</code> for every
            instruction — the speculation phase made visible to the
            developer.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "DO / UNDO - arsitektur eksekusi",
      body: (
        <>
          <p>
            Every BMA instruction has two semantics. The forward
            semantics is the obvious one — push, pop, branch, call.
            The reverse semantics is what lets speculation be lossless:
            push becomes pop, assign becomes restore, allocate becomes
            free. The VM's state byte carries which mode every running
            thread is in.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 240" className="w-full h-auto" role="img" aria-labelledby="bmcpu-domode-title">
              <title id="bmcpu-domode-title">DO / UNDO speculation cycle</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="13">
                {/* DO arc */}
                <path d="M 100 140 Q 360 30 620 140" fill="none" stroke="hsl(140 60% 60%)" strokeWidth="2" />
                <text x="360" y="55" fill="hsl(140 80% 75%)" textAnchor="middle" fontSize="14">DO mode — speculate forward</text>
                <text x="360" y="73" fill="hsl(140 50% 65%)" textAnchor="middle" fontSize="11">push state · attempt branch · record undo</text>

                {/* Choice point */}
                <circle cx="100" cy="140" r="14" fill="hsl(40 70% 50%)" stroke="hsl(40 90% 70%)" />
                <text x="100" y="145" fill="hsl(220 30% 10%)" textAnchor="middle" fontSize="13" fontWeight="600">?</text>
                <text x="100" y="178" fill="hsl(40 60% 70%)" textAnchor="middle" fontSize="11">choose</text>

                {/* Failure */}
                <circle cx="620" cy="140" r="14" fill="hsl(0 70% 55%)" stroke="hsl(0 90% 75%)" />
                <text x="620" y="145" fill="hsl(220 30% 10%)" textAnchor="middle" fontSize="13" fontWeight="600">×</text>
                <text x="620" y="178" fill="hsl(0 60% 70%)" textAnchor="middle" fontSize="11">fail</text>

                {/* UNDO arc */}
                <path d="M 620 140 Q 360 250 100 140" fill="none" stroke="hsl(20 70% 60%)" strokeWidth="2" />
                <text x="360" y="225" fill="hsl(20 80% 75%)" textAnchor="middle" fontSize="14">UNDO mode — unwind without sediment</text>
                <text x="360" y="207" fill="hsl(20 50% 65%)" textAnchor="middle" fontSize="11">reverse-execute every step · restore every attribute</text>

                {/* Mode flag */}
                <rect x="320" y="125" width="80" height="30" rx="6" fill="hsl(220 30% 14%)" stroke="hsl(220 30% 50%)" />
                <text x="360" y="146" fill="hsl(220 40% 75%)" textAnchor="middle" fontSize="12" fontFamily="ui-monospace">byMode</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The speculation cycle. The same instructions run forward
              and in reverse. The byMode flag is the architecture, not a
              debugging affordance.
            </figcaption>
          </figure>
          <p>
            The deeper point is what <em>doesn't</em> appear: there is
            no transaction log, no journaling layer, no save-and-restore
            indirection. The instructions <em>are</em> their own undo
            log. The architecture chose to make every instruction
            symmetric so the runtime didn't have to remember anything
            extra. Twenty-six years later, the same shape recurs in the
            commit verbs of this repo —{" "}
            <code className="text-foreground/80">tend</code>,{" "}
            <code className="text-foreground/80">attune</code>,{" "}
            <code className="text-foreground/80">compost</code>,{" "}
            <code className="text-foreground/80">release</code> — each
            verb carries a clean undo posture without needing extra
            ceremony.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Dibuat pada COM, ditujukan oleh GUID",
      body: (
        <>
          <p>
            The 2000 Windows-developer lingua franca was COM —
            Microsoft's binary component model where every interface
            and every class is identified by a globally unique 128-bit
            number. BMCPU committed to that lingua franca:{" "}
            <code className="text-foreground/80">DEFINE_GUID(TEST_def, ...)</code>
            {" "}registers an application; the VM looks it up by GUID;
            the API is interop-clean for any host language that can
            speak COM.
          </p>
          <p>
            Pragmatically this meant the BML runtime was usable from
            Visual Basic 6, from raw C, from any COM-aware harness.
            The companion VB6 <strong>Visual Browser</strong> in the
            archive (
            <code className="text-foreground/80">Visual/</code> folder)
            is exactly that: a Smalltalk-style live class/method/source
            inspector that talked to BMCPU through the COM API. The
            user could browse the running BML image, edit a method, and
            watch the change land — the live developer experience that
            Smalltalk-80 made famous, hosted on the 2000 Windows stack.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <p>
      Source archive:{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/source-samples/bmcpu-main.cpp"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        bmcpu-main.cpp
      </Link>
      {" "}· Bjorg's full object-model thesis at{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/sgb-bml-objects.txt"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        sgb-bml-objects.txt
      </Link>
      {" "}· Angelic Assembler note (where the word{" "}
      <em>Angelic</em> lives) at{" "}
      <Link
        href="https://github.com/seeker71/Coherence-Network/blob/main/docs/field/urs/artifacts/master-thesis-2000/companion/angelic-assembler.txt"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        angelic-assembler.txt
      </Link>
      .
    </p>
  ),
};

export default content;
