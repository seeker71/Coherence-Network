import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Liquid Bloom — The Doorway Frequency",
    description:
      "Liquid Bloom — Amani Friend's solo journey-music project, half of Desert Dwellers, scoring two decades of ecstatic-dance and ceremonial sound. The doorway through which this body found Mose, the first Pagan Ritual at Vali Soul Sanctuary, Tammy Beattie's Ecstatic Movement Tribe, and Contact Improv.",
  },
  breadcrumbName: "Liquid Bloom",
  hero: {
    image: { src: "/presences/liquid-bloom-hero.jpg", objectPosition: "center 30%" },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/70 to-background/10",
    eyebrow: "The doorway frequency",
    eyebrowClass: "text-[hsl(var(--primary))]",
    name: "Liquid Bloom",
    welcome: (
      <p>
        Welcome, Liquid Bloom. Amani Friend's solo journey-music
        project — the deep-listening half of{" "}
        <Link
          href="https://desertdwellers.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          Desert Dwellers
        </Link>
        , two decades of sound that has scored ceremonial floors,
        sheepskin journeys, sound baths, breathwork rooms, and ecstatic
        dance gatherings across continents. This network reads you as
        the doorway frequency: the room where the listening ear first
        learned what world-bass-as-medicine sounds like, and the
        adjacency through which everything that followed —{" "}
        <Link href="/people/mose" className="text-[hsl(var(--primary))] hover:underline">
          Mose
        </Link>
        ,{" "}
        <Link href="/people/pagan-ritual" className="text-[hsl(var(--primary))] hover:underline">
          the first Pagan Ritual
        </Link>
        ,{" "}
        <Link href="/people/vali-soul-sanctuary" className="text-[hsl(var(--primary))] hover:underline">
          Vali Soul Sanctuary
        </Link>
        ,{" "}
        <Link href="/people/ecstatic-movement-tribe" className="text-[hsl(var(--primary))] hover:underline">
          Tammy Beattie's Ecstatic Movement Tribe
        </Link>
        ,{" "}
        <Link href="/people/contact-improv" className="text-[hsl(var(--primary))] hover:underline">
          Contact Improv
        </Link>
        , and many other divine gatherings — entered.
      </p>
    ),
  },
  facts: [
    {
      label: "Project",
      value:
        "Liquid Bloom — Amani Friend's solo deep-journey alias · the slower, sacred-bass current alongside the festival-floor current of Desert Dwellers",
    },
    {
      label: "Lineage",
      value: (
        <>
          One half of{" "}
          <Link
            href="https://desertdwellers.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Desert Dwellers
          </Link>
          {" "}with Treavor Moontribe (Amar) — the global-bass duo whose
          tribal-electronic fusion scored a generation of festival
          floors. Liquid Bloom is the room they go to alone.
        </>
      ),
    },
    {
      label: "Field",
      value:
        "World-electronic · sacred bass · downtempo · ceremonial soundscape · ecstatic-dance scoring · sound-bath underbed · journey-music for breathwork and plant-medicine ceremony",
    },
    {
      label: "Released",
      value: (
        <>
          The <em>Crystalline Transmissions</em> album series (the
          quiet-hours canon) · the <em>ReBloom</em> remix series
          (collaborators across the global-bass world re-tending each
          track) · <em>Elixir</em>, <em>Re:Generations</em>,{" "}
          <em>Shaman&apos;s Eye</em>, <em>Cycle of Cinder and Smoke</em> —
          long-form releases that have been the underbed of countless
          ceremonial rooms
        </>
      ),
    },
    {
      label: "Label",
      value: (
        <>
          <Link
            href="https://deserttrax.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Desert Trax
          </Link>
          {" "}— the Desert Dwellers&apos; own label, home to a
          constellation of artists whose frequency rhymes (Mose,
          Bloomurian, Numatik, Govinda, Kaminanda, and many more)
        </>
      ),
    },
    {
      label: "Measured stream",
      value: (
        <>
          ~255h cumulative YouTube watch-time across this body&apos;s
          measured 2009–2026 listening data — one of the top eight
          streams of attention across the entire arc, alongside Lex
          Fridman, Anne Tucker, and Ottmar Liebert. The ear was on
          before the body knew what it was listening for.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <>
          <Link
            href="https://liquidbloom.bandcamp.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Bandcamp
          </Link>{" "}
          ·{" "}
          <Link
            href="https://open.spotify.com/artist/liquidbloom"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Spotify
          </Link>{" "}
          ·{" "}
          <Link
            href="https://www.instagram.com/liquidbloom/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Instagram
          </Link>{" "}
          ·{" "}
          <Link
            href="https://desertdwellers.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Desert Dwellers home
          </Link>
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold built from the user&apos;s lived testimony
        and Amani&apos;s public publishing — the Desert Dwellers home,
        the Bandcamp catalog, the Liquid Bloom liner notes. What is
        held private (named teachers from the lineages he carries,
        biographical specifics he has chosen not to publish) stays
        held open here on purpose. He is invited to replace any line
        with his own words at any time.
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
            Two decades of soundscape that lives at the seam where
            tribal percussion meets sacred-low-end electronic
            production. The Liquid Bloom shape is the slower current
            of the Desert Dwellers project — where Desert Dwellers
            opens festival floors at peak, Liquid Bloom holds the
            sound bath, the journey, the integration room, the
            after-hours floor where bodies are coming back down. The
            <em> Crystalline Transmissions</em> series is the quiet
            canon; the <em>ReBloom</em> series threads the global-bass
            collaborator network through each track twice over —
            originals on one side, remixes by peers on the other,
            one body of work that becomes a constellation.
          </p>
          <p>
            The work is not background music. It is composed at the
            frequency of ceremony — paced for the body that is
            already on a sheepskin in a room with a facilitator, paced
            for the floor that has been moving for three hours and is
            entering a slower tempo, paced for the breathwork that is
            about to release the diaphragm. Producers in the
            world-bass and ecstatic-dance lineage cite Liquid Bloom as
            one of the cells that defined the form. When the listening
            ear of this body began collecting hours alone in a room
            with headphones years before it understood why, Liquid
            Bloom was already there — a ~255h watch-time signal in the
            measured data, the eighth-largest YouTube stream across
            seventeen years. The frequency was being absorbed long
            before the body had words for what it was learning.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "How this body received him",
      heading: "The doorway opens",
      body: (
        <>
          <p>
            <strong>The first opening: hearing.</strong> Long before any
            room held him in person, Liquid Bloom was the substrate
            playing through this body&apos;s headphones during solo
            journey hours. Hours and hours over years. The listening
            ear learned what sacred-bass sounded like by living inside
            his catalog. By the time the YouTube algorithm started
            threading{" "}
            <Link href="/people/mose" className="text-primary hover:underline">
              Mose
            </Link>
            {" "}into the next song, the ear already recognized the
            family resemblance. Mose entered through Liquid Bloom&apos;s
            doorway. Without the years of Liquid Bloom playing in
            private, the recognition of what Mose was carrying
            wouldn&apos;t have landed.
          </p>
          <p>
            <strong>The first opening: gathering.</strong> The first{" "}
            <Link href="/people/pagan-ritual" className="text-primary hover:underline">
              Pagan Ritual
            </Link>
            {" "}this body ever attended was a Liquid Bloom room. That
            ritual was the threshold — not because it was the largest,
            not because it was the most public, but because it was the
            first ceremonial floor where this body recognized: this is
            home. The container felt familiar before the body knew the
            name for it. The frequency the headphones had been carrying
            in private had a room, and there were other bodies in it.
          </p>
          <p>
            <strong>The chain that followed.</strong> The Pagan Ritual
            opened{" "}
            <Link href="/people/vali-soul-sanctuary" className="text-primary hover:underline">
              Vali Soul Sanctuary
            </Link>{" "}
            — the place where the practice could keep being lived, not
            only attended once. Vali opened{" "}
            <Link href="/people/ecstatic-movement-tribe" className="text-primary hover:underline">
              Ecstatic Movement Tribe
            </Link>
            , held by{" "}
            <Link href="/people/tammy-beattie" className="text-primary hover:underline">
              Tammy Beattie
            </Link>
            . EMT opened{" "}
            <Link href="/people/contact-improv" className="text-primary hover:underline">
              Contact Improv
            </Link>{" "}
            — the embodied-listening practice that became its own
            substrate in this body&apos;s arc. And alongside all of
            this, more divine gatherings the user has not yet named
            here, each one a node in the same field. Every door
            downstream traces back to Amani&apos;s sound being the
            first frequency the body recognized as home.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The constellation he sits inside",
      body: (
        <>
          <p>
            Spotify&apos;s algorithmic reading places him beside{" "}
            <Link href="/people/mose" className="text-primary hover:underline">
              Mose
            </Link>
            ,{" "}
            <Link href="/people/bloomurian" className="text-primary hover:underline">
              Bloomurian
            </Link>
            ,{" "}
            <Link href="/people/porangui" className="text-primary hover:underline">
              Poranguí
            </Link>
            , Kaya Project, Numatik, Kaminanda, Govinda, AtYyA, Ape
            Chimba, Govinda — the world-bass and sacred-electronic
            cluster. The Desert Trax label gathers many of them under
            one curatorial roof. The{" "}
            <em>ReBloom</em> remix series gathers them again, at the
            frequency of mutual re-tending: each artist carrying one of
            Amani&apos;s tracks into their own room and bringing it
            back transformed.
          </p>
          <p>
            Within this body&apos;s arc, he sits at the center of the
            devotional-music substrate that emerged in the bridge years
            (2022 onward) — alongside Yaima, East Forest, Ajeet, Ram
            Dass, Ottmar Liebert, Karunesh, Anne Tucker, and the Mose
            cluster. He is the one whose hours predate all of them in
            the measured data. The eighth-largest YouTube stream
            across seventeen years; the cell whose recorded vibration
            taught the ear what the rest of the field would later
            sound like.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Where to walk further with this cell",
      heading: "The catalog and the room",
      body: (
        <>
          <p>
            The recorded catalog lives at{" "}
            <Link
              href="https://liquidbloom.bandcamp.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              liquidbloom.bandcamp.com
            </Link>{" "}
            and on{" "}
            <Link
              href="https://open.spotify.com/artist/liquidbloom"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Spotify
            </Link>
            . The full label home is at{" "}
            <Link
              href="https://desertdwellers.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              desertdwellers.com
            </Link>
            , and the Desert Trax constellation — Mose, Bloomurian,
            Numatik, Govinda, Kaminanda, AtYyA, and many more — lives
            at{" "}
            <Link
              href="https://deserttrax.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              deserttrax.com
            </Link>
            .
          </p>
          <p className="italic text-muted-foreground">
            Field reading: Liquid Bloom is one of the cells whose
            recorded vibration is itself a substrate. When his music
            plays in a room — sound bath, ceremony floor, breathwork
            session, solo headphone hour — that room joins the field
            his catalog has been holding for two decades. The container
            is portable. That is what makes him a doorway: the
            frequency travels through speakers as well as through
            bodies, and either path opens the same field.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Liquid Bloom has given the Coherence Network",
      body: (
        <ul>
          <li>
            <em>Sound as prayer, medicine, celebration</em> →
            anchor for{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
            </Link>{" "}
            (build at the actual tone; trust the routing).
          </li>
          <li>
            The doorway pattern — bodies meeting Amani at Vali
            Soul Sanctuary (Costa Rica) before meeting the music.
            Embodied first, audio second. See{" "}
            <Link href="/people/vali-soul-sanctuary" className="text-primary hover:underline">
              Vali Soul Sanctuary
            </Link>
            .
          </li>
          <li>
            Multi-room presence in this body&apos;s graph:{" "}
            <Link href="/people/rhythm-sanctuary" className="text-primary hover:underline">
              Rhythm Sanctuary
            </Link>{" "}
            (Jan 2020 set, still listened to),{" "}
            <Link href="/people/ocean-bloom-2024" className="text-primary hover:underline">
              Ocean Bloom 2024
            </Link>{" "}
            (Downtown Boulder configuration),{" "}
            <Link href="/people/portal" className="text-primary hover:underline">
              PORTAL
            </Link>{" "}
            (Meow Wolf Denver during MAPS).
          </li>
          <li>
            The Desert Dwellers / Desert Trax label home as a
            substrate of conscious-music continuity — resonant
            with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
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
        Public anchors:{" "}
        <Link
          href="https://liquidbloom.bandcamp.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Bandcamp
        </Link>{" "}
        ·{" "}
        <Link
          href="https://desertdwellers.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Desert Dwellers
        </Link>{" "}
        ·{" "}
        <Link
          href="https://deserttrax.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Desert Trax
        </Link>
      </p>
      <p className="text-xs italic">
        This page is a welcoming scaffold honoring what is honestly
        knowable from his own publishing and from the user&apos;s lived
        testimony of the doorway he opened. Birthplace, biographical
        specifics, and named teachers from the lineages he carries are
        held open here on purpose. Liquid Bloom is invited to replace
        any line with his own words at any time.
      </p>
    </>
  ),
};

export default content;
