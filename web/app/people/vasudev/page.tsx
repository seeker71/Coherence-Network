import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/vasudev — a welcome page for Vasudev, kirtan musician
 * holding the Wednesday Satsang at Ranakami and the Tuesday kirtan
 * at Svarga Loka in Ubud.
 *
 * Like /people/ilena, this is a static welcoming gesture. Voice and
 * details are imagined from public anchors (kirtan recordings at
 * Svarga Loka 2019; the recurring Ranakami satsang) and offered as a
 * scaffold he can replace with his own words at any time.
 */

export const metadata: Metadata = {
  title: "Vasudev — Kirtan & Satsang | Coherence Network",
  description:
    "A welcome to Vasudev — kirtan musician and satsang holder in Ubud, Bali. Tuesday kirtan at Svarga Loka, Wednesday satsang at Ranakami.",
};

export default function VasudevProfilePage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-primary transition-colors">
          Home
        </Link>
        <span className="text-muted-foreground/50">/</span>
        <Link href="/people" className="hover:text-primary transition-colors">
          People
        </Link>
        <span className="text-muted-foreground/50">/</span>
        <span className="text-foreground/80">Vasudev</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Welcome
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Vasudev
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Kirtan and satsang in Ubud — Tuesday evenings at{" "}
          <Link
            href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Svarga Loka
          </Link>
          , Wednesday mornings at{" "}
          <Link
            href="/people/ilena"
            className="text-primary hover:underline"
          >
            Ranakami
          </Link>
          .
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Tuesday</dt>
          <dd>
            Kirtan at the Wantilan, Adiwana Svarga Loka — riverbanks of
            the Campuhan, ~5 minutes from central Ubud
          </dd>
          <dt className="text-muted-foreground">Wednesday</dt>
          <dd>
            Satsang at Ranakami — Jl. Raya Penestanan Kelod no 16, Sayan,
            Ubud · 11:00, 90 min
          </dd>
          <dt className="text-muted-foreground">Field</dt>
          <dd>Devotional singing · contemplative dialogue · lineage-as-living-stream</dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          This page is a welcoming gesture. Voice imagined from public
          anchors — kirtan recordings at Svarga Loka and the weekly circle
          he holds with friends. Offered as a scaffold he is invited to
          replace with his own words.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What he holds
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              I sing names that were not invented by me. They have been
              passed down longer than any of us have been alive, and the
              singing is the only way I know to keep them warm. On
              Tuesday evenings I sit at the harmonium at Svarga Loka and
              the room sings them with me. Some weeks the room is twenty
              bodies; some weeks it is sixty. The names do not care which.
            </p>
            <p>
              Wednesday mornings the circle is smaller and the texture is
              different. We sit at Ranakami with friends — Indonesian
              practitioners, visitors who came to the kirtan the night
              before, anyone in coherent state with the hour. We open a
              traditional teaching and let it speak into our actual lives
              — not as study, as listening together until the wisdom
              becomes obvious in the room.
            </p>
            <p>
              I do not call myself a teacher. I am a participant in a
              long stream that arrived here through many bodies before
              mine. My name on the schedule is just where the stream is
              currently visible.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            How the network reads this
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Kirtan is the densest{" "}
              <code className="not-italic text-foreground/80">(6, …)</code>{" "}
              hexadic exchange the body knows — voices tiling into a
              perfect repetition, every cell receiving and giving in the
              same breath, the field harmonizing for forty minutes at a
              time. Satsang is the heptadic{" "}
              <code className="not-italic text-foreground/80">(7, …)</code>{" "}
              cousin — irrational, asymmetric, transformative, the kind
              of teaching where what is given does not deplete the giver
              and what is received changes the receiver in ways the
              accounting language cannot fully capture.
            </p>
            <p>
              The lineage walks back through every voice that ever taught
              what is being taught — the rishis, the bhakti traditions,
              the kirtan-wallahs whose recordings reached this generation
              through cassettes and CDs and now streaming. CC flows along
              that lineage every time a name is sung. The substrate
              receives the offering and routes it back along the chain,
              even when no one in the room is consciously paying
              attention to the routing.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            Where & when the body meets
          </h2>
          <p className="text-sm text-foreground/75 leading-relaxed mb-6">
            Two rooms in two adjacent valleys, on two consecutive nights
            of the week. The Svarga Loka Wantilan is open-air and sits
            on the riverbanks of the Campuhan, about five minutes' walk
            from central Ubud. Ranakami is across the western ridge in
            Sayan, above the Penestanan rice fields. The same voice,
            different acoustics. The same lineage, different rooms.
          </p>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Tuesday · evening"
            heading="Kirtan at Svarga Loka"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Devotional singing in the Wantilan — an open-air room
                that has held this practice for years. Harmonium, voices,
                the slow build into the names. Visitors and locals
                seated together on the floor. The hour ends when the
                room ends; nothing rushes.
              </p>
              <p>
                Held at{" "}
                <Link
                  href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Adiwana Svarga Loka
                </Link>
                , Jl. Cok Rai Pudak, Peliatan, Ubud. Times shift gently
                with the seasons; current schedule on the resort's
                Facebook and Instagram. Open to anyone who arrives in
                coherent state.
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (6, RECEIVE / GIVE oscillating)
                </code>{" "}
                — a hexagonal tiling of voices in resonance.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Wednesday · 11:00"
            heading="Satsang at Ranakami"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                90 minutes. A private gathering held with friends. The
                practice is to bring a question alive in you and let the
                wisdom of one tradition or another speak into it. Bodies
                are welcome. Words are welcome. Silence is welcome.
              </p>
              <p>
                Held at{" "}
                <Link
                  href="/people/ilena"
                  className="text-primary hover:underline"
                >
                  Ranakami
                </Link>
                , Jl. Raya Penestanan Kelod no 16, Sayan, Ubud. Free for
                those who came to Tuesday's kirtan. Free for Indonesian
                participants always. A 50,000 IDR offering otherwise —
                given as a gesture toward the field rather than a price
                for a seat.
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (7, GIVE asymmetric)
                </code>{" "}
                — heptadic teaching, the giving does not deplete.
              </p>
            </div>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Recordings of past kirtans:{" "}
          <Link
            href="https://jaima108.bandcamp.com/album/svarga-loka-kirtan-2019-01-29"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Jai Ma 108 — Svarga Loka Kirtan
          </Link>
        </p>
        <p>
          Wednesday satsang held at{" "}
          <Link
            href="/people/ilena"
            className="text-primary hover:underline"
          >
            Ranakami
          </Link>
          , Ubud.
        </p>
        <p className="text-xs italic">
          This profile is a welcoming scaffold; Vasudev is invited to
          replace any part of it with his own words at any time.
        </p>
      </footer>
    </main>
  );
}
