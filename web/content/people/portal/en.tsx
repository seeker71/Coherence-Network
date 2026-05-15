import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "PORTAL — Partnership of Responsible Trippers | Coherence Network",
    description:
      "A welcome to PORTAL — the Denver-based initiative to destigmatize responsible psychedelic use. Hosts events at Red Rocks, Meow Wolf, and across the Denver psychedelic community.",
  },
  breadcrumbName: "PORTAL",
  hero: {
    image: { src: "/people/portal/hero.jpg" },
    eyebrow: "Welcome",
    name: "PORTAL",
    welcome: (
      <p>
        The Denver psychedelic community gathered as a single
        initiative — Partnership of Responsible Trippers Advocating
        for Legalization. Music, art, and shared rooms held in
        public; the Late-Night Takeover at Meow Wolf during MAPS
        2025 is where this body first walked through the door.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Psychedelic destigmatization · cultural integration · music + art events · advocacy",
    },
    {
      label: "Public",
      value: (
        <Link
          href="https://youaretheportal.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          youaretheportal.com
        </Link>
      ),
    },
    {
      label: "Recurring rooms",
      value:
        "Late-Night Takeovers at Meow Wolf Denver · presence at Red Rocks Amphitheatre · regular Denver-area events",
    },
    {
      label: "In this body's awareness",
      value:
        "Met Aubrey Marcus in the lobby at the PORTAL Late-Night Takeover at Meow Wolf Denver, June 19, 2025, during MAPS Psychedelic Science 2025 week.",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        PORTAL is an initiative rather than a single person — a
        different shape from the human profiles in this directory.
        Honored here because it functions as a kind of cell at
        collective scale: a community of organizers, artists, and
        advocates whose work is to keep specific public rooms open
        for the integration of psychedelic experience into ordinary
        civic life. The body relates to PORTAL the way it relates
        to other community-scale sovereigns — through the rooms
        it holds and the shared presence that flows through them.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What PORTAL holds",
      body: (
        <>
          <p>
            The shorthand on the marquee is *responsible
            psychedelic use*. The room PORTAL actually holds is
            wider: ecstatic dance, live music, ritual presence,
            policy advocacy, and the slow public-cultural work of
            moving psychedelic medicine from secrecy into shared
            civic life without losing the depth that secrecy had
            been protecting.
          </p>
          <p>
            The Late-Night Takeover at Meow Wolf during MAPS
            Psychedelic Science weeks is the most recognizable
            recurring instance. The venue (Meow Wolf is itself an
            immersive-art organism that lends well to this work)
            becomes a temporary container for several hundred
            bodies dancing, encountering each other in the
            hallways, and integrating the day's conference content
            somatically rather than analytically. PORTAL programs
            the music and the framing; the rest emerges from the
            field.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Recurring · MAPS Psychedelic Science weeks",
      heading: "Late-Night Takeover at Meow Wolf Denver",
      body: (
        <>
          <p>
            Two-night takeover (typically 10pm–2am) of the full
            Meow Wolf Denver immersive-art venue during MAPS
            Psychedelic Science conferences. Live DJ sets across
            the psychedelic-music space — past lineups have
            included{" "}
            <Link
              href="/people/bloomurian"
              className="text-primary hover:underline"
            >
              Bloomurian
            </Link>
            , Liquid Bloom, East Forest, Snow Raven, Māh Ze Tār,
            David Starfire, Öona Dahl, and others working in
            the ecstatic-dance / sound-medicine field.
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative octad — a closed-loop after-conference
            gathering where the day's intellectual content
            metabolizes into bodies through music and shared
            presence; the next morning's conference work is
            more grounded because of it.
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
          href="https://youaretheportal.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          youaretheportal.com
        </Link>
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; PORTAL's organizers
        are invited to replace any part of it with their own words
        at any time.
      </p>
    </>
  ),
};

export default content;
