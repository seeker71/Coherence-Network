import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Elios — Sunday Spontaneous Chanting at Ranakami | Coherence Network",
    description:
      "A welcome to Elios — co-holding the spontaneous Sunday-night chanting practice at Ranakami in Ubud, with Ilena. Met at Mudra Cafe.",
  },
  breadcrumbName: "Elios",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 15%, hsl(35 70% 62% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 20% 85%, hsl(160 45% 22% / 0.65) 0%, transparent 60%), linear-gradient(180deg, hsl(28 55% 70%) 0%, hsl(150 30% 35%) 45%, hsl(160 50% 18%) 100%)",
    eyebrow: "Ubud · Sunday rhythm",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Elios",
    welcome: (
      <p>
        Held within the Ubud rhythm of Coherence Network — co-holding
        the spontaneous Sunday-night chanting practice at{" "}
        <Link
          href="/people/ilena"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          Ranakami
        </Link>{" "}
        with Ilena. The page below carries what the body has met of
        him so far; everything here is his to refine.
      </p>
    ),
  },
  facts: [
    {
      label: "Sunday · evening",
      value:
        "Spontaneous chanting at Ranakami — Jl. Raya Penestanan Kelod 16, Sayan, Ubud · with Ilena",
    },
    {
      label: "Often found at",
      value: (
        <>
          <Link
            href="https://mudracafe.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[hsl(var(--primary))] transition-colors"
          >
            Mudra Cafe
          </Link>{" "}
          — Jl. Goutama Sel. No. 21, Ubud
        </>
      ),
    },
    {
      label: "Field",
      value: "Voice · chanting · spontaneous practice · presence",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        The body's first profile written almost entirely from a lived
        encounter rather than from public anchors. A network cell met
        Elios at Mudra Cafe on a Sunday afternoon, then attended the
        spontaneous Sunday-night chanting practice he co-holds with
        Ilena at Ranakami. The page is sparse on purpose — Elios is
        invited to replace any part with his own words at any time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Where the body meets him",
      body: (
        <>
          <p>
            Sunday afternoons often find Elios at Mudra Cafe — the
            Ayurvedic dining room on Jl. Goutama Sel. that holds
            regular handpan and live-music presence and has become
            one of Ubud's quiet meeting points for those tracking
            wellness, music, and slow community. Sunday evenings,
            he and Ilena open the spontaneous chanting practice at
            Ranakami above the rice fields in Sayan — voices,
            breath, bodies, an open room, no fixed setlist, the
            field shaping the song.
          </p>
          <p>
            The Sunday rhythm in Ubud, as the body has been
            discovering it: lunch or afternoon at Mudra Cafe,
            dinner with resonant company at Sayuri Healing Food,
            evening chanting at Ranakami. The pattern is not a
            schedule anyone advertised; it is a current that
            several cells have found by following the field.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Sunday · evening",
      heading: "Spontaneous chanting at Ranakami",
      body: (
        <>
          <p>
            Held with Ilena at Ranakami's open-air room.
            Spontaneous rather than programmed — voices arrive,
            the song emerges, the practice unfolds for as long as
            the field holds. Distinct from{" "}
            <Link
              href="/people/vasudev-baba"
              className="text-[hsl(var(--primary))] hover:underline"
            >
              Vasudev Baba's
            </Link>{" "}
            Wednesday-morning satsang and his Sunday-evening
            kirtan at Sayuri — same valley, different practice,
            same openness to whoever arrives in coherent state.
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (6, RECEIVE / GIVE oscillating)
            </code>{" "}
            — hexagonal tiling of voices, but improvisational
            rather than traditional, so the geometry sometimes
            bends through{" "}
            <code className="not-italic text-foreground/80">
              (7, GIVE)
            </code>{" "}
            heptadic moments where someone's voice opens a
            direction no one was tracking.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Sunday chanting held at{" "}
        <Link
          href="/people/ilena"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          Ranakami
        </Link>
        , Ubud. Mudra Cafe on{" "}
        <Link
          href="https://mudracafe.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          mudracafe.com
        </Link>
        .
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Elios is invited to
        replace any part of it with his own words at any time.
        Direct contact details, a fuller name, and his own framing of
        the practice will land here as he chooses.
      </p>
    </>
  ),
};

export default content;
