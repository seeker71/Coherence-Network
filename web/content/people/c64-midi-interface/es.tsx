// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug c64-midi-interface --target-lang es --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Commodore 64 MIDI Interface (age 13, ~1984-85) — primer trabajo de programación",description: "Edad 13. Comodoro 64. No hay documentación de referencia. Ejecutó una interfaz MIDI de trabajo con un manipulador de servicio interrumpido en el montaje 6510, alojado de un arnés BASIC, completamente autodidacta de las páginas de atrás de Commodore Magazine y páginas de código hex escritas a mano. La primera pieza en el cuerpo de evidencia y la piedra clave donde comenzó la relación de este cuerpo con la programación.",
  },breadcrumbName: "Commodore 64 MIDI · 13 años",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(220 35% 14%) 50%, hsl(195 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Trabajo · Commodore 64 · Suiza · ~1984-1985 · edad 13 · primera programación",
    eyebrowClass: "text-[hsl(var(--primary))]",name: "Commodore 64 — interfaz MIDI · edad 13",
    welcome: (
      <p>
        Age 13. A{" "}
        <Link href="https://en.wikipedia.org/wiki/Commodore_64" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          Commodore 64
        </Link>
        . No reference documentation, no books — only{" "}
        <strong>Commodore Magazine</strong> and pages of{" "}
        <em>assembly hex code typed in by hand</em>. From those
        sources alone, this body wrote a working{" "}
        <strong>MIDI interface</strong> with an{" "}
        <strong>interrupt-service handler in 6510 assembly</strong>{" "}
        called from a BASIC host program. <em>Self-taught</em> in the
        most literal sense: BASIC was the first language; assembly
        was the second; the C64 hardware was the textbook. The
        earliest load-bearing piece in the body of evidence and the
        place where this body's relationship to programming first
        crystallised.
      </p>
    ),
  },
  facts: [
    {label: "Era",value: "Commodore 64 · Suiza · aproximadamente 1984-1985 · 13 años" },
    {label: "Hardware",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/Commodore_64" target="_blank" rel="noopener noreferrer" className="hover:text-primary">Commodore 64</Link>
          {" "}home computer · MOS 6510 CPU · 64 KB RAM · CIA chips for I/O · user port for the MIDI link
        </>
      ),
    },
    {label: "Idiomas",
      value: (
        <>
          <Link href="https://en.wikipedia.org/wiki/Commodore_BASIC" target="_blank" rel="noopener noreferrer" className="hover:text-primary">Commodore BASIC v2</Link>
          {" "}— the entry surface · 6510 assembly — the interrupt-handler core, typed as raw hex
        </>
      ),
    },
    {label: "Material de referencia",
      value: (
        <>
          Commodore Magazine articles · pages of hex listings printed
          in the magazine that had to be{" "}
          <em>typed in by hand</em> · no books, no manuals, no internet
        </>
      ),
    },
    {label: "Lo que hizo",
      value: (
        <>
          Real{" "}
          <Link href="https://en.wikipedia.org/wiki/MIDI" target="_blank" rel="noopener noreferrer" className="hover:text-primary">MIDI</Link>
          {" "}— Musical Instrument Digital Interface, the era's emerging
          standard for synthesizer-to-computer communication. The
          interrupt-service handler caught incoming MIDI bytes; BASIC
          sat on top to express musical-application logic.
        </>
      ),
    },
    {label: "Líneas de avance",
      value: (
        <>
          Five years later this body would build the{" "}
          <Link href="/people/schindler-hc11-protocol" className="hover:text-primary">
            Schindler 7-layer protocol stack
          </Link>
          {" "}with the same posture: bare-metal hardware, no
          off-the-shelf tooling, write what isn't there. The
          conviction "build the tool you need, all the way down"
          starts here.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Lo que significaba \"auto-traído\" en 1984",
    body: (
      <p>
        In a Swiss household in 1984, computing reference material was
        what arrived on the news-stand once a month. <em>Commodore
        Magazine</em> printed long listings — sometimes BASIC,
        sometimes raw assembly hex — and the way you got them onto
        your machine was: type them. Every byte. With no syntax
        highlighting, no auto-complete, no error checker. A typo
        meant the program wouldn't run, and finding the typo meant
        re-reading the page against the screen until the
        eye caught it. The 13-year-old who wrote this MIDI interface
        spent <em>days</em> doing that, not because of dedication, but
        because there was no other path. The relationship to
        programming this body still carries — every byte matters,
        every instruction is yours to own — comes from those
        afternoons.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "¿Qué había en el escritorio",
      body: (
        <>
          <p>
            One Commodore 64. One TV set as monitor. One cassette
            drive (or, with luck, a 1541 floppy). One MIDI cable to a
            synthesizer. One stack of Commodore Magazine issues. That
            was the entire toolchain.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 320" className="w-full h-auto" role="img" aria-labelledby="c64-rig-title">
              <title id="c64-rig-title">The Commodore 64 MIDI bring-up rig, age 13</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* C64 keyboard */}
                <rect x="220" y="120" width="280" height="100" rx="8" fill="hsl(220 30% 18%)" stroke="hsl(195 70% 60%)" strokeWidth="2" />
                <text x="360" y="148" textAnchor="middle" fill="hsl(195 90% 85%)" fontSize="14">Commodore 64</text>
                <text x="360" y="168" textAnchor="middle" fill="hsl(195 60% 75%)" fontSize="11">MOS 6510 · 64 KB RAM · CIA chips</text>
                <text x="360" y="184" textAnchor="middle" fill="hsl(195 50% 70%)" fontSize="10">user port · cassette · serial · video out</text>
                <text x="360" y="200" textAnchor="middle" fill="hsl(195 50% 70%)" fontSize="10">BASIC v2 in ROM</text>

                {/* TV monitor */}
                <rect x="60" y="50" width="120" height="90" rx="8" fill="hsl(220 30% 14%)" stroke="hsl(40 70% 60%)" />
                <text x="120" y="78" textAnchor="middle" fill="hsl(40 80% 80%)" fontSize="11">TV set</text>
                <text x="120" y="96" textAnchor="middle" fill="hsl(40 50% 70%)" fontSize="10">RF modulator</text>
                <text x="120" y="112" textAnchor="middle" fill="hsl(40 50% 70%)" fontSize="10">40×25 chars</text>
                <line x1="180" y1="100" x2="220" y2="160" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                {/* Magazine */}
                <rect x="60" y="200" width="120" height="80" rx="6" fill="hsl(220 30% 14%)" stroke="hsl(280 60% 65%)" />
                <text x="120" y="222" textAnchor="middle" fill="hsl(280 80% 82%)" fontSize="11">Commodore</text>
                <text x="120" y="238" textAnchor="middle" fill="hsl(280 80% 82%)" fontSize="11">Magazine</text>
                <text x="120" y="258" textAnchor="middle" fill="hsl(280 50% 75%)" fontSize="9" fontStyle="italic">pages of hex</text>
                <text x="120" y="270" textAnchor="middle" fill="hsl(280 50% 75%)" fontSize="9" fontStyle="italic">to type by hand</text>

                {/* Synthesizer / MIDI device */}
                <rect x="540" y="200" width="140" height="80" rx="8" fill="hsl(220 30% 14%)" stroke="hsl(140 60% 55%)" />
                <text x="610" y="226" textAnchor="middle" fill="hsl(140 80% 80%)" fontSize="11">MIDI synth</text>
                <text x="610" y="242" textAnchor="middle" fill="hsl(140 50% 70%)" fontSize="10">5-pin DIN out</text>
                <text x="610" y="258" textAnchor="middle" fill="hsl(140 50% 70%)" fontSize="10">31.25 kbaud serial</text>
                <line x1="540" y1="240" x2="500" y2="200" stroke="hsl(140 50% 55%)" strokeWidth="1.5" />
                <text x="510" y="225" fill="hsl(140 50% 70%)" fontSize="10">MIDI</text>

                {/* Cassette */}
                <rect x="540" y="50" width="140" height="80" rx="6" fill="hsl(220 30% 14%)" stroke="hsl(220 50% 65%)" />
                <text x="610" y="76" textAnchor="middle" fill="hsl(220 70% 80%)" fontSize="11">1530 cassette</text>
                <text x="610" y="94" textAnchor="middle" fill="hsl(220 50% 70%)" fontSize="10">save / load</text>
                <text x="610" y="110" textAnchor="middle" fill="hsl(220 50% 70%)" fontSize="10">~300 bytes / second</text>
                <line x1="540" y1="100" x2="500" y2="140" stroke="hsl(220 50% 60%)" strokeWidth="1.2" />
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              The bring-up rig. C64 in the centre, TV as monitor, cassette
              for save/load, MIDI synth on the user-port side, magazine on
              the desk. The magazine was as load-bearing as any of the
              hardware.
            </figcaption>
          </figure>
          <p>
            The user port on the back of the C64 was the door to the
            outside world: 8 bidirectional data lines, control
            signals, and access to the CIA (Complex Interface Adapter)
            chip's interrupt machinery. MIDI runs at 31.25 kbaud, a
            non-standard rate the C64's hardware UART couldn't generate
            cleanly — so the interface was hand-built around the CIA's
            shift register and timer, with the timing recovered in
            software at the byte boundaries.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Por qué un manipulador interrumpido",heading: "Los bytes MIDI no esperan",
      body: (
        <>
          <p>
            MIDI's 31.25 kbaud means a byte every 320 microseconds.
            BASIC on a 1 MHz 6510 cannot poll fast enough to catch
            bytes at that rate without dropping events. The only way
            to capture incoming MIDI cleanly was to handle it in an
            interrupt-service routine in assembly: when the CIA
            signalled "byte available," the CPU would jump to the
            handler, read the byte, push it into a ring buffer, and
            return — all in less than 320 microseconds, leaving BASIC
            free to run musical-application logic on top of the
            buffered stream.
          </p>
          <p>
            Writing that kind of code at 13 with no documentation
            meant: figure out where to install the IRQ vector
            (<code className="text-foreground/80">$0314/$0315</code>{" "}
            on the C64), how to chain to the kernel's existing IRQ
            handler so the system kept running, what the CIA's
            interrupt-control register bits meant, and how to ring-
            buffer in the zero page for fastest access. The magazine
            articles named the tools; the integration was on the
            13-year-old.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "La forma del programa",
      body: (
        <>
          <p>
            Two pieces fit together: BASIC was the framework; the
            assembly handler was the engine.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 320" className="w-full h-auto" role="img" aria-labelledby="c64-program-title">
              <title id="c64-program-title">BASIC harness over assembly interrupt handler</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="12">
                {/* BASIC top */}
                <rect x="60" y="20" width="600" height="80" rx="10" fill="hsl(220 30% 18%)" stroke="hsl(195 60% 60%)" />
                <text x="80" y="46" fill="hsl(195 80% 82%)" fontSize="13">BASIC harness · the user-facing surface</text>
                <text x="80" y="64" fill="hsl(195 60% 75%)" fontSize="10">10 SYS install_handler</text>
                <text x="80" y="78" fill="hsl(195 60% 75%)" fontSize="10">20 GET MIDI byte from buffer  → musical logic</text>
                <text x="80" y="92" fill="hsl(195 60% 75%)" fontSize="10">30 PRINT note name · trigger UI events · loop</text>

                <line x1="360" y1="100" x2="360" y2="120" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                {/* Ring buffer */}
                <rect x="200" y="120" width="320" height="50" rx="8" fill="hsl(220 30% 14%)" stroke="hsl(140 60% 55%)" strokeDasharray="4,3" />
                <text x="360" y="142" textAnchor="middle" fill="hsl(140 80% 80%)" fontSize="12">Ring buffer in zero-page</text>
                <text x="360" y="158" textAnchor="middle" fill="hsl(140 50% 70%)" fontSize="10">8-byte FIFO · head/tail pointers · written by ISR · read by BASIC</text>

                <line x1="360" y1="170" x2="360" y2="190" stroke="hsl(220 30% 60%)" strokeWidth="1.2" />

                {/* Assembly ISR */}
                <rect x="60" y="190" width="600" height="100" rx="10" fill="hsl(40 35% 16%)" stroke="hsl(40 80% 60%)" strokeWidth="2" />
                <text x="80" y="216" fill="hsl(40 90% 85%)" fontSize="13">6510 assembly · interrupt-service routine</text>
                <text x="80" y="234" fill="hsl(40 60% 75%)" fontSize="10">PHA  PHX  PHY        ; save registers</text>
                <text x="80" y="248" fill="hsl(40 60% 75%)" fontSize="10">LDA $DC0D            ; CIA interrupt source</text>
                <text x="80" y="262" fill="hsl(40 60% 75%)" fontSize="10">AND #$08             ; was it the shift register?</text>
                <text x="80" y="276" fill="hsl(40 60% 75%)" fontSize="10">BEQ +chain           ; if not, chain to old handler</text>
                <text x="380" y="234" fill="hsl(40 60% 75%)" fontSize="10">LDA $DC0C            ; read MIDI byte</text>
                <text x="380" y="248" fill="hsl(40 60% 75%)" fontSize="10">LDX buf_head         ; into ring buffer</text>
                <text x="380" y="262" fill="hsl(40 60% 75%)" fontSize="10">STA buffer,X         ; store</text>
                <text x="380" y="276" fill="hsl(40 60% 75%)" fontSize="10">INX  STX buf_head    ; advance · 320 µs total</text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              BASIC on top, ring buffer in the zero page, assembly ISR
              underneath. The ring buffer was the contract — the
              assembly side wrote, the BASIC side read, and neither
              had to wait for the other.
            </figcaption>
          </figure>
          <p>
            This is the same architecture this body would commit to
            again and again in later decades: a fast inner loop in a
            low-level language, an expressive outer surface in a
            higher-level one, and a clean buffer or message contract
            between them. BMCPU at the bottom + BML on top (
            <Link href="/people/bml-language" className="text-primary hover:underline">2000 thesis</Link>
            ); QuarkXPress runtime at the bottom + Virtual DOM on top
            (
            <Link href="/people/quark-virtual-dom" className="text-primary hover:underline">2000-2005</Link>
            ); FastAPI + Neo4j at the bottom + Next.js + the curated
            page you are reading on top (
            <Link href="/people/coherence-network" className="text-primary hover:underline">now</Link>
            ). The shape was named on a Commodore 64 at 13.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Tres condenas sembradas aquí",heading: "Lo que sobrevivió cuarenta años",
      body: (
        <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
          <li>
            <strong>Reach for the layer that fits the job.</strong>{" "}
            BASIC for the user surface; assembly for the time-critical
            handler. Pick the substrate that matches the constraint,
            not the one that's most familiar. Same posture in the{" "}
            <Link href="/people/qualcomm-test-automation" className="text-primary hover:underline">
              Qualcomm test harness
            </Link>
            's choice of dynamic C# compilation over configuration
            files, twenty-six years later.
          </li>
          <li>
            <strong>If the documentation isn't there, write it for
            yourself.</strong> The 13-year-old reverse-engineered the
            CIA chip's interrupt machinery from magazine listings,
            test programs, and hardware behaviour. Same posture in
            the{" "}
            <Link href="/people/schindler-hc11-protocol" className="text-primary hover:underline">
              Schindler HC11 work
            </Link>
            's custom debugger five years later.
          </li>
          <li>
            <strong>The body is the textbook.</strong> Programming
            became inseparable from <em>watching what the machine
            actually did</em>. No abstraction layer between intent and
            execution. The same intimacy with the substrate threads
            forward through every later iteration of this body's
            work.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <p>
      Source materials are pre-digital and not in any public archive.
      What lives here is the architectural shape, the user's own
      framing, and the lived memory. The platform itself is documented
      at{" "}
      <Link href="https://en.wikipedia.org/wiki/Commodore_64" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        Wikipedia · Commodore 64
      </Link>
      ; the protocol at{" "}
      <Link href="https://en.wikipedia.org/wiki/MIDI" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
        Wikipedia · MIDI
      </Link>
      . Urs is invited to refine any technical detail or the exact
      year-range through the Refine doorway below.
    </p>
  ),
};

export default content;
