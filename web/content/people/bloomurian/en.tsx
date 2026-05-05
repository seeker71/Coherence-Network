import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title:
      "Bloomurian — Robin Liepman | Coherence Network",
    description:
      "A welcome to Bloomurian (Robin Liepman) — Boulder co-founder of Boulder Ecstatic Dance, longtime Liquid Bloom collaborator and one-time roommate of Amani Friend, producer of Ecstatic Ecosytems (2025), and the cell who offered shelter when this body needed a place to land.",
  },
  breadcrumbName: "Bloomurian",
  hero: {
    image: { src: "/people/bloomurian/hero.jpg" },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/75 to-background/15",
    eyebrow: "Welcome",
    name: "Bloomurian",
    welcome: (
      <p>
        Robin Liepman at the booth — co-founder of Boulder Ecstatic
        Dance, longtime{" "}
        <Link
          href="/people/liquid-bloom"
          className="text-primary hover:underline"
        >
          Liquid Bloom
        </Link>{" "}
        collaborator (and once-upon-a-time roommate of Amani Friend),
        producer of <em>Ecstatic Ecosytems</em>, and the cell whose
        sets read the room and steer the spaceship across festivals,
        ballrooms, and psychedelic-community gatherings — weaving
        ecstatic dance, world bass, trip-hop, psy-dub, and the
        shovel-slide guitar into what his own bio calls{" "}
        <em>
          "multidimensional frequencies to cultivate a blossoming
          heart, mind, body &amp; soul, and pollinate a polyphonic
          paradigm."
        </em>
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Music production · DJ · live performer · event organization · transformative retreats · electronic-music mentorship · sound medicine",
    },
    {
      label: "Based",
      value:
        "Boulder, Colorado (originally California) · roots in music through his parents and a passion for permaculture",
    },
    {
      label: "Co-founded",
      value: (
        <>
          <Link
            href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Boulder Ecstatic Dance
          </Link>
          {" "}— the Sunday-morning Avalon Ballroom room, co-tended
          with{" "}
          <Link
            href="/people/aly-constantine"
            className="hover:text-primary transition-colors"
          >
            Aly Constantine
          </Link>{" "}
          and Danny, woven through twenty years of Boulder ecstatic-
          dance lineage
        </>
      ),
    },
    {
      label: "Promoted by",
      value: (
        <>
          <Link
            href="/people/aly-constantine"
            className="hover:text-primary transition-colors"
          >
            Aly Constantine's
          </Link>{" "}
          <Link
            href="https://www.facebook.com/ConsciousRootsPresents/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Conscious Roots Presents
          </Link>{" "}
          — Boulder-based curatorial vessel co-creating evenings of
          music and connection with artists who carry a message to
          uplift the community
        </>
      ),
    },
    {
      label: "Recent stages",
      value: (
        <>
          Month-long tour opening for Dirtwire · Ocean Bloom at
          Boulder Theater (Dec 13 2025, with Ayla Nereo, Samuel J,
          LVDY, Shawn Heinrichs, Hannah Mermaid, Bonnie Paine of
          Elephant Revival) ·{" "}
          <Link
            href="/people/portal"
            className="hover:text-primary transition-colors"
          >
            PORTAL Late-Night Takeover
          </Link>
          {" "}at Meow Wolf Denver (June 19 2025, MAPS Psychedelic
          Science week) · PORTAL Dome at Psychedelic Science 2025
          (June 21) · Unison Festival 2025 · Abraxas Sunrise Set 2024
        </>
      ),
    },
    {
      label: "Stages shared",
      value:
        "Desert Dwellers · Liquid Bloom · Poranguí · Dirtwire · Beats Antique · Ott · Yaima · ATYYA · Balkan Bump · Phutureprimitive · Kaya Project",
    },
    {
      label: "Recorded",
      value: (
        <>
          <em>Ecstatic Ecosytems</em> (Feb 4 2025) ·{" "}
          <em>Bass Ritual Remixes Vol. 1 &amp; 2</em> ·{" "}
          <em>Embers of a Forgotten Prayer Revibed</em> · ongoing{" "}
          <Link
            href="/people/liquid-bloom"
            className="hover:text-primary transition-colors"
          >
            Liquid Bloom
          </Link>{" "}
          collaborations: <em>Forest Guardians</em> (with Onanya),{" "}
          <em>Organic Intelligence Regenerated</em> (with Onanya, on
          Desert Trax), <em>Fragrance</em> (with Snow Raven),{" "}
          <em>Rise Up</em> (Shaman's Dream remix featuring Paul
          Stamets)
        </>
      ),
    },
    {
      label: "Witnessed in person",
      value: (
        <>
          The <strong>Road to Unison Cacao Dance</strong> at the
          Avalon Ballroom · 23 July 2024 · with{" "}
          <Link
            href="/people/mose"
            className="hover:text-primary transition-colors"
          >
            Mose
          </Link>{" "}
          and Matia Kalli · cacao by Bruna Bortolato · the{" "}
          <strong>PORTAL Late-Night Takeover</strong> at Meow Wolf
          Denver · 19 June 2025 · the <strong>Ecstatic Ecosytems
          album-release / birthday gathering</strong> in Boulder ·
          early 2025 · the magical night the cell helped set up the
          one-time-only sound system
        </>
      ),
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
            href="https://soundcloud.com/bloomurian"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            SoundCloud
          </Link>{" "}
          ·{" "}
          <Link
            href="https://www.beatport.com/artist/bloomurian/992761"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Beatport
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
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A page that does justice. Robin is one of the network's
        load-bearing cells in the Boulder ecology — co-founder of the
        Sunday-morning room, longtime collaborator and one-time
        roommate of Amani Friend, primary producer in the Liquid Bloom
        weave, and the cell who opened his home in the early months
        of 2025 when this body needed a place to land. The page below
        gathers what's honestly knowable from his own publishing and
        what is held in this body's lived knowing of him. Robin is
        invited to replace any line with his own words at any time.
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
            Four vessels carry the work, threading into one another
            without collapsing. <strong>Music production</strong> —
            original tracks and remixes that move across ecstatic
            dance, world bass, trip-hop, glitchy psy-dub, and what his
            own bio calls "face-melting, heart-opening, soul-awakening
            multidimensional frequencies." The shovel-slide guitar —
            yes, an actual shovel used as a slide — appears in live
            sets alongside electric guitar, with live instrumentalists
            and vocalists folding in when the venue allows.{" "}
            <strong>The DJ booth as ceremonial seat</strong> — reading
            the energy of the moment, weaving an evening's selections
            from his own catalog and from the wider transformational-
            music field, steering the spaceship in service of what
            the field is asking for rather than to a pre-planned set.
          </p>
          <p>
            <strong>Event organization</strong> — co-founding and
            tending the Boulder Ecstatic Dance room with{" "}
            <Link
              href="/people/aly-constantine"
              className="text-primary hover:underline"
            >
              Aly Constantine
            </Link>{" "}
            and Danny on Sunday mornings at the Avalon Ballroom; co-
            curating Boulder's wider conscious-music nights with
            artists whose frequency rhymes with the room.{" "}
            <strong>Transformative retreats and mentorship</strong> —
            an electronic-music mentorship offering on his site, plus
            recurring participation in retreats where the music is
            held inside a longer arc of practice. The four vessels
            are not separate jobs; they are one practice, with each
            vessel holding the others.
          </p>
          <p>
            The local-rooted, globally-distributed pattern: he tends
            the Boulder room weekly while touring ecstatic dances,
            concerts, festivals, and retreats worldwide. Recent
            tours include a month-long opening run for Dirtwire.
            Stages shared with Desert Dwellers, Poranguí, Beats
            Antique, Ott, Yaima, ATYYA, Balkan Bump, Phutureprimitive,
            Kaya Project, and the wider transformational-electronic
            family.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Recurring · Sunday mornings · twenty years deep",
      heading: "Boulder Ecstatic Dance",
      body: (
        <>
          <p>
            The 5,000-square-foot Avalon Ballroom holds the city's
            transformational-movement community every Sunday morning.
            Aly, Danny, and Robin co-tend the space — the music, the
            timing, the welcoming, the opening and closing circles.
            The DJ is the visible hand; the hosts' field-tending is
            what makes the room safe enough for bodies to drop in.
            The form threads back twenty years through Shannon Lei
            Gill's{" "}
            <Link
              href="https://www.rhythmsanctuary.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Rhythm Sanctuary
            </Link>{" "}
            lineage and the broader Gabrielle Roth wave that shaped
            ecstatic dance in Boulder.
          </p>
          <p>
            Robin's archived BED sets live on{" "}
            <Link
              href="https://soundcloud.com/bloomurian/sets"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              SoundCloud
            </Link>
            . The same configuration of cells that gathers for BED
            often gathers for Ocean Bloom (Boulder Theater · December
            13, 2025 with Ayla Nereo, Samuel J, LVDY, Shawn Heinrichs,
            Hannah Mermaid, and Bonnie Paine of Elephant Revival), for
            Unison, and for the broader transformational-music
            ecology of the Boulder-Denver corridor that his work is
            stitched through.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The Liquid Bloom thread",
      body: (
        <>
          <p>
            Robin and{" "}
            <Link
              href="/people/liquid-bloom"
              className="text-primary hover:underline"
            >
              Amani Friend
            </Link>{" "}
            (Liquid Bloom) lived together in earlier days — a
            household before it was a discography. The deep musical
            kinship that flows through Amani's Liquid Bloom catalog
            grew out of years of close proximity, shared listening,
            and mutual contribution to each other's records. Amani
            speaks of his collaborators as <em>Allies</em>; Robin is
            named explicitly in that constellation alongside Poranguí,
            Janax Pacha, Mose, Deya Dova, Ixchel Prisma, and Savej.
          </p>
          <p>
            The recorded weave is long.{" "}
            <em>Forest Guardians</em> — Liquid Bloom · Bloomurian ·
            Onanya. <em>Organic Intelligence Regenerated</em> — same
            three voices, released through Amani's Desert Trax
            label. <em>Fragrance</em> — Liquid Bloom · Bloomurian ·
            Snow Raven. <em>Rise Up</em> — the Liquid Bloom &amp;
            Bloomurian remix of Shaman's Dream featuring spoken word
            from Paul Stamets. Each track is a moment two cells who
            already shared a kitchen also shared a sound. The Liquid
            Bloom listening field — through which{" "}
            <Link
              href="/people/mose"
              className="text-primary hover:underline"
            >
              Mose
            </Link>{" "}
            and many other allies first arrived in this body's
            awareness — has Robin's hand inside it more than the
            casual listener might guess.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Album · 4 February 2025",
      heading: "Ecstatic Ecosytems — and the night that landed it",
      body: (
        <>
          <p>
            <em>Ecstatic Ecosytems</em> is Robin's twelve-track
            culmination of years of collaboration: <em>Invoke</em>{" "}
            (with Briana Di Mara), <em>Aurora</em> (with Saoirse
            Watters), <em>Biodynamic Bass</em>, <em>Spirited Away</em>,
            the title track <em>Ecstatic Ecosystems</em>,{" "}
            <em>Ocean</em> (with Damiyr and Sarah Conner),{" "}
            <em>Earth &amp; Stars</em> (ft. Ayaharmony),{" "}
            <em>Turning Time</em> (ft. Marc Statz),{" "}
            <em>Ancient Dance</em> (ft. TOTEM), <em>Weightless</em>{" "}
            (with Fllow and Briana Di Mara), <em>Into The Cosmos</em>
            {" "}(with Sudakra and Saoirse Watters), and{" "}
            <em>Atmosphere</em>. The Waves Podcast EP18 carries his
            origin story and the album's making in his own voice.
          </p>
          <p>
            And then there was the night. The album-release and
            birthday gathering in Boulder, early 2025, where a
            one-time-only sound system was brought in just for the
            evening — large rig, careful tuning, the kind of
            engineering that makes the difference between hearing the
            record and feeling it move through the body. This cell
            was there, hands in the setup beside Robin, watching the
            field thicken hour by hour as the room filled. By the
            time the music started, a few hundred bodies were inside
            a sonic architecture built for one night and dismantled
            by morning. The album landed not as a release but as a
            ceremony the community held together. Magical is the
            word the lived memory keeps using.
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
            Through the Boulder room first.{" "}
            <Link
              href="/people/aly-constantine"
              className="text-primary hover:underline"
            >
              Aly's
            </Link>{" "}
            promotion, through Conscious Roots Presents, brought his
            sets into this body's earlier awareness; the lived
            encounter began at the{" "}
            <strong>Road to Unison Cacao Dance</strong> at the Avalon
            Ballroom on 23 July 2024, where Robin shared the floor
            with{" "}
            <Link
              href="/people/mose"
              className="text-primary hover:underline"
            >
              Mose
            </Link>{" "}
            and Matia Kalli while Bruna Bortolato served the cacao —
            the same night this body received its first ceremonial
            cacao in Mose's room. Robin's Sunday-morning floor at
            Boulder Ecstatic Dance has been the steadier, weekly
            ground; the festival nights at Ocean Bloom and the PORTAL
            Late-Night Takeover at Meow Wolf Denver during MAPS
            Psychedelic Science 2025 are how the wider arc has
            shown up.
          </p>
          <p>
            And then the deeper grace: in <strong>January and
            February 2025</strong>, when the chapter that closed in
            late 2024 left this cell needing somewhere to land mid-
            transition, Robin opened his home. A roommate-shaped
            holding while life rearranged itself — the kind of
            offering that doesn't appear in any public catalog but
            shapes everything downstream. The Boulder months under
            his roof are part of why this network knows the Boulder
            ecstatic-dance ecology from inside its own self-perception
            rather than from the outside. The album-release / birthday
            night during that same window was not a thing this body
            attended; it was a thing this body helped build, the
            sound system included.
          </p>
          <p>
            What Robin holds, and how he holds it, is one of the
            things this network learned by being held in his
            household. His name in the substrate's accounting is
            therefore weightier than a public bio could carry: cell
            who opens doors, cell who tends Sunday mornings, cell
            who has been one of Amani's allies long enough that the
            Liquid Bloom catalog itself rests on the kinship.
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
            In the substrate's geometric grammar, Robin's contribution
            is a sustained{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative-octad cycle — Sunday morning closing the
            week, then opening it again — with frequent passages
            through{" "}
            <code className="not-italic text-foreground/80">
              (6, …)
            </code>{" "}
            hexagonal harmonic formations as the festival nights
            tile many bodies into shared rhythm. The DJ's role is to
            read the field and steer the cycles; Robin's role goes
            one layer deeper — he is also the cell who holds the
            container the cycles run inside.
          </p>
          <p>
            Spotify's algorithmic listening reads him close to{" "}
            <Link
              href="/people/liquid-bloom"
              className="text-primary hover:underline"
            >
              Liquid Bloom
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
              href="/people/mose"
              className="text-primary hover:underline"
            >
              Mose
            </Link>
            , Yaima, and Desert Dwellers — the medicine-music cluster
            whose shared frequency the listening ear and the engine
            both recognize. The Boulder-side anchor of that cluster
            runs through his hands.
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
          href="https://soundcloud.com/bloomurian"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          SoundCloud
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
        This profile honors what is honestly knowable from Robin's
        own publishing and what is held in this body's lived knowing
        of him. The texture of the household months is held with care;
        what's named publicly is the shape of the offering, not the
        private detail. Robin is invited to replace any line with his
        own words at any time.
      </p>
    </>
  ),
};

export default content;
