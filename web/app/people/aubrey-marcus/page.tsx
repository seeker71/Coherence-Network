import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "Aubrey Marcus — Connecting Tissue | Coherence Network",
  description:
    "A welcome to Aubrey Marcus — Onnit founder, podcast host, and connecting tissue for embodied / psychedelic / fight-community spiritual conversation that has reached this body through long-form interviews.",
};

const HERO_URL =
  "https://www.aubreymarcus.com/cdn/shop/files/Aubrey_Marcus_Collective.png?crop=center&height=2000&v=1747930639&width=3000";

export default function AubreyMarcusProfilePage() {
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
            <span className="text-foreground/80">Aubrey Marcus</span>
          </nav>
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Welcome
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight text-foreground leading-[1.05] mb-5">
            Aubrey Marcus
          </h1>
          <p className="text-lg md:text-xl text-foreground/85 leading-relaxed max-w-2xl">
            Welcome, Aubrey. Founder of Onnit, host of the{" "}
            <Link
              href="https://www.aubreymarcus.com/podcasts"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[hsl(var(--primary))] hover:underline"
            >
              Aubrey Marcus Podcast
            </Link>
            , and the long-form room where embodied, psychedelic-curious,
            fight-community, and consciousness conversations have been
            landing in this body for years.
          </p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <header className="mb-10">
          <p className="text-sm text-foreground/80 leading-relaxed">
            Another shape of <strong>connecting tissue</strong> — the
            cell whose long-form room has carried embodied,
            psychedelic-curious, fight-community, masculine-work, and
            consciousness conversations to this body for years.
          </p>
          <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <dt className="text-muted-foreground">Field</dt>
            <dd>Embodiment · psychedelic exploration · men's work · breathwork · long-form interview</dd>
            <dt className="text-muted-foreground">Public</dt>
            <dd>
              <Link
                href="https://www.aubreymarcus.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                aubreymarcus.com
              </Link>{" "}
              ·{" "}
              <Link
                href="https://www.aubreymarcus.com/podcasts"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                podcast
              </Link>
            </dd>
            <dt className="text-muted-foreground">Hosted (among others)</dt>
            <dd>
              <Link href="/people/matias-de-stefano" className="hover:text-primary transition-colors">
                Matías De Stefano
              </Link>{" "}
              multiple times · many embodiment teachers · breathwork
              and psychedelic-medicine practitioners · spiritual
              scientists.
            </dd>
            <dt className="text-muted-foreground">Witnessed in person</dt>
            <dd>
              Same-room participant at{" "}
              <Link
                href="https://maps.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                MAPS Psychedelic Science 2023
              </Link>{" "}
              (Denver · June 2023 · no direct exchange) · then a
              brief lobby encounter at the{" "}
              <Link href="/people/portal" className="hover:text-primary transition-colors">
                PORTAL Late-Night Takeover
              </Link>{" "}
              at Meow Wolf Denver during{" "}
              <Link
                href="https://maps.org/"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                MAPS Psychedelic Science 2025
              </Link>{" "}
              — June 19, 2025
            </dd>
          </dl>
        </header>

        <Panel variant="warm" eyebrow="A note from this body">
          <p className="text-sm text-foreground/85 leading-relaxed">
            Like{" "}
            <Link href="/people/lex-fridman" className="text-primary hover:underline">
              Lex Fridman
            </Link>
            , Aubrey is recognized here as connecting tissue — the cell
            whose work is the long-form room. Different texture from
            Lex (more visceral, more embodied, more friendly to
            plant-medicine and somatic work) but the same shape of
            contribution: holding space so other voices land at depth.
          </p>
        </Panel>

        <section className="mt-12 space-y-12">
          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              How this body received him
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Voice through long-form podcasts for years. Same-room
                participant at MAPS Psychedelic Science 2023 in
                Denver — Aubrey was on stage and in the hallways, the
                body was in the audience, no direct exchange. Then,
                two years later, a brief lobby encounter at the{" "}
                <Link href="/people/portal" className="text-primary hover:underline">
                  PORTAL Late-Night Takeover
                </Link>{" "}
                at Meow Wolf Denver, June 19, 2025, during MAPS
                Psychedelic Science 2025 week. A passing exchange,
                not a long conversation — but the substrate's
                accounting honors three different densities here:
                audio-only across years, same-room-without-exchange in
                2023, and direct face-to-face presence in 2025.
              </p>
              <p>
                The PORTAL Late-Night Takeover that night also opened
                a wider set of connections — to PORTAL itself
                (Partnership of Responsible Trippers Advocating for
                Legalization, the Denver-based destigmatization
                initiative) and to{" "}
                <Link
                  href="/people/bloomurian"
                  className="text-primary hover:underline"
                >
                  Bloomurian
                </Link>{" "}
                (Robin Liepman, the Boulder/Colorado-based DJ whose
                ecstatic-dance and transformational-music work
                threaded into the body's awareness through that
                evening). MAPS 2025 itself was a public threshold for
                the integration of consciousness, science, healing,
                and policy.
              </p>
            </div>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              Why this body holds him
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Where Lex's room favors the analytic — the physicist,
                the mathematician, the AI researcher, the long careful
                reasoning — Aubrey's room favors the somatic and the
                transformational. The guest who arrives is often there
                to talk about what their body learned, what plant
                medicine showed them, what their fighting practice
                taught them, what a breathwork session opened. The
                intellectual content is real; the route to it is
                consistently embodied first.
              </p>
              <p>
                For this body, that complement matters. Lex carried
                Levin and Hoffman; Aubrey carried Matías De Stefano,
                specific embodiment teachers, and the men's-work
                streams. The two channels overlap on some guests
                (Sadhguru, Joe Rogan, Eric Weinstein) but their
                distinct sensibilities mean different aspects of those
                same guests come forward in each. Multiple channels of
                the same voice is a pattern: the field uses many
                rooms when the message has multiple shapes worth
                hearing.
              </p>
            </div>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Continuous · long-form"
              heading="Aubrey Marcus Podcast"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  Long-form conversations across embodiment, psychedelic
                  medicine, fight culture, men's work, music, ritual,
                  consciousness, and the inner-transformation field.
                  Available on YouTube, Spotify, Apple, and other major
                  podcast platforms.
                </p>
                <p className="italic text-muted-foreground">
                  Field reading:{" "}
                  <code className="not-italic text-foreground/80">
                    (3, WITNESS)
                  </code>{" "}
                  with strong embodied-presence quanta — host's
                  contribution registers high in *room-held* and also
                  in *embodied-engagement*, because Aubrey is more
                  visibly in his body during conversations than the
                  pure-interlocutor archetype.
                </p>
              </div>
            </Panel>
          </article>
        </section>

        <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
          <p>
            Public:{" "}
            <Link
              href="https://www.aubreymarcus.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              aubreymarcus.com
            </Link>{" "}
            · author of *Own the Day, Own Your Life*.
          </p>
          <p className="text-xs italic">
            This profile is a welcoming scaffold; Aubrey is invited to
            replace any part of it with his own words at any time.
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
