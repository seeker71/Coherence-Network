import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const HERO_BACKGROUND =
  "radial-gradient(ellipse at 30% 20%, rgba(255, 196, 140, 0.55) 0%, rgba(255, 158, 110, 0.32) 22%, rgba(212, 132, 176, 0.28) 45%, rgba(120, 92, 168, 0.32) 68%, rgba(36, 28, 64, 0.85) 100%), linear-gradient(180deg, rgba(255, 210, 165, 0.18) 0%, rgba(180, 120, 170, 0.22) 38%, rgba(40, 36, 80, 0.92) 100%)";

const content: PersonProfileContent = {
  metadata: {
    title: "Aly Constantine — Conscious Roots Presents | Coherence Network",
    description:
      "A welcome to Aly Constantine — co-founder of Boulder Ecstatic Dance, curatorial cell behind Conscious Roots Presents, key connector for the music entering Rise & Vibes and Unison festivals, and co-host with Rocco of the Courtyard Constellations gatherings at their Boulder home.",
  },
  breadcrumbName: "Aly Constantine",
  hero: {
    background: HERO_BACKGROUND,
    eyebrow: "Welcome",
    name: "Aly Constantine",
    welcome: (
      <p>
        Co-founder of{" "}
        <Link
          href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Boulder Ecstatic Dance
        </Link>
        {" "}and the curatorial cell behind{" "}
        <Link
          href="https://www.facebook.com/ConsciousRootsPresents/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Conscious Roots Presents
        </Link>
        {" "}— the Boulder vessel co-creating evenings of music and
        connection with artists who carry a message to uplift the
        community. A key connector for the music flowing into the{" "}
        <strong>Rise &amp; Vibes</strong> and{" "}
        <strong>Unison</strong> festivals, and co-host with her
        husband{" "}
        <Link
          href="/people/rocco-tortorella"
          className="text-primary hover:underline"
        >
          Rocco
        </Link>
        {" "}of the recurring{" "}
        <strong>Courtyard Constellations</strong> gatherings at their
        Boulder home. Deeply woven into{" "}
        <Link
          href="/people/bloomurian"
          className="text-primary hover:underline"
        >
          Bloomurian's
        </Link>{" "}
        circle, the{" "}
        <Link
          href="/people/porangui"
          className="text-primary hover:underline"
        >
          Ocean Bloom
        </Link>{" "}
        configuration, and the wider Boulder–Denver
        transformational-music ecology.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Ecstatic-dance facilitation · curatorial production · community-tending · transformational-music ecology",
    },
    {
      label: "Curates",
      value: (
        <>
          <Link
            href="https://www.facebook.com/ConsciousRootsPresents/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Conscious Roots Presents
          </Link>
          {" "}— Boulder, Colorado · co-creating evenings of music and
          connection with artists whose message uplifts the community ·
          recurring collaborator with Boulder Ecstatic Dance
        </>
      ),
    },
    {
      label: "Held with",
      value: (
        <>
          <Link
            href="/people/rocco-tortorella"
            className="hover:text-primary transition-colors"
          >
            Rocco
          </Link>{" "}
          as husband and co-host of Courtyard Constellations;{" "}
          <strong>Danny Balgooyen</strong> and{" "}
          <Link
            href="/people/bloomurian"
            className="hover:text-primary transition-colors"
          >
            Robin Liepman (Bloomurian)
          </Link>{" "}
          as fellow Boulder Ecstatic Dance co-founders and Sunday-
          morning tenders; close shared friendships with{" "}
          <Link
            href="/people/brigitte-mars"
            className="hover:text-primary transition-colors"
          >
            Brigitte Mars
          </Link>
          , <strong>Tay Blevons</strong> (
          <Link
            href="/people/portal"
            className="hover:text-primary transition-colors"
          >
            PORTAL
          </Link>
          ), <strong>Andy Babb</strong> and{" "}
          <strong>Lara Elle</strong> (
          <Link
            href="/people/rhythm-sanctuary"
            className="hover:text-primary transition-colors"
          >
            Rhythm Sanctuary
          </Link>
          ); presence woven through Rise &amp; Vibes, Unison, and
          Ocean Bloom; one of the cells who has consistently brought{" "}
          <Link
            href="/people/mose"
            className="hover:text-primary transition-colors"
          >
            Mose
          </Link>
          ,{" "}
          <Link
            href="/people/porangui"
            className="hover:text-primary transition-colors"
          >
            Poranguí
          </Link>
          ,{" "}
          <Link
            href="/people/liquid-bloom"
            className="hover:text-primary transition-colors"
          >
            Liquid Bloom
          </Link>
          , and the wider transformational-music family into Boulder
          rooms
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
          — Avalon Ballroom and Congregation Nevei Kodesh, Boulder ·
          Conscious Roots Presents nights · Courtyard Constellations
          (the home gatherings she and Rocco host) · Rise &amp; Vibes ·
          Ocean Bloom · Unison
        </>
      ),
    },
    {
      label: "In this body's awareness",
      value: (
        <>
          <Link
            href="/people/urs"
            className="hover:text-primary transition-colors"
          >
            Urs
          </Link>{" "}
          lived as a houseguest at Aly and Rocco's Boulder home from{" "}
          <strong>February 2025 through December 2025</strong>,
          witnessing the constellation — Conscious Roots, Boulder
          Ecstatic Dance, Rise &amp; Vibes, Unison, Courtyard
          Constellations — from inside the household that anchors much
          of it.
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold. Aly is one of the most connected cells in
        this network's Boulder configuration: Conscious Roots Presents
        is hers, the Sunday-morning ballroom is hers to co-tend, the
        Courtyard Constellations gatherings happen at the home she
        keeps with Rocco, and the music flowing into Rise &amp; Vibes
        and Unison moves through her hands. Many of the artists this
        body has come to know — Robin (Bloomurian) most directly, but
        also Mose, Poranguí, Liquid Bloom — entered our awareness
        through rooms she helped build. Urs lived as a houseguest at
        Aly and Rocco's home from February through December 2025, so
        the network's reading of this whole configuration is an
        inside-the-household reading, not an outside one. Aly is
        invited to replace any part of this page with her own words at
        any time.
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
            Several vessels, threading. <strong>Boulder Ecstatic
            Dance</strong> is the recurring Sunday-morning room — at
            the Avalon Ballroom, sometimes at Congregation Nevei
            Kodesh — that Aly co-founded at the beginning. The room
            is now co-tended week to week with Danny and with{" "}
            <Link
              href="/people/bloomurian"
              className="text-primary hover:underline"
            >
              Robin (Bloomurian)
            </Link>
            ; the three of them hold the space, the music, the
            welcoming, the timing, the closing circles. The DJ is the
            visible hand; the hosts' field-tending is what makes the
            room safe enough for bodies to drop in.
          </p>
          <p>
            <strong>Conscious Roots Presents</strong> is her own
            curatorial vessel — the Boulder-based event production
            line that "co-creates evenings of music and connection
            with artists who share music with a message to uplift
            their community." The wider Boulder ecstatic-dance ecology
            and the conscious-music nights that intersect with it move
            through her hands: Bloomurian's sets land inside the rooms
            she helps build, the visiting medicine-music artists
            touring through Colorado are met by the container she has
            shaped, and the constellation of cells that gathers for{" "}
            <Link
              href="/people/porangui"
              className="text-primary hover:underline"
            >
              Ocean Bloom
            </Link>{" "}
            (the immersive visual-concert experience with Poranguí,
            Liquid Bloom, Samuel J, Bloomurian, Shawn Heinrichs and
            others), for the <strong>Rise &amp; Vibes</strong> and{" "}
            <strong>Unison</strong> festivals, and for the broader
            Boulder–Denver transformational-music gatherings is the
            same configuration Conscious Roots Presents holds inside
            its curatorial field. Much of the music landing on those
            festival stages enters through her connecting work.
          </p>
          <p>
            <strong>Courtyard Constellations</strong> is the home
            vessel — the gatherings Aly and{" "}
            <Link
              href="/people/rocco-tortorella"
              className="text-primary hover:underline"
            >
              Rocco
            </Link>{" "}
            host at their Boulder house, where the same constellation
            of musicians, dancers, and conscious-community cells that
            fills the ballrooms and the festival fields gathers in a
            domestic-scale courtyard for music, food, and direct
            relation. The household is one of the quiet anchors of the
            Boulder configuration.
          </p>
          <p>
            Curatorial work, ecstatic-dance founding, and home-
            gathering hosting are not separate practices for her. They
            are one practice across three scales — the same field-
            tending sensitivity that decides which artists belong in
            the same room opens and closes the Sunday wave and shapes
            who is welcomed into the courtyard.
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
            Through the household. After Urs's January–February 2025
            stay in the Boulder mountains with{" "}
            <Link
              href="/people/bloomurian"
              className="text-primary hover:underline"
            >
              Robin (Bloomurian)
            </Link>
            {" "}— the same house{" "}
            <Link
              href="/people/liquid-bloom"
              className="text-primary hover:underline"
            >
              Amani Friend (Liquid Bloom)
            </Link>{" "}
            had once lived in — Aly and Rocco opened their Boulder
            home as the next place to land. Urs lived as a houseguest
            from <strong>February 2025 through December 2025</strong>:
            ten months at the address where Conscious Roots is
            curated, where Boulder Ecstatic Dance is co-tended, and
            where the Courtyard Constellations gather. After the
            houseguest months, this body remained in the Boulder–
            Longmont area until the April 2026 departure for Bali.
          </p>
          <p>
            Through Aly and that household, the body's awareness of
            the Boulder / Bloomurian / Ocean Bloom / Rise &amp; Vibes
            / Unison / Conscious Roots constellation is not an outside
            reading. It is an inside-the-house reading — a witness
            channel from the kitchen and the courtyard, not from the
            audience. Cells we encounter through living under the same
            roof show us the field they belong to from inside its own
            self-perception. That kind of knowing cannot be replicated
            by media research. It is its own substrate channel.
          </p>
          <p>
            The Boulder arc closed in the same form it began: in the
            home, around the constellation. On{" "}
            <strong>April 18, 2026</strong>,{" "}
            <Link
              href="/people/rocco-tortorella"
              className="text-primary hover:underline"
            >
              Rocco's
            </Link>{" "}
            36th birthday gathered all the close friends into one
            jungle-themed evening of celebration in the courtyard —
            two days before this body's departure for Bali on April
            20, 2026. For this body, that night was the most divine
            goodbye to the Boulder chapter that could have been
            imagined.
          </p>
          <p>
            The texture of those household months is held with care.
            The substrate's recording of it is brief on purpose —
            what is shared publicly is the existence of the household
            as the witnessing point and the recognition of Aly's role
            in the field. What is not shared publicly is the daily
            texture of the household itself, which belongs to the
            cells in it and not to the substrate's reader.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Curatorial vessel · Boulder",
      heading: "Conscious Roots Presents",
      body: (
        <>
          <p>
            The Boulder-based production line through which Aly
            curates evenings of music and connection — collaborating
            with Boulder Ecstatic Dance on shared bills, hosting
            visiting medicine-music artists, weaving local Boulder-
            Denver talent into rooms where the audience knows what
            kind of evening they are walking into.{" "}
            <Link
              href="https://www.facebook.com/ConsciousRootsPresents/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              facebook.com/ConsciousRootsPresents
            </Link>{" "}
            holds the public face of the work; Boulder Ecstatic
            Dance's Instagram and Conscious Roots cross-tag each
            other on co-curated nights.
          </p>
          <p>
            The cells whose names recur in the Conscious Roots
            curatorial weave are the same cells the rest of this
            network recognizes:{" "}
            <Link
              href="/people/bloomurian"
              className="text-primary hover:underline"
            >
              Bloomurian
            </Link>{" "}
            most steadily,{" "}
            <Link
              href="/people/mose"
              className="text-primary hover:underline"
            >
              Mose
            </Link>
            ,{" "}
            <Link
              href="/people/porangui"
              className="text-primary hover:underline"
            >
              Poranguí
            </Link>
            ,{" "}
            <Link
              href="/people/liquid-bloom"
              className="text-primary hover:underline"
            >
              Liquid Bloom
            </Link>
            , and the wider family that travels between Atitlán,
            Boulder, Tulum, and the festival circuit. Conscious Roots
            is one of the gates through which their work reaches
            Boulder bodies — and through which Boulder bodies meet
            their work for the first time.
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
            Sunday-morning ecstatic-dance gathering at the Avalon
            Ballroom (and historically at Congregation Nevei Kodesh
            and other Boulder venues). Co-founded by Aly at the
            beginning, now co-tended week to week with Danny and
            Robin (
            <Link
              href="/people/bloomurian"
              className="text-primary hover:underline"
            >
              Bloomurian
            </Link>
            ) along with rotating guest DJs. Free-form embodied
            movement, opening and closing circles, no shoes, no
            talking on the dance floor — the standard ecstatic-dance
            container, held with Boulder's particular flavor of
            conscious-community presence. The form threads back twenty
            years through Shannon Lei Gill's{" "}
            <Link
              href="https://www.rhythmsanctuary.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Rhythm Sanctuary
            </Link>{" "}
            lineage and the Gabrielle Roth wave that shaped Boulder
            ecstatic dance.
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
            regenerative octad — a closed-loop weekly cycle where the
            city's dancers metabolize the week's accumulation through
            movement. The hosts' role is the field-coherence layer
            that lets the cycle close cleanly each Sunday.
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
          href="https://www.facebook.com/ConsciousRootsPresents/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Conscious Roots Presents
        </Link>{" "}
        ·{" "}
        <Link
          href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Boulder Ecstatic Dance
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
        This profile is a welcoming scaffold; Aly is invited to
        replace any part of it with her own words at any time. The
        texture of the household months is held privately and is not
        part of the substrate's public rendering.
      </p>
    </>
  ),
};

export default content;
