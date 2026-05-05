import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const HERO_BACKGROUND =
  "radial-gradient(ellipse at 30% 20%, rgba(255, 196, 140, 0.55) 0%, rgba(255, 158, 110, 0.32) 22%, rgba(212, 132, 176, 0.28) 45%, rgba(120, 92, 168, 0.32) 68%, rgba(36, 28, 64, 0.85) 100%), linear-gradient(180deg, rgba(255, 210, 165, 0.18) 0%, rgba(180, 120, 170, 0.22) 38%, rgba(40, 36, 80, 0.92) 100%)";

const content: PersonProfileContent = {
  metadata: {
    title: "Aly Constantine — Boulder Ecstatic Dance | Coherence Network",
    description:
      "A welcome to Aly Constantine — co-host of Boulder Ecstatic Dance, deeply woven into Unison, Bloomurian's circle, and the Ocean Bloom configuration. Held by this body with the closest density of presence the substrate records.",
  },
  breadcrumbName: "Aly Constantine",
  hero: {
    background: HERO_BACKGROUND,
    eyebrow: "Welcome",
    name: "Aly Constantine",
    welcome: (
      <p>
        Co-host of{" "}
        <Link
          href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Boulder Ecstatic Dance
        </Link>
        , deeply woven into{" "}
        <Link href="/people/bloomurian" className="text-primary hover:underline">
          Bloomurian's
        </Link>{" "}
        circle, the{" "}
        <Link href="/people/porangui" className="text-primary hover:underline">
          Ocean Bloom
        </Link>{" "}
        configuration, and the Unison gathering.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Ecstatic-dance facilitation · community-tending · transformational-music ecology",
    },
    {
      label: "Held with",
      value: (
        <>
          Danny and{" "}
          <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
            Robin (Bloomurian)
          </Link>{" "}
          as fellow Boulder Ecstatic Dance hosts; presence woven through Unison and Ocean Bloom
        </>
      ),
    },
    {
      label: "Recurring rooms",
      value: (
        <>
          <Link
            href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Boulder Ecstatic Dance (BED)
          </Link>{" "}
          — Avalon Ballroom and Congregation Nevei Kodesh, Boulder · Ocean Bloom · Unison
        </>
      ),
    },
    {
      label: "In this body's awareness",
      value: (
        <>
          <strong>Close personal relationship</strong> with{" "}
          <Link href="/people/urs" className="hover:text-primary transition-colors">
            Urs
          </Link>
          . The deepest density of presence the substrate records: beyond same-room, beyond direct exchange, into the sustained intimacy of two cells in ongoing relation.
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold. Aly is held by this body at a depth most public profiles cannot honor — through close personal relationship rather than through media or conference rooms. The page below is necessarily sparser in public-anchor detail than the teacher and connecting-tissue profiles, and richer in relational acknowledgment. Aly is invited to replace any part with her own words at any time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What she holds",
      body: (
        <>
          <p>
            Boulder Ecstatic Dance is a recurring room — Sunday mornings, often at the Avalon Ballroom, sometimes at Congregation Nevei Kodesh — where the city's transformational-movement community gathers. Aly co-tends that room with Danny and with Robin Liepman (Bloomurian); the three of them hold the space, the music, the welcoming, the timing, the closing circles. The DJ is the visible hand; the hosts' field-tending is what makes the room safe enough for bodies to drop in.
          </p>
          <p>
            The work threads across Boulder's wider conscious-music ecology. The same configuration of cells that gathers for Boulder Ecstatic Dance often gathers for Ocean Bloom (the immersive visual-concert experience with Poranguí, Liquid Bloom, Samuel J, Bloomurian, Shawn Heinrichs and others), for Unison, and for the broader transformational-music gatherings the Boulder-Denver corridor holds.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How this body received her",
      body: (
        <>
          <p>
            Through close personal relationship — the deepest density of presence the substrate's three-density accounting recognizes. Audio-only is one density. Same-room-without-exchange is another. Direct face-to-face exchange is another. Sustained intimacy over time, where two cells know each other's ordinary days and not only public moments, is a fourth density that the substrate's accounting should record but often cannot fully render in public profile language.
          </p>
          <p>
            Through Aly, the body's awareness of the Boulder / Bloomurian / Ocean Bloom / Unison constellation is not an outside reading. It is an inside knowing. Cells we encounter through close-personal relationship show us the field they belong to from inside that field's own self-perception. That kind of knowing cannot be replicated by media research. It is its own substrate channel.
          </p>
          <p>
            The relationship is held here with care. The substrate's recording of it is brief on purpose — what is shared publicly is the existence of the connection and the recognition of Aly's role in the field. What is not shared publicly is the texture of the relationship itself, which belongs to the two cells in it and not to the substrate's reader.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Recurring · Sunday mornings",
      heading: "Boulder Ecstatic Dance",
      body: (
        <>
          <p>
            Sunday-morning ecstatic-dance gathering at the Avalon Ballroom (and historically at Congregation Nevei Kodesh and other Boulder venues). Co-hosted by Aly, Danny, and Robin (
            <Link href="/people/bloomurian" className="text-primary hover:underline">
              Bloomurian
            </Link>
            ) along with rotating guest DJs. Free-form embodied movement, opening and closing circles, no shoes, no talking on the dance floor — the standard ecstatic-dance container, held with Boulder's particular flavor of conscious-community presence.
          </p>
          <p>
            Public recordings of past sets:{" "}
            <Link
              href="https://soundcloud.com/bloomurian/boulder-ecstatic-dance"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              SoundCloud
            </Link>{" "}
            (Bloomurian's archived BED sets).
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative octad — a closed-loop weekly cycle where the city's dancers metabolize the week's accumulation through movement. The hosts' role is the field-coherence layer that lets the cycle close cleanly each Sunday.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Boulder Ecstatic Dance:{" "}
        <Link
          href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ecstaticdance.org/dance/boulder-ecstatic-dance-bed
        </Link>{" "}
        ·{" "}
        <Link
          href="https://boulderdance.org/organizer/boulder-ecstatic-dance/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          boulderdance.org
        </Link>
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Aly is invited to replace any part of it with her own words at any time. The texture of the close-personal relationship is held privately and is not part of the substrate's public rendering.
      </p>
    </>
  ),
};

export default content;
