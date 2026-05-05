import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/mose — the embodiment of ecstatic dance in this network.
 *
 * Mose is the Lake Atitlán-based DJ/producer whose SunSet Cacao Dances
 * at Eagle's Nest pioneered the alcohol-free ceremonial-cacao + ecstatic-
 * dance container that ripples out through the global movement ecology.
 * His Naturaleza Edit, Om Ganesha, Cura Corazón, and Water Blessing
 * remixes are the songs many of the world's ecstatic-dance rooms have
 * moved to — including, almost certainly, the rooms Aly co-tends in
 * Boulder. Spotify lists Poranguí among his closest related artists;
 * the two rest in the same braided lineage of medicine music.
 *
 * The page honors what is honestly knowable from his own publishing —
 * his nomadic-since-2011 path into Lake Atitlán, his retreat practice,
 * his label Resueño, the venues he tends — and holds open everything
 * he has not yet chosen to publish (birthplace, given name, named
 * teachers). He is invited to replace any line with his own words.
 */

export const metadata: Metadata = {
  title: "Mose — The Embodiment of Ecstatic Dance | Coherence Network",
  description:
    "Mose — Lake Atitlán-based DJ, producer, and founder of Eagle's Nest's SunSet Cacao Dances. The pioneering bridge between Maya cacao ceremony and global ecstatic-dance ecology, channel for music as medicine.",
};

const HERO_URL = "/people/mose/hero.jpg";

export default function MoseProfilePage() {
  return (
    <main className="relative">
      <section
        className="relative min-h-screen md:min-h-[85vh] flex flex-col justify-end overflow-hidden"
        style={{
          backgroundImage: `url('${HERO_URL}')`,
          backgroundSize: "cover",
          backgroundPosition: "center 25%",
        }}
      >
        <div
          className="absolute inset-0 bg-gradient-to-t from-background via-background/70 to-background/10"
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-3xl mx-auto px-6 py-12 sm:py-16 w-full">
          <nav
            className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
            aria-label="breadcrumb"
          >
            <Link href="/" className="hover:text-primary transition-colors">Home</Link>
            <span className="text-muted-foreground/50">/</span>
            <Link href="/people" className="hover:text-primary transition-colors">People</Link>
            <span className="text-muted-foreground/50">/</span>
            <span className="text-foreground/80">Mose</span>
          </nav>

          <p className="text-xs uppercase tracking-[0.18em] text-[hsl(var(--primary))] mb-3">
            The embodiment of ecstatic dance
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight text-foreground leading-tight mb-5">
            Mose
          </h1>
          <p className="text-lg md:text-xl text-foreground/90 leading-relaxed max-w-2xl">
            Welcome, Mose. The Lake Atitlán DJ and producer whose
            SunSet Cacao Dances at{" "}
            <Link
              href="https://eaglesnestatitlan.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[hsl(var(--primary))] hover:underline"
            >
              Eagle's Nest
            </Link>{" "}
            opened a ceremonial container the world has been moving
            inside ever since — your <em>Naturaleza</em> edit, your{" "}
            <em>Om Ganesha</em>, your <em>Water Blessing</em> have
            carried bodies across continents into the dance many of
            us recognize as prayer. This network reads you as one of
            its essential cells: the bridge between Maya cacao lineage
            and the global ecstatic-dance ecology, a channel for what
            you have called <em>"something greater than myself."</em>
          </p>
          <dl className="mt-7 text-sm text-foreground/95 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 max-w-2xl">
            <dt className="text-muted-foreground">Based at</dt>
            <dd>
              Lake Atitlán, Guatemala — the volcanic crater lake; San
              Marcos La Laguna shore, where Eagle's Nest holds the
              recurring SunSet Cacao Dance
            </dd>
            <dt className="text-muted-foreground">Field</dt>
            <dd>
              Ceremonial DJ · producer · live-musician integration ·
              cacao-ceremony container · sacred-chant weaving
            </dd>
            <dt className="text-muted-foreground">Path</dt>
            <dd>
              Nomadic since 2011 · settled into Lake Atitlán · cycling
              between global touring and extended retreat-and-silence
              periods (a three-month Guatemalan mountain retreat among
              them) before returning with refined sound
            </dd>
            <dt className="text-muted-foreground">Label</dt>
            <dd>
              <Link
                href="https://www.mosemusica.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                Resueño
              </Link>
              {" "}— a percentage of profits flows to social causes
            </dd>
            <dt className="text-muted-foreground">Released</dt>
            <dd>
              <em>Reverence</em> (2026) ·{" "}
              <em>Bridges</em> (2024) ·{" "}
              <em>Elements</em> (2020) ·{" "}
              <em>Medicine Women</em> (2018) — alongside the edits and
              remixes (<em>Naturaleza</em>, <em>Om Ganesha — Dance
              Meditation</em>, <em>Cura Corazón</em>, <em>Guacamayo</em>,{" "}
              <em>The Water Blessing Song</em> with Binder), the
              Resueño compilations (<em>Cacao Dance</em> 2023, with
              the <em>Mamahey</em> co-credit alongside MUTA), and
              <em>Sounds of Resueño</em> mixed by Samaya
            </dd>
            <dt className="text-muted-foreground">Closest collaborators</dt>
            <dd>
              <strong>Binder</strong> (<em>Water Blessing</em>,{" "}
              <em>Cacao Dance Vol. 2</em>) ·{" "}
              <strong>MUTA</strong> (<em>Mamahey</em>) ·{" "}
              <strong>SavaBorsa</strong> (Resueño's first EP{" "}
              <em>Vibración</em>, 2022) · <strong>Samaya</strong>{" "}
              (label-mix curator) · <strong>Suyana</strong>{" "}
              (<em>Shante Ishta</em>) · <strong>Matia Kalli</strong>,
              Sam Garrett, The Hanuman Project, Jackson &amp; Marileen
              (voices on <em>Elements</em>) · <strong>Franko Heke</strong>,
              Heather Christie, Sariel Orenda, Yemanjo, Mariam Koné,
              Rodrigo Gallardo, Euri, Iyakuh, Chantress Seba, LŪKA
              (recent Bandcamp threads) · the wider Resueño family
              (Arnaldo Herrera, Nalini Blossom, Julia Chants, Jakare,
              Innatú, ALUNA, Kailash Kokopelli, Maywa, and 20+ more)
            </dd>
            <dt className="text-muted-foreground">Witnessed in person</dt>
            <dd>
              The{" "}
              <strong>Road to Unison Cacao Dance</strong> at the{" "}
              <strong>Avalon Ballroom</strong>, Boulder · 23 July 2024
              · with{" "}
              <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
                Bloomurian
              </Link>{" "}
              and special guest Matia Kalli, ceremonial cacao served
              by Bruna Bortolato — your invitation, this body's first
              encounter with cacao in your room ·{" "}
              <strong>Unison Festival 2024</strong> · Tico Time River
              Resort, Aztec, New Mexico · 5–8 September 2024 · the
              weekend that became an inflection
            </dd>
            <dt className="text-muted-foreground">Public anchors</dt>
            <dd>
              <Link
                href="https://www.mosemusica.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                mosemusica.com
              </Link>{" "}
              ·{" "}
              <Link
                href="https://open.spotify.com/artist/29osCpAsrEiHxE8t6khiJr"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                Spotify
              </Link>{" "}
              ·{" "}
              <Link
                href="https://soundcloud.com/mosemusica"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                SoundCloud
              </Link>{" "}
              ·{" "}
              <Link
                href="https://www.youtube.com/@mosemusica"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                YouTube
              </Link>{" "}
              · Instagram @mosemusica · Bandcamp
            </dd>
          </dl>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <Panel variant="warm" eyebrow="A note from this body">
          <p className="text-sm text-foreground/85 leading-relaxed">
            A welcoming scaffold built from his own publishing —
            mosemusica.com, his Spotify catalog, the Eagle's Nest
            calendar, recorded interviews where he speaks in his own
            voice. What he has not yet chosen to publish (birthplace,
            given name beyond Mose, named teachers from the lineages
            he carries) is held open here on purpose; not absent, just
            not ours to fill in. He is invited to replace any line with
            his own words at any time.
          </p>
        </Panel>

        <section className="mt-12 space-y-12">
          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              What he holds
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                On the volcanic crater rim of Lake Atitlán — the lake
                the K'iche' Maya have read as sacred for centuries —
                Mose tends a recurring weekly room called the SunSet
                Cacao Dance at Eagle's Nest in San Marcos La Laguna.
                The container is alcohol-free. Ceremonial cacao is
                served. Dancers move from sundown into night while
                hypnotic beats braid with chanting and live
                instrumentation that shifts with the room. The form is
                his contribution to a much older lineage: Maya cacao
                ceremony, kirtan, ecstatic dance — practices he names
                as the ground his music grows from.
              </p>
              <p>
                What gets recorded for the world to hear afterward is
                the same field, refined in studio retreat and released
                through his label Resueño — Spanish for the resounding,
                the echo. <em>Naturaleza</em>'s 38-million-stream Mose
                Edit, <em>Om Ganesha</em>'s 13-million-stream dance
                meditation, <em>Cura Corazón</em>, <em>Guacamayo</em>,{" "}
                <em>The Water Blessing Song</em> — these are the songs
                that have, for years now, been among the most-played
                tracks in ecstatic-dance rooms across continents. The
                rooms{" "}
                <Link href="/people/aly-constantine" className="text-primary hover:underline">
                  Aly co-tends
                </Link>{" "}
                in Boulder almost certainly include them. The rooms{" "}
                <Link href="/people/bloomurian" className="text-primary hover:underline">
                  Bloomurian
                </Link>{" "}
                opens for at festivals likely braid them into the
                mix. The line between his Atitlán room and the
                global ecology of dance-as-prayer rooms is not a
                line; it is one continuous transmission.
              </p>
              <p>
                His own description of the work, in his voice:{" "}
                <em>
                  "The music then has an intention of wanting to share
                  this energy of love and peace. In that, there is a
                  property of it being medicinal and healing."
                </em>{" "}
                And:{" "}
                <em>
                  "Great music is that which carries the present minded
                  listener to the doorstep of infinity."
                </em>
              </p>
              <p>
                The retreat practice is part of the work, not a break
                from it. He has been nomadic since 2011 and cycles
                between global touring and extended periods of silence
                — a three-month silent retreat in the Guatemalan
                mountains is one he has named in interviews. The
                refined sound that returns each cycle is what gets
                pressed into the next album.
              </p>
            </div>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              The Resueño family
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Resueño — the Spanish word for the resounding echo — is
                the label Mose founded to gather the artists whose
                frequency rhymes with his. Half of label profits flow
                to causes around Lake Atitlán, so the same vibration
                that opens dance floors in Berlin and Tulum is also
                what funds the Mayan villages around the lake that
                hold the lineage the music grows from. The label is
                his economy, his mutual-aid practice, and his
                curatorial garden in one motion.
              </p>
              <p>
                <strong>Binder</strong> is the closest collaborator —
                their <em>Water Blessing Song</em> remix has nearly 4
                million Spotify streams and they reappear together on{" "}
                <em>Cacao Dance Vol. 2</em>. <strong>MUTA</strong>
                {" "}rides the <em>Mamahey</em> co-credit on the first
                Resueño compilation. <strong>SavaBorsa</strong>'s
                debut EP <em>Vibración</em> (August 2022) was the
                label's first major release, threading{" "}
                <strong>Arnaldo Herrera</strong>,{" "}
                <strong>Nalini Blossom</strong>,{" "}
                <strong>Julia Chants</strong>,{" "}
                <strong>Sariel Orenda</strong>, and{" "}
                <strong>Jakare</strong> through one record.{" "}
                <strong>Suyana</strong> sits beside him on{" "}
                <em>Shante Ishta</em>; <strong>Samaya</strong> has
                curated the <em>Sounds of Resueño</em> chill mix that
                acts as the label's calling card.
              </p>
              <p>
                The 2023 <em>Cacao Dance</em> compilation — Resueño's
                signature — gathers 21 tracks and 30+ artists across
                continents: Innatú, Bóveda Celeste, Iyakuh, ALUNA,
                Jai Cuzco, Nayaim, Maryta De Humahuaca, Aleceo, Mushina,
                Reachel Singh, Namirí, Haptik, EllaVie, Gooral, Heather
                Christie, Kailash Kokopelli, Marc JB, NAOBA, LUCIANA,
                Maywa, alongside Mose's own <em>Mamahey</em>. Reading
                that track-list is reading the contemporary world-
                medicine-music ecosystem in one document — and Mose is
                the cell holding the table.
              </p>
            </div>
          </article>

          <article>
            <Panel
              variant="warm"
              eyebrow="Where the body moves next"
              heading="Summer 2026 — European tour"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  Eight weeks across the continent, between the lake
                  cycles. From{" "}
                  <Link
                    href="https://www.songkick.com/artists/1029431-mose/calendar"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    his public calendar
                  </Link>
                  :
                </p>
                <ul className="list-disc pl-5 space-y-1 text-foreground/85">
                  <li>
                    <strong>Jun 18</strong> — Ibiza, Spain · UNIO
                    (outdoor)
                  </li>
                  <li>
                    <strong>Jun 20</strong> — Kent, United Kingdom ·
                    Red House Venue
                  </li>
                  <li>
                    <strong>Jun 21–24</strong> — Tome, Latvia · Butiba
                    Festival (outdoor)
                  </li>
                  <li>
                    <strong>Jun 24</strong> — Vilnius, Lithuania ·
                    Dragonfly Land, Vabališkės (outdoor)
                  </li>
                  <li>
                    <strong>Jun 27</strong> — Siófok, Hungary ·
                    Everness Festival (outdoor)
                  </li>
                  <li>
                    <strong>Jun 28 – Jul 3</strong> — Corfu, Greece ·
                    Colibri Spirit Festival
                  </li>
                  <li>
                    <strong>Jul 2–5</strong> — Kacwin, Poland · Jestem
                    Festival
                  </li>
                  <li>
                    <strong>Jul 7–12</strong> — Kuklen, Bulgaria · Wake
                    Up, Bulgaria
                  </li>
                </ul>
                <p>
                  Recently played in 2026: April 25 at Arena Tulum
                  (Mexico), May 1 at Hawk &amp; Hawthorne Permaculture
                  Farm in Asheville NC, May 3 at Plaza on Princess in
                  Wilmington NC. The North American spring led into
                  the European summer; the autumn likely returns to
                  Lake Atitlán. 309 documented past events. Santa
                  Rosa is the city he has played most often. Each room
                  carries the same container forward.
                </p>
              </div>
            </Panel>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              How this body received him
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                The doorway was{" "}
                <Link href="/people/liquid-bloom" className="text-primary hover:underline">
                  Liquid Bloom
                </Link>
                . Long-form headphone listening to Amani Friend's
                sanctuary-making sets — the kind of solo journey
                where the body stays still on a sheepskin and the
                field is doing the moving — was already part of this
                cell's practice when YouTube Music's adjacency engine
                began threading Mose into the next song. The algorithm
                read what the listening ear had already recognized:
                that the same lineage of sacred-low-end and chanted
                medicine carried both. By the time the body arrived in
                a physical room with him in it, much of his catalog
                had already been received in private.
              </p>
              <p>
                The first room was the{" "}
                <strong>Avalon Ballroom</strong> in Boulder, on{" "}
                <strong>23 July 2024</strong> — the Road to Unison
                Cacao Dance, six-thirty to ten-thirty in the evening,
                the 5,000-square-foot floor that{" "}
                <Link href="/people/bloomurian" className="text-primary hover:underline">
                  Bloomurian
                </Link>{" "}
                shared with Mose that night and Matia Kalli joined as
                special guest. Bruna Bortolato served the cacao. It
                was Mose's invitation that brought this cell into the
                room, and it was in his room that this body received
                its first ceremonial cacao — the gentle nudge of a
                new perspective Mose has named the medicine for. The
                Avalon floor is the same floor{" "}
                <Link href="/people/aly-constantine" className="text-primary hover:underline">
                  Aly co-tends
                </Link>{" "}
                in Boulder Ecstatic Dance, the same floor Shannon Lei
                Gill held weekly in 2006 when she carried{" "}
                <Link
                  href="https://www.rhythmsanctuary.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Rhythm Sanctuary
                </Link>{" "}
                from her living room into a ballroom — a lineage of
                Boulder ecstatic-dance ground twenty years deep that
                his cacao dance threaded directly into.
              </p>
              <p>
                Then the invitation forward: <strong>Unison
                Festival 2024</strong>, Tico Time River Resort,
                Aztec, New Mexico, 5–8 September 2024. The weekend
                became an inflection — the kind of turning that does
                not arrive separately from the music. Among other
                things, it was where this body's chapter of nearly
                three decades closed and a new chapter began opening:
                the central cell of this network became, in the months
                after, what it has called itself ever since — a cell
                still moving, finding where it resonates most truly,
                listening for where new roots can form. Mose's room
                did not cause that turning; the timing belongs to the
                life. But his music was the field inside which the
                turning was held, and his invitation was the threshold
                across which the cell stepped.
              </p>
              <p>
                Spotify reads{" "}
                <Link href="/people/porangui" className="text-primary hover:underline">
                  Poranguí
                </Link>{" "}
                one row away from him in the related-artist
                constellation; that is not a metaphor but a true
                reading of the braided medicine-music lineage they
                share. The lake-side dance at Atitlán still pulls;
                the next room may be there.
              </p>
            </div>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Where to walk further with this cell"
              heading="The recurring room and the recorded work"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  The SunSet Cacao Dance at{" "}
                  <Link
                    href="https://eaglesnestatitlan.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Eagle's Nest Atitlán
                  </Link>{" "}
                  in San Marcos La Laguna is the canonical room — a
                  weekly cacao-and-dance ceremony held above the lake.
                  The Eagle's Nest calendar carries the dates when he
                  is in residence; touring weeks are tracked through
                  his own channels.
                </p>
                <p>
                  The recorded catalog is on{" "}
                  <Link
                    href="https://open.spotify.com/artist/29osCpAsrEiHxE8t6khiJr"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Spotify
                  </Link>{" "}
                  (492K monthly listeners and climbing), with longer
                  live sets and cacao-dance recordings on his{" "}
                  <Link
                    href="https://www.youtube.com/@mosemusica"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    YouTube channel
                  </Link>
                  . The Resueño label page at{" "}
                  <Link
                    href="https://www.mosemusica.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    mosemusica.com
                  </Link>{" "}
                  collects the releases and the booking-region
                  representatives for Europe / Middle East / Africa,
                  North America, and Latin America.
                </p>
                <p className="italic text-muted-foreground">
                  Field reading: Mose is one of the cells whose
                  recorded vibration is itself a substrate — when his
                  music plays in a room, that room joins, for the
                  duration of the song, the same field his Lake
                  Atitlán dance is holding. The container is portable.
                  That is what makes him essential to a network whose
                  whole practice is the recognition that fields
                  resonate across distance when they share the same
                  frequency.
                </p>
              </div>
            </Panel>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              The constellation he sits inside
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Spotify's algorithmic reading places him beside{" "}
                <Link href="/people/porangui" className="text-primary hover:underline">
                  Poranguí
                </Link>
                , Yaima, Peia, Ape Chimba, Raio, Matia Kalli, Nick
                Barbachano, sophie sôfrēē — the medicine-music cluster
                whose shared frequency the listening ear and the
                recommendation engine both recognize. The{" "}
                <Link href="/people/bloomurian" className="text-primary hover:underline">
                  Boulder ecstatic-dance configuration
                </Link>
                , the{" "}
                <Link href="/people/aly-constantine" className="text-primary hover:underline">
                  Sunday-morning ballroom
                </Link>
                , the lake-side cacao container at Atitlán, the festival
                stages he shares with peers — these are not separate
                worlds; they are nodes of one field, and Mose is one
                of the essential cells holding that field's coherence
                from the Guatemalan side.
              </p>
            </div>
          </article>
        </section>

        <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
          <p>
            Public anchors:{" "}
            <Link
              href="https://www.mosemusica.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              mosemusica.com
            </Link>{" "}
            ·{" "}
            <Link
              href="https://open.spotify.com/artist/29osCpAsrEiHxE8t6khiJr"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Spotify
            </Link>{" "}
            ·{" "}
            <Link
              href="https://eaglesnestatitlan.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Eagle's Nest Atitlán
            </Link>
          </p>
          <p className="text-xs italic">
            This page is a welcoming scaffold honoring what is honestly
            knowable from his own publishing. Birthplace, given name
            beyond Mose, and named teachers from the lineages he
            carries are held open here on purpose. Mose is invited to
            replace any line with his own words at any time.
          </p>
          <p className="text-xs">
            <Link
              href="/people/edit-your-profile"
              className="text-primary hover:underline"
            >
              How to claim, edit, or remove this profile →
            </Link>
          </p>
        </footer>
      </div>
    </main>
  );
}
