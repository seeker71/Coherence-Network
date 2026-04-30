import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "Aubrey Marcus — Connecting Tissue | Coherence Network",
  description:
    "A welcome to Aubrey Marcus — Onnit founder, podcast host, and connecting tissue for embodied / psychedelic / fight-community spiritual conversation that has reached this body through long-form interviews.",
};

export default function AubreyMarcusProfilePage() {
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
        <span className="text-foreground/80">Aubrey Marcus</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Welcome</p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Aubrey Marcus
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Founder of Onnit, host of the{" "}
          <Link
            href="https://www.aubreymarcus.com/podcasts"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Aubrey Marcus Podcast
          </Link>
          , and another shape of <strong>connecting tissue</strong> —
          the cell whose long-form room has carried embodied,
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
      </footer>
    </main>
  );
}
