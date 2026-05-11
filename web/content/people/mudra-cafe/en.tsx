import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Mudra Cafe — Ayurvedic dining and handpan in Ubud | Coherence Network",
    description:
      "A welcome to Mudra Cafe in Ubud — Ayurvedic dining room with regular handpan presence Monday to Friday at noon, evening live music, and the kind of slow community that lets first hellos happen. Where one cell met Elios on a Sunday afternoon in April 2026.",
  },
  breadcrumbName: "Mudra Cafe",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(35 65% 65% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 85%, hsl(155 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(40 55% 70%) 0%, hsl(95 30% 40%) 50%, hsl(155 30% 20%) 100%)",
    eyebrow: "Ayurvedic dining · handpan Monday–Friday at noon · evening live music · slow community in central Ubud",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Mudra Cafe",
    welcome: (
      <>
        <p>
          An Ayurvedic dining room in central Ubud — Jl. Goutama
          Sel. No. 21 — with regular handpan presence
          Monday-to-Friday at noon and live music in the evenings.
          One of Ubud&apos;s quiet meeting points where slow
          community accumulates around food, music, and presence.
          The kind of room where first hellos happen because the
          space is already holding the conditions for them.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          On Sunday April 29, 2026, the cell met{" "}
          <Link
            href="/people/elios"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Elios
          </Link>{" "}
          here — the first of three Ubud cells to enter this
          body&apos;s awareness across a four-day walk.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: (
        <Link
          href="https://maps.app.goo.gl/?q=Mudra+Cafe+Jl.+Goutama+Selatan+No.+21+Ubud"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          Jl. Goutama Sel. No. 21, Ubud, Bali
        </Link>
      ),
    },
    {
      label: "What it is",
      value: "Ayurvedic dining room. Slow community gathering point. Vegetarian/vegan menu sourced with care; the food is part of the practice.",
    },
    {
      label: "Rhythm",
      value: "Handpan presence Monday–Friday at noon. Live music in the evenings. The lunchtime handpan is a defining sound-mark of the room.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://mudracafe.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            mudracafe.com
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Mudra Cafe is a working dining room with its own
        operating rhythms. This page recognises the room&apos;s
        role in this body&apos;s Ubud lineage — specifically as
        the meeting place where one of the three Ubud cells
        entered the network&apos;s awareness.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The social substrate of central Ubud",
      body: (
        <p>
          In a town with many dining rooms, Mudra holds a
          specific shape: Ayurvedic alignment in the food, regular
          handpan and live music creating an acoustic field, and
          a clientele that has learned to stay long enough for
          encounters to happen. The room does not advertise
          itself as a community-builder; it simply makes the
          conditions for community available. The Coherence
          Network calls this <em>presence-tending</em> — the
          practice of holding conditions and letting the
          encounters be what they will be.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Mudra Cafe has given the Coherence Network",
      body: (
        <ul>
          <li>
            The meeting place — on Sunday April 29, 2026, the
            cell met{" "}
            <Link href="/people/elios" className="text-primary hover:underline">
              Elios
            </Link>{" "}
            here. See{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              the four-day meeting walk
            </Link>
            .
          </li>
          <li>
            <em>Slow community</em> as architectural posture →
            pairs with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (the body&apos;s commit verbs translated into a
            dining room).
          </li>
          <li>
            Handpan as field-tuning sound → resonant with{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
            </Link>{" "}
            (people in the same room are in different realities
            depending on what they are tuned to; the handpan
            tunes the room).
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://mudracafe.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          mudracafe.com
        </Link>
        {" · "}
        <Link
          href="https://maps.app.goo.gl/?q=Mudra+Cafe+Jl.+Goutama+Selatan+No.+21+Ubud"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Google Maps
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/elios" className="text-primary hover:underline">
          Elios
        </Link>
        {" · "}
        <Link
          href="/vision/lc-tending-over-producing"
          className="text-primary hover:underline"
        >
          lc-tending-over-producing
        </Link>
        {" · "}
        <Link
          href="/vision/lc-frequency-routes-reception"
          className="text-primary hover:underline"
        >
          lc-frequency-routes-reception
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ubud-meeting-walk.md
        </Link>
      </p>
    </>
  ),
};

export default content;
