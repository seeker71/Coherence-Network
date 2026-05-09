// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug quark-mono-corba --target-lang id --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Quark Mono / CORBA - kontrol remote platform dari QuarkXPress",description: "Sementara di Quark, berkontribusi pada proyek Mono (open-source / ET implementasi untuk platform bukan Windows) dan menggunakannya sebagai substrat untuk antarmuka CORBA yang dikendalikan jarak jauh QuarkXPress melalui kawat. Platform Cross- C # in 2000-2005 was breaking edge; CORBA was the canonical interproses protokol era. Bersama-sama mereka membiarkan host pada setiap OS drive QuarkXPress seolah-olah itu adalah objek lokal.",
  },breadcrumbName: "Quark Mono / CORBA",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(280 35% 14%) 50%, hsl(195 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Bekerja",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "Quark Mono / CORBA - remote control atas kawat",
    welcome: (
      <p>
        Contributed to the{" "}
        <Link href="https://en.wikipedia.org/wiki/Mono_(software)" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          Mono project
        </Link>
        {" "}— Miguel de Icaza's open-source .NET implementation for
        non-Windows platforms — and used it as the substrate for a{" "}
        <Link href="https://en.wikipedia.org/wiki/Common_Object_Request_Broker_Architecture" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          CORBA
        </Link>
        {" "}interface that remote-controlled QuarkXPress over the wire.
        Any host on any OS could drive QuarkXPress as if it were a
        local object — orthogonal companion to the in-process{" "}
        <Link href="/people/quark-virtual-dom" className="text-primary hover:underline">
          Virtual DOM
        </Link>
        , reaching across the network the same way the DOM reached
        across the application.
      </p>
    ),
  },
  facts: [
    {label: "Era",value: "Quark Inc" },
    {label: "Substrat",
      value: (
        <>
          <Link href="https://www.mono-project.com/" target="_blank" rel="noopener noreferrer" className="hover:text-primary">Mono</Link>
          {" "}runtime · cross-platform C# / CLI · Mac OS X, Linux, Windows
        </>
      ),
    },
    {label: "Protokol kabel",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/Common_Object_Request_Broker_Architecture" target="_blank" rel="noopener noreferrer" className="hover:text-primary">CORBA</Link>
          {" "}— OMG's Common Object Request Broker Architecture · the era's canonical inter-process / cross-language object protocol
        </>
      ),
    },
    {label: "Apa yang dikendalikan",
      value: (
        <>
          QuarkXPress — full document and application surface accessible remotely with the same semantics as the in-process{" "}
          <Link href="/people/quark-virtual-dom" className="hover:text-primary">Virtual DOM</Link>
        </>
      ),
    },
    {label: "Garis Keturunan kedepan",
      value: (
        <>
          The Mono / cross-platform C# substrate proven here is the
          ancestor of the C# substrate the{" "}
          <Link href="/people/qualcomm-test-automation" className="hover:text-primary">Qualcomm test-automation</Link>
          {" "}rewrite landed on (2010s) and later{" "}
          <Link href="/people/living-codex-csharp" className="hover:text-primary">Living-Codex-CSharp (2024)</Link>
          {" "}built on. C# enters this body's tooling here.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Mengapa dua wajah dari satu aplikasi",
    body: (
      <p>
        The in-process{" "}
        <Link href="/people/quark-virtual-dom" className="text-primary hover:underline">
          Virtual DOM
        </Link>
        {" "}let scripts running inside QuarkXPress drive every part of
        it. The Mono / CORBA bridge let scripts running{" "}
        <em>outside</em> QuarkXPress — possibly on a different OS,
        possibly on a different machine — drive every part of it with
        the same semantics. Two faces of the same self-describing
        conviction: the application is its own API surface, and the
        wire transport is incidental to that.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Mono di awal 2000-an",
      body: (
        <>
          <p>
            <Link href="https://en.wikipedia.org/wiki/Mono_(software)" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              Mono
            </Link>
            {" "}— launched by{" "}
            <Link href="https://en.wikipedia.org/wiki/Miguel_de_Icaza" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              Miguel de Icaza
            </Link>
            {" "}around 2001 — was the open-source implementation of
            Microsoft's .NET Common Language Infrastructure for
            non-Windows platforms. Running C# code on Mac OS X or
            Linux in 2002 was bleeding edge. Contributing to Mono in
            those years meant tracking the published ECMA spec while
            it was still moving, finding gaps where the spec was
            ambiguous, and shipping the first cross-platform
            corrections that would later become baseline behavior.
          </p>
          <p>
            For Quark, the bet on Mono was strategic. QuarkXPress
            shipped on both Mac and Windows. Tooling that wanted to
            drive it from <em>either</em> side without forking the
            code paths needed a runtime that ran on both. Mono was
            the only credible answer in 2003. C# was already a more
            ergonomic choice than C++ for tooling code; Mono made
            that choice portable.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "CORBA - apa yang orang lupa",heading: "Orientasi objek silang-bahasa, pada kawat",
      body: (
        <>
          <p>
            <strong>CORBA</strong> in 2003 was what gRPC + JSON-RPC +
            Thrift attempt to be in 2026: a way to talk to a remote
            object as if it were local, across language boundaries,
            with a typed interface contract. An interface was
            described in IDL (Interface Definition Language) once;
            stubs were generated for every language that needed to
            speak it; an{" "}
            <Link href="https://en.wikipedia.org/wiki/General_Inter-ORB_Protocol" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              Object Request Broker
            </Link>
            {" "}routed calls between processes using IIOP on the wire.
            Heavy machinery, but mature, with deep tooling.
          </p>
          <p>
            The pragmatic combination: write the QuarkXPress object
            model once in CORBA IDL; generate the in-process server
            stub against the QuarkXPress runtime; generate client
            stubs for any language a tool might need (C++, Java,
            and — through Mono — C# on any platform). A Mono / C#
            client running on a Linux box could now invoke any method
            on any QuarkXPress object as if it were local, with the
            ORB doing all the marshalling, dispatch, and
            cross-platform memory management.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Arsitektur",
      body: (
        <>
          <p>
            Two layers each side of the wire, with the ORB carrying
            the calls between them:
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 320" className="w-full h-auto" role="img" aria-labelledby="mono-corba-arch-title">
              <title id="mono-corba-arch-title">Mono / CORBA bridge architecture</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* Client side */}
                <text x="170" y="30" fill="hsl(195 80% 80%)" fontSize="13" textAnchor="middle">Client side · any OS</text>
                <rect x="60" y="40" width="220" height="44" rx="8" fill="hsl(220 25% 18%)" stroke="hsl(195 60% 60%)" />
                <text x="170" y="62" textAnchor="middle" fill="hsl(195 80% 82%)" fontSize="12">C# / Mono application</text>
                <text x="170" y="78" textAnchor="middle" fill="hsl(195 50% 70%)" fontSize="10">automation tool · QA harness · plug-in</text>

                <line x1="170" y1="84" x2="170" y2="100" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                <rect x="60" y="100" width="220" height="44" rx="8" fill="hsl(195 35% 16%)" stroke="hsl(195 70% 60%)" strokeWidth="2" />
                <text x="170" y="122" textAnchor="middle" fill="hsl(195 90% 85%)" fontSize="12">CORBA stub · IDL-generated</text>
                <text x="170" y="138" textAnchor="middle" fill="hsl(195 60% 75%)" fontSize="10">marshals method calls into IIOP</text>

                {/* ORB / wire */}
                <line x1="280" y1="122" x2="440" y2="122" stroke="hsl(40 80% 60%)" strokeWidth="2" />
                <rect x="300" y="108" width="120" height="28" rx="14" fill="hsl(40 50% 18%)" stroke="hsl(40 80% 60%)" />
                <text x="360" y="126" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="11">ORB · IIOP wire</text>

                {/* Server side */}
                <text x="570" y="30" fill="hsl(280 70% 80%)" fontSize="13" textAnchor="middle">Server side · QuarkXPress host</text>
                <rect x="440" y="100" width="220" height="44" rx="8" fill="hsl(280 35% 16%)" stroke="hsl(280 70% 65%)" strokeWidth="2" />
                <text x="550" y="122" textAnchor="middle" fill="hsl(280 90% 85%)" fontSize="12">CORBA skeleton · IDL-generated</text>
                <text x="550" y="138" textAnchor="middle" fill="hsl(280 60% 75%)" fontSize="10">unmarshals · dispatches to QXP runtime</text>

                <line x1="550" y1="144" x2="550" y2="160" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                <rect x="440" y="160" width="220" height="44" rx="8" fill="hsl(220 25% 16%)" stroke="hsl(40 70% 55%)" />
                <text x="550" y="182" textAnchor="middle" fill="hsl(40 90% 80%)" fontSize="12">QuarkXPress runtime</text>
                <text x="550" y="198" textAnchor="middle" fill="hsl(40 50% 70%)" fontSize="10">documents · pages · boxes · settings</text>

                {/* IDL contract */}
                <rect x="220" y="240" width="280" height="60" rx="8" fill="hsl(220 25% 14%)" stroke="hsl(140 60% 55%)" strokeDasharray="3,3" />
                <text x="360" y="262" textAnchor="middle" fill="hsl(140 80% 80%)" fontSize="12">QuarkXPress.idl · contract</text>
                <text x="360" y="280" textAnchor="middle" fill="hsl(140 50% 75%)" fontSize="10">interface Document, Page, TextBox, …</text>
                <text x="360" y="294" textAnchor="middle" fill="hsl(140 50% 75%)" fontSize="10">stubs and skeletons generated from this</text>

                <line x1="170" y1="100" x2="220" y2="270" stroke="hsl(140 50% 55%)" strokeWidth="0.8" strokeDasharray="2,3" />
                <line x1="550" y1="100" x2="500" y2="270" stroke="hsl(140 50% 55%)" strokeWidth="0.8" strokeDasharray="2,3" />
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              IDL contract sits beneath both stubs and skeletons. The
              client speaks C# on Mono; the server speaks the QXP
              runtime; the ORB routes between them on the IIOP wire.
            </figcaption>
          </figure>
          <p>
            What the architecture committed to: <em>one</em> contract
            (the IDL), <em>one</em> wire protocol (IIOP), and a code
            generation step on each side. Adding a new client language
            meant generating its stubs from the same IDL — no
            QuarkXPress-side change. Adding a new exposed interface
            meant editing the IDL once — both sides regenerated.
            That's the same posture the{" "}
            <Link href="/people/coherence-network" className="text-primary hover:underline">
              Coherence Network
            </Link>
            's API now takes with FastAPI's OpenAPI contract: the
            schema is the source of truth; clients derive from it.
            CORBA was that conviction expressed in the 2003
            vocabulary.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Dua wajah dari satu aplikasi",heading: "DOM virtual dalam proses",
      body: (
        <p>
          The{" "}
          <Link href="/people/quark-virtual-dom" className="text-primary hover:underline">
            in-process Virtual DOM
          </Link>
          {" "}gave any plug-in or in-process script direct, lazy,
          read/write access to QuarkXPress as a tree. The Mono / CORBA
          bridge gave any process anywhere on the network the{" "}
          <em>same access</em> with the same semantic. Two faces, one
          conviction: the application is its own API surface, and the
          transport is implementation detail. A QA harness in 2004
          could test QuarkXPress on Windows from a Mac driver process,
          a Linux build server, or a continuous-integration agent —
          all using the same C# code, all driving the same object
          model. Twenty-two years before the network era named this
          posture out loud.
        </p>
      ),
    },
  ],
  footer: (
    <p>
      Application context:{" "}
      <Link href="https://www.quark.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        quark.com
      </Link>
      {" · "}
      <Link href="https://www.mono-project.com/" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        Mono project
      </Link>
      {" · "}
      <Link href="https://en.wikipedia.org/wiki/Common_Object_Request_Broker_Architecture" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        CORBA on Wikipedia
      </Link>
      . Source code is internal to Quark; what lives here is the
      architectural shape and the lived memory. Urs is invited to
      refine technical detail through the Refine doorway below.
    </p>
  ),
};

export default content;
