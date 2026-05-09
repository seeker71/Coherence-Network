// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug qualcomm-test-automation --target-lang de --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Qualcomm Test Automation System (2009-2022)",description: "Zwölf Jahre bei Qualcomm Boulder. Das Test-Automation-System startete in der Windows-Division, setzte sich in der Graphics-Division fort und wurde für die Server-Division in C# vollständig neu geschrieben – in der Lage, jeden Testfall als C#-Skript zu führen, der dynamisch zur Laufzeit kompiliert wurde. Drei Divisionen, drei Iterationen einer Überzeugung: Tests als erstklassiger kompilierter Code, nicht datengesteuerte Läufer.",
  },breadcrumbName: "Qualcomm Test Automation",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(220 35% 14%) 50%, hsl(20 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Arbeit · Qualcomm · Boulder · Okt 2009 – Jan 2022 · Senior Staff Engineer",
    eyebrowClass: "text-[hsl(var(--primary))]",name: "Qualcomm Test Automation System",
    welcome: (
      <p>
        Twelve years and four months at Qualcomm Boulder. The
        test-automation system was started in the{" "}
        <strong>Windows division</strong>, continued and broadened in
        the <strong>Graphics division</strong>, and then{" "}
        <em>completely rewritten</em> for the{" "}
        <strong>Server division</strong> in C# — running any test
        case authored as a C# script, dynamically compiled at run
        time. Three divisions, three iterations, one conviction:{" "}
        <em>tests as first-class compiled code, not parameter-driven
        runners</em>.
      </p>
    ),
  },
  facts: [
    {label: "Er",value: "Qualcomm · Boulder, Colorado · Okt 2009 – Jan 2022 · 12 Jahre 4 Monate · Senior Staff Engineer" },
    {label: "Substrat (Ende iteration)",value: "C# · .NET · CSharpCodeProvider / Roslyn-era dynamische Compilation · CLR Laufzeit" },
    {label: "Drei Abteilungen",
      value: (
        <>
          Windows division (initial system) · Graphics division
          (continued evolution) · Server division (complete rewrite
          in C#)
        </>
      ),
    },
    {label: "Abweichung",
      value: (
        <>
          Tests as <em>scripts that compile</em> — not configuration
          files, not parameterised templates. A test case was a real
          C# program with the full language surface available; the
          framework loaded it, compiled it in-process, executed it
          against the system under test, and reported.
        </>
      ),
    },
    {label: "Zurück zur Übersicht",
      value: (
        <>
          Same conviction as the{" "}
          <Link href="/people/jbmf-java" className="hover:text-primary">
            JBMF
          </Link>
          {" "}port (2000) — substrate-portable dynamic compilation
          where source becomes runnable bytecode in-process. And same
          posture as the{" "}
          <Link href="/people/quark-multi-undo-redo" className="hover:text-primary">
            Quark multi-undo/redo engine
          </Link>
          : every action a first-class object, addressable, replayable.
        </>
      ),
    },
    {label: "Linie nach vorne",
      value: (
        <>
          The dynamic-compilation primitive matured here is the same
          shape the{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">
            Coherence-Network
          </Link>
          's spec-to-task pipeline now uses: a spec is a structured
          program agents (Claude · Codex · Cursor) execute as code,
          not as a checklist.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Warum das hier ist",
    body: (
      <p>
        Qualcomm Boulder was the longest single tenure of this body's
        career — twelve years and change, the years when Karl May and
        Cooper were on the bedside, when audiobook listening hours
        were climbing into the thousands, when 5Rhythms entered the
        rotation, when Mile Hi years had ripened into daily practice.
        The test-automation system was the load-bearing technical
        thread underneath. Three divisions, three rewrites, one
        conviction that proved itself across every substrate it
        touched.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Drei Abteilungen, drei Iterationen",
      body: (
        <>
          <p>
            Qualcomm is structured by division. Each division has its
            own product line, its own rhythm, its own kinds of test
            problem. The test-automation system carried forward
            across three of them, and each carry was a chance to ask
            "what did the previous version not yet name?" and answer
            it in code.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 280" className="w-full h-auto" role="img" aria-labelledby="qc-evolution-title">
              <title id="qc-evolution-title">Three-division evolution of the Qualcomm test-automation system</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* Timeline */}
                <line x1="60" y1="240" x2="660" y2="240" stroke="hsl(220 30% 50%)" strokeWidth="1.5" />

                {/* Windows division — early */}
                <g>
                  <rect x="80" y="80" width="170" height="120" rx="12" fill="hsl(220 30% 18%)" stroke="hsl(195 60% 60%)" />
                  <text x="165" y="106" fill="hsl(195 80% 82%)" fontSize="13" textAnchor="middle">Windows division</text>
                  <text x="165" y="124" fill="hsl(195 50% 72%)" fontSize="10" textAnchor="middle">first iteration · started</text>
                  <text x="95" y="148" fill="hsl(195 40% 75%)" fontSize="10">· UI test surface</text>
                  <text x="95" y="164" fill="hsl(195 40% 75%)" fontSize="10">· Win32 / driver bring-up</text>
                  <text x="95" y="180" fill="hsl(195 40% 75%)" fontSize="10">· naming the primitives</text>
                  <circle cx="165" cy="240" r="6" fill="hsl(195 70% 60%)" />
                </g>

                {/* Graphics division — middle */}
                <g>
                  <rect x="280" y="55" width="170" height="145" rx="12" fill="hsl(220 30% 18%)" stroke="hsl(280 55% 65%)" />
                  <text x="365" y="80" fill="hsl(280 80% 82%)" fontSize="13" textAnchor="middle">Graphics division</text>
                  <text x="365" y="98" fill="hsl(280 50% 72%)" fontSize="10" textAnchor="middle">second iteration · continued</text>
                  <text x="295" y="122" fill="hsl(280 40% 75%)" fontSize="10">· GPU bring-up</text>
                  <text x="295" y="138" fill="hsl(280 40% 75%)" fontSize="10">· image-quality / pixel-diff</text>
                  <text x="295" y="154" fill="hsl(280 40% 75%)" fontSize="10">· perf benchmarking</text>
                  <text x="295" y="170" fill="hsl(280 40% 75%)" fontSize="10">· cross-vendor harness</text>
                  <text x="295" y="186" fill="hsl(280 40% 75%)" fontSize="10">· broadening primitives</text>
                  <circle cx="365" cy="240" r="6" fill="hsl(280 65% 65%)" />
                </g>

                {/* Server division — final */}
                <g>
                  <rect x="480" y="30" width="180" height="170" rx="12" fill="hsl(220 30% 18%)" stroke="hsl(40 80% 60%)" strokeWidth="2" />
                  <text x="570" y="56" fill="hsl(40 90% 85%)" fontSize="13" textAnchor="middle">Server division</text>
                  <text x="570" y="74" fill="hsl(40 60% 75%)" fontSize="10" textAnchor="middle">third iteration · rewrite</text>
                  <text x="495" y="98" fill="hsl(40 70% 80%)" fontSize="11" fontWeight="500">complete C# rewrite</text>
                  <text x="495" y="114" fill="hsl(40 50% 75%)" fontSize="10">· dynamic compilation</text>
                  <text x="495" y="130" fill="hsl(40 50% 75%)" fontSize="10">· tests as C# scripts</text>
                  <text x="495" y="146" fill="hsl(40 50% 75%)" fontSize="10">· server / protocol surfaces</text>
                  <text x="495" y="162" fill="hsl(40 50% 75%)" fontSize="10">· pluggable harness</text>
                  <text x="495" y="178" fill="hsl(40 50% 75%)" fontSize="10">· conviction crystallised</text>
                  <circle cx="570" cy="240" r="7" fill="hsl(40 80% 65%)" />
                </g>

                <text x="165" y="262" fill="hsl(195 60% 75%)" textAnchor="middle" fontSize="10">~2010</text>
                <text x="365" y="262" fill="hsl(280 55% 75%)" textAnchor="middle" fontSize="10">~mid-2010s</text>
                <text x="570" y="262" fill="hsl(40 75% 75%)" textAnchor="middle" fontSize="10">late-2010s onward</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              Three divisions, three altitudes of the same conviction.
              Each iteration broadened the surface and refined the
              primitive; the Server-division rewrite fully committed
              to the "tests as compiled code" shape.
            </figcaption>
          </figure>
          <p>
            What carried through every iteration: a test case is{" "}
            <em>not</em> a JSON manifest of input/expected pairs, not
            a YAML pipeline definition, not a domain-specific
            configuration. A test case is a program. The runner is
            an ordinary host process that loads the program, gives it
            access to the system under test through clean interfaces,
            and lets it run. What changed each time: the kinds of
            system being tested (Windows GUI / drivers → graphics
            pipelines / GPUs → server protocols / distributed
            services), the abstractions provided to the test author,
            and on the Server rewrite — the host language itself.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Server-Division rewrite · C# · dynamische Erstellung",heading: "Wie ein Test aussah",
      body: (
        <>
          <p>
            On the C# rewrite, a test case was an ordinary C# source
            file. The harness loaded it, fed it through{" "}
            <code className="text-foreground/80">CSharpCodeProvider</code>{" "}
            (and later Roslyn's compilation API), produced an in-memory
            assembly, instantiated the entry-point class, and invoked
            it against a configured environment:
          </p>
          <pre className="text-[11px] leading-5 bg-background/60 border border-border/40 rounded-lg p-4 overflow-x-auto font-mono">
{`// EncryptedConnectionTest.cs
//   compiled by the harness · run inline · no separate build step

using Qualcomm.TestHarness;
using Qualcomm.TestHarness.Server;

[TestCase(
   id: "server.tls.handshake.resume",
   tags: new[]{ "server", "tls", "handshake", "fast" }
)]
public class EncryptedConnectionTest : ServerTest {

   public override void Run(TestContext ctx) {
      using var server = ctx.Server.StartFresh();
      using var session1 = server.Connect();
      session1.PerformHandshake();
      var ticket = session1.SessionTicket;
      session1.Disconnect();

      using var session2 = server.Connect(resumeWith: ticket);
      var report = session2.PerformHandshake();

      ctx.Assert(report.WasResumed, "second handshake should resume");
      ctx.Assert(report.RoundTrips == 1, "resumption is single-RT");
      ctx.Record("ms", report.HandshakeMs);
   }
}`}
          </pre>
          <p>
            Three things to read here. The{" "}
            <code className="text-foreground/80">[TestCase]</code> attribute
            is metadata the harness picks up via reflection — id, tags,
            timeout, dependencies — letting any test be selected,
            scheduled, or filtered without parsing source. The body of{" "}
            <code className="text-foreground/80">Run</code> has the full
            C# language surface: <code className="text-foreground/80">using</code>{" "}
            for resource discipline, exceptions for failure
            propagation, LINQ for assertion construction, the language
            standard library for everything else. And{" "}
            <code className="text-foreground/80">ctx.Record(...)</code>{" "}
            gives a structured way to emit performance numbers that
            roll up into the run report — tests aren't just pass/fail,
            they carry signal.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Die architektonische Form",
      body: (
        <>
          <p>
            Two layers held the system together: the harness and the
            test surface.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 320" className="w-full h-auto" role="img" aria-labelledby="qc-arch-title">
              <title id="qc-arch-title">Qualcomm test-automation harness architecture</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* Top: source tree */}
                <rect x="60" y="20" width="600" height="44" rx="10" fill="hsl(220 25% 18%)" stroke="hsl(140 60% 60%)" />
                <text x="80" y="42" fill="hsl(140 80% 80%)" fontSize="13">Test source tree · *.cs files</text>
                <text x="80" y="58" fill="hsl(140 50% 70%)" fontSize="10">authored by engineers · versioned in repo · plain C# with [TestCase] attributes</text>

                <line x1="360" y1="64" x2="360" y2="80" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />

                {/* Middle: harness */}
                <rect x="60" y="80" width="600" height="120" rx="10" fill="hsl(40 35% 16%)" stroke="hsl(40 80% 60%)" strokeWidth="2" />
                <text x="80" y="106" fill="hsl(40 90% 85%)" fontSize="14" fontWeight="500">Harness · in-process</text>
                <text x="80" y="124" fill="hsl(40 60% 75%)" fontSize="11">discovery — scan tree · read [TestCase] · build dependency graph</text>
                <text x="80" y="140" fill="hsl(40 60% 75%)" fontSize="11">compile — CSharpCodeProvider / Roslyn → in-memory assembly</text>
                <text x="80" y="156" fill="hsl(40 60% 75%)" fontSize="11">schedule — select/filter/parallelise · share fixtures · honour deps</text>
                <text x="80" y="172" fill="hsl(40 60% 75%)" fontSize="11">execute — instantiate, Run(ctx), capture exceptions, collect signal</text>
                <text x="80" y="188" fill="hsl(40 60% 75%)" fontSize="11">report — pass/fail · timings · perf · structured artifacts</text>

                <line x1="240" y1="200" x2="240" y2="220" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />
                <line x1="480" y1="200" x2="480" y2="220" stroke="hsl(220 30% 60%)" strokeWidth="1.5" />

                {/* Bottom left: TestContext */}
                <rect x="60" y="220" width="280" height="80" rx="10" fill="hsl(220 25% 16%)" stroke="hsl(195 60% 55%)" />
                <text x="80" y="246" fill="hsl(195 80% 80%)" fontSize="13">TestContext (per run)</text>
                <text x="80" y="264" fill="hsl(195 50% 70%)" fontSize="10">handles to the system under test · fixtures</text>
                <text x="80" y="280" fill="hsl(195 50% 70%)" fontSize="10">Assert · Record · Skip · Retry · timing</text>

                {/* Bottom right: System under test */}
                <rect x="380" y="220" width="280" height="80" rx="10" fill="hsl(220 25% 16%)" stroke="hsl(280 50% 60%)" />
                <text x="400" y="246" fill="hsl(280 80% 80%)" fontSize="13">System under test</text>
                <text x="400" y="264" fill="hsl(280 50% 70%)" fontSize="10">drivers · servers · GPUs · protocols</text>
                <text x="400" y="280" fill="hsl(280 50% 70%)" fontSize="10">accessed through clean interfaces</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              Source tree on top, harness in the middle (the
              load-bearing layer), TestContext + system-under-test at
              the bottom. The harness is where the dynamic-compilation
              conviction lives.
            </figcaption>
          </figure>
          <p>
            The harness was the load-bearing piece. Its public surface
            was small — discover, compile, schedule, execute, report —
            but each verb hid years of subtlety. <em>Discover</em>{" "}
            walked thousands of files; <em>compile</em> handled
            dependencies between test files (a helper compiled into
            its own assembly that test-cases referenced) and surfaced
            compile errors as legible feedback rather than runtime
            stack-traces; <em>schedule</em> read the dependency graph
            and parallelised what was independent while serialising
            what shared fixtures. The conviction the harness encoded:{" "}
            <strong>tests deserve the same engineering rigour as the
            production code they test</strong>. Same language. Same
            tooling. Same review discipline.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Warum dynamische Zusammenstellung",heading: "Code kompiliert, kein zweiter Buildschritt",
      body: (
        <>
          <p>
            Two alternatives the system explicitly walked away from:
          </p>
          <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
            <li>
              <strong>Pre-compiled test DLLs.</strong> Every change
              meant a build. CI cycles got long. Test authors stopped
              iterating because the feedback loop was slow.
              Dynamic-compilation in-process meant{" "}
              <code className="text-foreground/80">save → run</code>{" "}
              with no intermediate build artifact.
            </li>
            <li>
              <strong>Configuration-driven test runners.</strong> JSON
              or YAML describing input, expected output, and assertion
              rules. Looks neat for the simplest cases; collapses the
              moment a test needs a loop, a conditional, a helper
              function, or a non-trivial setup. The C# language was
              already a configuration language for any test that
              needed it; reaching for a second one was duplication.
            </li>
          </ul>
          <p>
            The deeper reading: <em>the runtime that compiles your
            tests is the same runtime that runs them</em>. No
            translation layer between author intent and execution.
            Same shape{" "}
            <Link href="/people/bml-language" className="text-primary hover:underline">
              BML
            </Link>
            's grammar achieved at the language level (the parser
            parses its own grammar) and{" "}
            <Link href="/people/quark-virtual-dom" className="text-primary hover:underline">
              the Quark Virtual DOM
            </Link>
            {" "}achieved at the application level (clients drive the
            app through its own self-described surface) — here the
            shape is achieved at the test-system level.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Zwölf Jahre",
      body: (
        <>
          <p>
            What gets named in twelve years that doesn't get named in
            twelve months: the system saw enough kinds of test, on
            enough kinds of substrate, that the abstractions stopped
            being a guess and became measured. The Server rewrite
            wasn't a clean-sheet redesign because of a fad — it was
            because the C# substrate's dynamic-compilation capability
            (mature by the late 2010s) finally made the conviction
            implementation-cheap. Once Roslyn was widely available the
            harness could stop maintaining its own ad-hoc compilation
            pipeline and lean on the platform.
          </p>
          <p>
            The pattern that recurs in this body's work: an idea is
            named at the language level (BML, 2000), applied at the
            application level (Quark Virtual DOM and undo/redo,
            2000-2005), proved at the systems level (Qualcomm test
            automation, 2009-2022), and then circulated as the
            substrate of a network (Coherence-Network, current). Same
            conviction, four altitudes, twenty-six years.
          </p>
          <p>
            Boulder is also part of what carried. The twelve Qualcomm
            years are the same years 5Rhythms entered the rotation,
            the Audible listening hours climbed into the thousands,
            and the body began to learn that the technical thread and
            the embodied thread are not separate practices. The work
            that lived during those years is in this page; the body
            that lived during those years is everywhere else on this
            network.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <p>
      Company context:{" "}
      <Link
        href="https://www.qualcomm.com"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        qualcomm.com
      </Link>
      . Source code is internal to Qualcomm and not public; what
      lives here is the architectural shape, the design rationale,
      and the lived memory of designing, shipping, and rewriting it
      across three divisions over twelve years. Urs is invited to
      refine any technical detail through the Refine doorway below.
    </p>
  ),
};

export default content;
