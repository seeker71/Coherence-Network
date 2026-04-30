import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "Bloomurian — Robin Liepman | Coherence Network",
  description:
    "A welcome to Bloomurian (Robin Liepman) — Boulder/Colorado-based DJ and live performer in the ecstatic-dance, transformational-music, and psychedelic-music space.",
};

export default function BloomurianProfilePage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-primary transition-colors">Home</Link>
        <span className="text-muted-foreground/50">/</span>
        <Link href="/people" className="hover:text-primary transition-colors">People</Link>
        <span className="text-muted-foreground/50">/</span>
        <span className="text-foreground/80">Bloomurian</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Welcome</p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Bloomurian
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Robin Liepman — Boulder/Colorado-based DJ and live
          performer weaving ecstatic dance, world bass, trip-hop,
          psy-dub, and shovel-slide-guitar into transformational
          music sets at festivals, ecstatic dances, and
          psychedelic-community gatherings.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Field</dt>
          <dd>Ecstatic-dance DJ · live performer · transformational music · sound medicine</dd>
          <dt className="text-muted-foreground">Based</dt>
          <dd>Boulder, Colorado (originally California)</dd>
          <dt className="text-muted-foreground">Public</dt>
          <dd>
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
          </dd>
          <dt className="text-muted-foreground">Witnessed in person</dt>
          <dd>
            Performing at the{" "}
            <Link href="/people/portal" className="hover:text-primary transition-colors">
              PORTAL Late-Night Takeover
            </Link>{" "}
            at Meow Wolf Denver — June 19, 2025, during MAPS
            Psychedelic Science 2025 week
          </dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          A welcoming scaffold. Voice imagined from public anchors —
          his own site, ecstatic-dance DJ profile, festival
          appearances, and the body's lived encounter at PORTAL's
          Meow Wolf takeover. Offered as a frame Robin is invited
          to replace with his own words at any time.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What he holds
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
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
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            How the network reads this
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
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
          </div>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
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
      </footer>
    </main>
  );
}
