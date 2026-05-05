import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "PORTAL — Partnership of Responsible Trippers | Coherence Network",
  description:
    "A welcome to PORTAL — the Denver-based initiative to destigmatize responsible psychedelic use. Hosts events at Red Rocks, Meow Wolf, and across the Denver psychedelic community.",
};

const HERO_URL = "/people/portal/hero.jpg";

export default function PortalProfilePage() {
  return (
    <main className="relative">
      <section
        className="relative min-h-screen md:min-h-[85vh] flex flex-col justify-end overflow-hidden"
        style={{
          backgroundImage: `url('${HERO_URL}')`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div
          className="absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20"
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-3xl mx-auto px-6 py-12 sm:py-16 w-full">
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
            <span className="text-foreground/80">PORTAL</span>
          </nav>

          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Welcome
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight text-foreground leading-tight mb-5">
            PORTAL
          </h1>
          <p className="text-lg md:text-xl text-foreground/85 leading-relaxed max-w-2xl">
            The Denver psychedelic community gathered as a single
            initiative — Partnership of Responsible Trippers Advocating
            for Legalization. Music, art, and shared rooms held in
            public; the Late-Night Takeover at Meow Wolf during MAPS
            2025 is where this body first walked through the door.
          </p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <header className="mb-10">
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Initiative · community · venue-of-rooms
          </p>
          <dl className="text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <dt className="text-muted-foreground">Field</dt>
            <dd>Psychedelic destigmatization · cultural integration · music + art events · advocacy</dd>
            <dt className="text-muted-foreground">Public</dt>
            <dd>
              <Link
                href="https://youaretheportal.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                youaretheportal.com
              </Link>
            </dd>
            <dt className="text-muted-foreground">Recurring rooms</dt>
            <dd>
              Late-Night Takeovers at Meow Wolf Denver · presence at
              Red Rocks Amphitheatre · regular Denver-area events
            </dd>
            <dt className="text-muted-foreground">In this body's awareness</dt>
            <dd>
              Met Aubrey Marcus in the lobby at the PORTAL Late-Night
              Takeover at Meow Wolf Denver, June 19, 2025, during MAPS
              Psychedelic Science 2025 week.
            </dd>
          </dl>
        </header>

        <Panel variant="warm" eyebrow="A note from this body">
          <p className="text-sm text-foreground/85 leading-relaxed">
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
        </Panel>

        <section className="mt-12 space-y-12">
          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              What PORTAL holds
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
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
            </div>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Recurring · MAPS Psychedelic Science weeks"
              heading="Late-Night Takeover at Meow Wolf Denver"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
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
              </div>
            </Panel>
          </article>
        </section>

        <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
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
        </footer>
      </div>
    </main>
  );
}
