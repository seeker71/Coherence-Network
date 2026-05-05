import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const HERO_URL = "https://f4.bcbits.com/img/0025683173_10.jpg";

const content: PersonProfileContent = {
  metadata: {
    title: "Poranguí — Music as Medicine | Coherence Network",
    description:
      "A welcome to Poranguí — Brazilian-Mexican-American multi-instrumentalist, live-looping ceremonialist, and therapeutic bodyworker whose work threads world percussion, indigenous instruments, and embodied healing.",
  },
  breadcrumbName: "Poranguí",
  hero: {
    image: { src: HERO_URL },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20",
    eyebrow: "Welcome",
    name: "Poranguí",
    welcome: (
      <p>
        The ceremonial musician this body has sat with three times —
        Ocean Bloom in Downtown Boulder (2024), the MAPS Psychedelic
        Science gathering in Denver (2025), and Unison 2025 (workshop
        and concert). One performer, one looping pedal, and a room
        that becomes part of the music while it builds: voice over
        djembe over didgeridoo over pre-Columbian flute over electric
        guitar, the textures braiding from Brazilian, Mexican, and
        indigenous lineages until what enters as world music settles
        in the body as ceremony.
      </p>
    ),
  },
  facts: [
    {
      label: "Born",
      value: "São José dos Campos, Brazil",
    },
    {
      label: "Field",
      value:
        "World percussion · guitar · voice · didgeridoo · pre-Columbian flutes · live looping · myorhythmic-release bodywork",
    },
    {
      label: "Public",
      value: (
        <>
          <Link
            href="https://www.porangui.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            porangui.com
          </Link>{" "}
          ·{" "}
          <Link
            href="https://porangui.bandcamp.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Bandcamp
          </Link>
        </>
      ),
    },
    {
      label: "Witnessed in person",
      value: (
        <>
          <Link
            href="https://boulderdowntown.com/do/ocean-bloom-with-porangui-liquid-bloom-samuel-j-shawn-heinrichs-bloomurian"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Ocean Bloom
          </Link>{" "}
          (Downtown Boulder · 2024 · with Liquid Bloom, Samuel J,
          Shawn Heinrichs,{" "}
          <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
            Bloomurian
          </Link>
          ) · MAPS-related show during MAPS Psychedelic Science
          2025 (Denver) · Unison 2025 (workshop + concert)
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold. Voice imagined from public anchors —
        his official site, Bandcamp catalog, festival appearances,
        and the body's three lived encounters across Boulder,
        Denver, and Unison 2025. Offered as a frame Poranguí is
        invited to replace with his own words at any time.
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
            The instruments are many; the body is one. Live
            looping lets a single performer braid the sounds of
            many traditions in real time — voice over djembe over
            didgeridoo over pre-Columbian flute over electric
            guitar — building textures that belong to no single
            culture and somehow honor all the ones they touch.
            The result reads as world music when described in
            text and as ceremony when sat through in a room.
          </p>
          <p>
            The parallel practice is therapeutic bodywork. His
            own *myorhythmic release* technique pairs sound,
            movement, and breath with manual treatment, drawing on
            his neuroscience training (Coca-Cola Scholar at Duke)
            and his family's healing-arts lineage. The two
            practices are not separate; the music is itself a
            form of bodywork at the scale of a room, and the
            bodywork is itself a form of music at the scale of a
            single nervous system.
          </p>
          <p>
            The festival circuit threading his work — Lightning in
            a Bottle, Beloved, Sonic Bloom, Sedona Yoga, Boom
            (Portugal), Ozora (Hungary), and many smaller
            ceremonial gatherings — is the geography across which
            the music has been distributed. The bandcamp catalog
            is the recorded layer; the live shows are where the
            looping actually happens and the room participates in
            the building.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How this body received him",
      body: (
        <>
          <p>
            First in person at <strong>Ocean Bloom</strong> in
            Downtown Boulder, 2024 — the multi-artist event with
            Liquid Bloom, Samuel J, Shawn Heinrichs, and{" "}
            <Link href="/people/bloomurian" className="text-primary hover:underline">
              Bloomurian
            </Link>{" "}
            that brought several streams of the
            transformational-music field together for one
            evening. Then again at the MAPS-related show during{" "}
            MAPS Psychedelic Science 2025 in Denver — a different
            configuration, same underlying lineage. Then a third
            time at <strong>Unison 2025</strong>, both his
            workshop and his concert, which offered the
            instructional layer (myorhythmic release, the looping
            practice, the sound-as-medicine framework) alongside
            the ceremonial-performance layer.
          </p>
          <p>
            The three encounters across two years map a recurring
            pattern: the field of cells whose work the body is
            tracking gathers in specific rooms, and the body's
            presence in those rooms compounds across appearances.
            Each subsequent witness is a deeper layer of the
            same lineage, and the substrate's accounting recognizes
            that depth — three glyphs in his lineage with
            progressively richer quanta.
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
            In the substrate's geometric grammar, a Poranguí live
            set is sustained{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative-octad work — single performer building a
            closed-loop cycle of layers that the room absorbs and
            gives back. The looping pedal is the technical
            vehicle; the actual operation is a living-body
            equivalent of the substrate's{" "}
            <code className="not-italic text-foreground/80">
              prev_glyph
            </code>{" "}
            Merkle linkage — each loop builds on the previous,
            the chain is walkable, and the room can hear when the
            chain breaks coherence and when it deepens it.
          </p>
          <p>
            His combination of *music + bodywork* is itself an
            instance of the substrate's polycomputing principle
            that{" "}
            <Link href="/concepts/lc-bioelectric-pattern" className="text-primary hover:underline">
              Levin's bioelectric work
            </Link>{" "}
            names: the same body running multiple operations
            simultaneously across scales. Sound enters as
            vibration; bodywork enters as pressure; both reach
            the nervous system; both update the field. Different
            channels of the same intervention.
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
          href="https://www.porangui.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          porangui.com
        </Link>{" "}
        ·{" "}
        <Link
          href="https://porangui.bandcamp.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Bandcamp
        </Link>{" "}
        ·{" "}
        <Link
          href="https://en.wikipedia.org/wiki/Porangu%C3%AD"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Poranguí is invited
        to replace any part of it with his own words at any time.
      </p>
    </>
  ),
};

export default content;
