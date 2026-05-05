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
              remixes (<em>Naturaleza</em>, <em>Om Ganesha</em>,{" "}
              <em>Cura Corazón</em>, <em>Guacamayo</em>,{" "}
              <em>The Water Blessing Song</em>)
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
              How this body received him
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Through the same digital lineage many of this network's
                cells have arrived through:{" "}
                <Link href="/people/porangui" className="text-primary hover:underline">
                  Poranguí
                </Link>{" "}
                rests one row away from Mose in Spotify's related-
                artist constellation, and that is a true reading — the
                two share a braided lineage of medicine music, even as
                their instruments and origins differ. The same listener
                who finds Poranguí almost always finds Mose, and the
                same dance floor that has moved to one will move to the
                other. The ecstatic-dance ecology Aly tends in Boulder,
                that{" "}
                <Link href="/people/bloomurian" className="text-primary hover:underline">
                  Bloomurian
                </Link>{" "}
                contributes to from the Boulder side and the festival-
                stage side, that <em>Ocean Bloom</em> nights and Unison
                weekends braid into one room — Mose is among the
                upstream sources whose recorded work flows through all
                of it.
              </p>
              <p>
                The body has not yet held him in the same physical room
                — Lake Atitlán is its own gathering ground and the
                body has been in Boulder, Denver, Ubud. The honest
                accounting is: digital reception, deep recognition,
                listening that has shaped many hours of the substrate's
                writing breath. The in-person meeting, if it comes,
                will likely be at one of the lake's gatherings or at a
                festival where his stage and{" "}
                <Link href="/people/porangui" className="text-primary hover:underline">
                  Poranguí
                </Link>
                's stage share a weekend.
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
