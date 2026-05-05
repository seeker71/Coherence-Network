import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Bloomurian — Robin Liepman | Coherence Network",
    description:
      "A welcome to Bloomurian (Robin Liepman) — Boulder/Colorado-based DJ and live performer in the ecstatic-dance, transformational-music, and psychedelic-music space.",
  },
  breadcrumbName: "Bloomurian",
  hero: {
    image: { src: "/people/bloomurian/hero.jpg" },
    eyebrow: "Welcome",
    name: "Bloomurian",
    welcome: (
      <p>
        Robin Liepman at the booth — weaving ecstatic dance, world
        bass, trip-hop, psy-dub, and the shovel-slide guitar into
        sets that read the room and steer the spaceship across
        festivals, dance floors, and psychedelic-community
        gatherings.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Ecstatic-dance DJ · live performer · transformational music · sound medicine",
    },
    {
      label: "Based",
      value: "Boulder, Colorado (originally California)",
    },
    {
      label: "Public",
      value: (
        <>
          <Link
            href="https://www.bloomurian.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            bloomurian.com
          </Link>{" "}
          ·{" "}
          <Link
            href="https://bloomurian.bandcamp.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Bandcamp
          </Link>{" "}
          ·{" "}
          <Link
            href="https://ecstaticdance.org/dj/bloomurian/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Ecstatic Dance
          </Link>
        </>
      ),
    },
    {
      label: "Witnessed in person",
      value: (
        <>
          Performing at the{" "}
          <Link href="/people/portal" className="hover:text-primary transition-colors">
            PORTAL Late-Night Takeover
          </Link>{" "}
          at Meow Wolf Denver — June 19, 2025, during MAPS
          Psychedelic Science 2025 week
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold. Voice imagined from public anchors —
        his own site, ecstatic-dance DJ profile, festival
        appearances, and the body's lived encounter at PORTAL's
        Meow Wolf takeover. Offered as a frame Robin is invited
        to replace with his own words at any time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What he holds",
      body: (
        <>
          <p>
            The DJ booth as ceremonial seat. The work of weaving
            tracks across an evening — original productions,
            collaborations, remixes, tasteful selections from the
            wider transformational-music field — into a sonic
            tapestry that reads the room and steers the
            spaceship. The role asks for technical mastery and
            also for something else: the willingness to be in
            service to the field's energy rather than to a
            pre-planned set.
          </p>
          <p>
            His sound moves across ecstatic dance, world bass,
            trip-hop, glitchy psy-dub, and what his bio names
            "face-melting, heart-opening, soul-awakening
            multidimensional frequencies." The shovel-slide
            guitar — yes, an actual shovel used as a slide-guitar
            — appears in live sets. Live instrumentalists and
            vocalists join when the venue allows.
          </p>
          <p>
            The work is local-rooted (Boulder, Colorado, with
            Denver-area presence) and globally distributed (he DJs
            ecstatic dances, concerts, festivals, and retreats
            worldwide). His Bandcamp holds the recorded body of
            work; the live shows are where the field-reading
            actually happens.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How the network reads this",
      body: (
        <>
          <p>
            In the substrate's geometric grammar, an ecstatic-
            dance DJ set is a sustained{" "}
            <code className="not-italic text-foreground/80">
              (6, …)
            </code>{" "}
            hexagonal harmonic — many bodies tiling into shared
            rhythm — with frequent passages through{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative-octad cycles as the energy builds and
            releases across the night. The DJ's role is to read
            the field and steer the cycles; the crowd's role is to
            follow the steering with embodied presence.
          </p>
          <p>
            Bloomurian's specific contribution to this body's
            awareness threads through the Boulder /
            Colorado-Front-Range music ecology and the broader
            psychedelic-community-events field. The June 19,
            2025 set at Meow Wolf was the moment his work entered
            this body's direct lived awareness; his recorded
            catalog is the lineage walking back from that night.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Public:{" "}
        <Link
          href="https://www.bloomurian.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          bloomurian.com
        </Link>{" "}
        ·{" "}
        <Link
          href="https://bloomurian.bandcamp.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Bandcamp
        </Link>{" "}
        ·{" "}
        <Link
          href="https://www.beatport.com/artist/bloomurian/992761"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Beatport
        </Link>
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Robin is invited to
        replace any part of it with his own words at any time.
      </p>
    </>
  ),
};

export default content;
