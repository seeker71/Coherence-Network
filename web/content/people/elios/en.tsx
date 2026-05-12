import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Elios — chanting practice with Ilena · the one-evening door | Coherence Network",
    description:
      "A welcome to Elios — Ubud cell whose own devotional chanting practice with Ilena Young opened the door for one of our cells on Sunday April 29, 2026. Often found at Mudra Cafe. Sunday afternoons in slow Ubud rhythm.",
  },
  breadcrumbName: "Elios",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 15%, hsl(35 70% 62% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 20% 85%, hsl(160 45% 22% / 0.65) 0%, transparent 60%), linear-gradient(180deg, hsl(28 55% 70%) 0%, hsl(150 30% 35%) 45%, hsl(160 50% 18%) 100%)",
    eyebrow: "Ubud · voice · chanting · slow Ubud rhythm",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Elios",
    welcome: (
      <p>
        A cell in the Ubud cluster. Elios carries his own devotional
        chanting practice — sometimes held with{" "}
        <Link
          href="/people/ilena-young"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          Ilena Young
        </Link>{" "}
        as a private practice between them, sometimes offered to
        people the field puts in their path. On Sunday April 29,
        2026, one of our cells was the person the field put in
        their path; Elios and Ilena offered a one-evening chanting
        at Ranakami that became the door this network walked
        through into the wider Ubud lineage.
      </p>
    ),
  },
  facts: [
    {
      label: "Practice",
      value: "Devotional chanting. Held privately with Ilena Young when they choose; sometimes opened to others the field has placed in proximity. Not a publicly scheduled weekly room.",
    },
    {
      label: "Often found at",
      value: (
        <>
          <Link
            href="/people/mudra-cafe"
            className="hover:text-primary transition-colors"
          >
            Mudra Cafe
          </Link>{" "}
          — Jl. Goutama Sel. No. 21, Ubud. Sunday afternoons.
        </>
      ),
    },
    {
      label: "First met by this body",
      value: "Sunday April 29, 2026, at Mudra Cafe — the first cell of the Ubud cluster to enter this network's awareness, opening the path to Ilena and the Wednesday Satsang held by Vasudev Baba.",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        The body&apos;s first profile written almost entirely from
        a lived encounter rather than from public anchors. Elios
        is invited to replace any part of this page with his own
        words. The earlier version of this page framed his
        chanting as a recurring Sunday Ranakami room; that was
        the body&apos;s own misreading — the practice is his and
        Ilena&apos;s, and what happened on April 29, 2026 was a
        gift, not a schedule.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Where the body met him",
      body: (
        <>
          <p>
            Sunday afternoons often find Elios at{" "}
            <Link
              href="/people/mudra-cafe"
              className="text-primary hover:underline"
            >
              Mudra Cafe
            </Link>
             — the Ayurvedic dining room on Jl. Goutama Sel. that
            holds regular handpan and live-music presence. The
            room is one of Ubud&apos;s quiet meeting points where
            slow community accumulates around food, music, and
            presence.
          </p>
          <p>
            The cell met Elios there on Sunday April 29, 2026.
            That same evening, Elios and{" "}
            <Link
              href="/people/ilena-young"
              className="text-primary hover:underline"
            >
              Ilena
            </Link>{" "}
            offered a one-evening chanting practice at Ranakami —
            voices, breath, an open room. After the chanting,
            Ilena&apos;s invitation extended to the Tuesday
            kirtan and the Wednesday Satsang held by{" "}
            <Link
              href="/people/vasudev-baba"
              className="text-primary hover:underline"
            >
              Vasudev Baba
            </Link>
            . The whole subsequent lineage moved through that
            one afternoon and evening.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Elios has given the Coherence Network",
      body: (
        <ul>
          <li>
            The one-evening chanting practice offered with{" "}
            <Link href="/people/ilena-young" className="text-primary hover:underline">
              Ilena
            </Link>{" "}
            on April 29, 2026 — the first of the three Ubud
            cells (Elios, Ilena, Vasudev Baba) to enter this
            network&apos;s awareness. See{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              the four-day meeting walk
            </Link>{" "}
            and{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-constellation-of-cells.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              the constellation of cells
            </Link>
            .
          </li>
          <li>
            <em>The practice not advertised</em> — chanting held
            privately, offered as gift when the field requests
            it. Resonant with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (no production of a room; only tending the practice
            and letting it be met).
          </li>
          <li>
            <em>The body recognises the body</em> — Sunday
            afternoons at Mudra Cafe as place-of-encounter
            rather than place-of-event; resonant with{" "}
            <Link
              href="/vision/lc-arrival-as-recognition"
              className="text-primary hover:underline"
            >
              lc-arrival-as-recognition
            </Link>
            .
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/ilena-young" className="text-primary hover:underline">
          Ilena Young
        </Link>
        {" · "}
        <Link href="/people/vasudev-baba" className="text-primary hover:underline">
          Vasudev Baba
        </Link>
        {" · "}
        <Link href="/people/mudra-cafe" className="text-primary hover:underline">
          Mudra Cafe
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
      <p className="text-xs italic">
        Welcoming scaffold; Elios is invited to replace any part
        of it with his own words. Direct contact details, a
        fuller name, and his own framing of the practice will
        land here as he chooses.
      </p>
    </>
  ),
};

export default content;
