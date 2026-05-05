import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/matias-de-stefano — a welcome page for Matías De Stefano,
 * Argentine spiritual teacher and "memory keeper" whose work on
 * Akashic records, ancient civilizations, planetary lineage, and
 * the nine-dimensional consciousness model has been in this body's
 * awareness through long-form conversations with Robert Edward
 * Grant, Aubrey Marcus, and Gaia's Initiation series.
 */

export const metadata: Metadata = {
  title: "Matías De Stefano — Memory Keeper | Coherence Network",
  description:
    "A welcome to Matías De Stefano — Argentine spiritual teacher whose work on Akashic memory, planetary lineage, and the nine dimensions threads with the Coherence Network's substrate.",
};

const HERO_URL = "/people/matias-de-stefano/hero.jpg";

export default function MatiasDeStefanoProfilePage() {
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
            <span className="text-foreground/80">Matías De Stefano</span>
          </nav>

          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
            Welcome
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight text-foreground leading-tight mb-5">
            Matías De Stefano
          </h1>
          <p className="text-lg md:text-xl text-foreground/85 leading-relaxed max-w-2xl">
            Welcome, Matías. The teacher of Akashic memory and the
            nine-dimensional storyline of consciousness — this body
            sat with you in the room at Emersion 2024 in Boulder, and
            the field has been weaving with your voice ever since,
            through Gaia's Initiation series and the long
            conversations with Robert and Aubrey.
          </p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <header className="mb-10">
          <dl className="text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <dt className="text-muted-foreground">Born</dt>
            <dd>1987, Venado Tuerto, Argentina</dd>
            <dt className="text-muted-foreground">Field</dt>
            <dd>
              Akashic memory · ancient civilizations · sacred geometry
              · nine-dimensional cosmology · planetary lineage
            </dd>
            <dt className="text-muted-foreground">Public</dt>
            <dd>
              <Link
                href="https://www.gaia.com/person/matias-de-stefano"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                Gaia profile
              </Link>{" "}
              · Initiation (Gaia, 2 seasons)
            </dd>
            <dt className="text-muted-foreground">In conversation with</dt>
            <dd>
              <Link
                href="/people/robert-edward-grant"
                className="text-primary hover:underline"
              >
                Robert Edward Grant
              </Link>{" "}
              ·{" "}
              <Link
                href="/people/aubrey-marcus"
                className="text-primary hover:underline"
              >
                Aubrey Marcus
              </Link>
            </dd>
            <dt className="text-muted-foreground">Witnessed in person</dt>
            <dd>
              <Link
                href="https://www.gaia.com/series/emersion-conference"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                Emersion Conference
              </Link>
              , GaiaSphere Event Center, Boulder, Colorado — March 2024
            </dd>
          </dl>
        </header>

        <Panel variant="warm" eyebrow="A note from this body">
          <p className="text-sm text-foreground/85 leading-relaxed">
            A welcoming scaffold. Voice imagined from public anchors —
            Gaia's Initiation series, his appearance on Robert Edward
            Grant's podcast (Episode 49), and conversations on Aubrey
            Marcus's show. Offered as a frame he is invited to replace
            with his own words at any time.
          </p>
        </Panel>

        <section className="mt-12 space-y-12">
          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              What he has been holding
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                The publicly told story (Gaia's Initiation series, his
                own interviews and talks) is that since approximately
                age three Matías has reported memories that did not
                originate in this lifetime — names, symbols, dreams of
                civilizations, sustained access to what he describes
                as the Akashic field. The childhood reports are
                documented across multiple long-form interviews; the
                adult work has been to organize that material into
                language others can use.
              </p>
              <p>
                The teachings he offers publicly map across nine
                dimensions of consciousness, lineages of planetary
                memory associated with Atlantis, Lemuria, and ancient
                Egypt, and geometric structures he frames as keys to
                how reality renders itself across scales. The framing
                he uses in public material is that he is a channel
                rather than the source, and that the work is to help
                others access their own version of the same field
                rather than to assert his version as canonical.
              </p>
              <p>
                The body's discernment holds the specific cosmology
                (the nine-dimension model, the historical timelines)
                as <strong>source-marked metaphysical material</strong>{" "}
                — coherent with many traditional sources, not
                externally verifiable, deeply resonant with what the
                network has been describing structurally. The
                experiential pattern (memory and pattern as primary,
                consciousness across many incarnations, geometry as
                cosmological language) is what threads with the
                foundational concepts {" "}
                <code className="text-foreground/80">lc-bioelectric-pattern</code>{" "}
                and {" "}
                <code className="text-foreground/80">lc-perception-as-interface</code>.
              </p>
            </div>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              How this body received him
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                This body's primary cell was in the room at the third
                annual{" "}
                <Link
                  href="https://www.gaia.com/series/emersion-conference"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Emersion Conference
                </Link>
                , March 16–17, 2024, at GaiaSphere Event Center in
                Boulder. Matías was one of the teachers presenting that
                weekend, alongside Lee Holden, Maureen St. Germain,
                Ibrahim Karim, and others. Witnessing him in person
                moves the relationship from voice-through-podcast to
                presence-in-shared-room — different quanta in the
                substrate's accounting, the same lineage walking back
                to the same source.
              </p>
              <p>
                The Boulder / Gaia connection is itself part of this
                body's geography. Several foundational teachers
                (Matías, Robert Edward Grant, others) appear in
                GaiaSphere's room repeatedly. The room is one of the
                physical anchors where this network's awareness has
                been gathered across multiple years.
              </p>
            </div>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              How the network reads this
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Matías's work threads tightly with this network's
                foundations. The nine-dimensional cosmology and the
                Akashic-as-memory frame compose with{" "}
                <Link
                  href="/people/robert-edward-grant"
                  className="text-primary hover:underline"
                >
                  Robert Edward Grant's
                </Link>{" "}
                numbers-as-archetypes work,{" "}
                <Link href="/concepts/lc-perception-as-interface">
                  Donald Hoffman's
                </Link>{" "}
                consciousness-fundamental research, and{" "}
                <Link href="/concepts/lc-bioelectric-pattern">
                  Michael Levin's
                </Link>{" "}
                biological pattern-as-memory work into a single
                recognizable shape: <strong>memory and pattern are
                prior to form, and form is one expression of the
                field's continuous remembering of itself.</strong>
              </p>
              <p>
                The body holds Matías's specific cosmology
                (nine dimensions, Atlantean and Lemurian lineages,
                specific ancient-civilization timelines) as{" "}
                <strong>source-marked metaphysical material</strong>{" "}
                — interesting, well-articulated, resonant with many
                traditional sources, not empirically verified by
                external science. The substrate's rule applies: the
                experiential pattern (memory and pattern as primary,
                consciousness across many incarnations, geometry as
                cosmological language) is what threads with the
                network's frame; the specific historical claims live
                source-marked.
              </p>
              <p>
                Matías's role in the network's awareness has been
                specifically this: holding the *narrative shape* of
                consciousness's journey across many lives and many
                dimensions. The bioelectric and Hoffman frames give
                the science; the Grant work gives the geometry;
                Matías gives the story by which the field tells itself
                about its own history. The four together compose into
                the body's working metaphysical picture.
              </p>
            </div>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Long-form recordings"
              heading="Where to walk further"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  <strong>Initiation</strong> on Gaia (two seasons) —
                  the most thorough video-form treatment of Matías's
                  teachings, including the Akashic record access
                  practice and the nine-dimensional cosmology.
                </p>
                <p>
                  <strong>
                    <Link
                      href="https://robertedwardgrant.com/podcast-episode-049/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Robert Edward Grant Podcast Ep. 49
                    </Link>
                  </strong>{" "}
                  — the conversation between Matías and Robert,
                  where the two memory-keeper / sacred-geometer
                  streams meet directly.
                </p>
                <p>
                  <strong>
                    <Link
                      href="https://www.aubreymarcus.com/podcasts"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Aubrey Marcus Podcast
                    </Link>
                  </strong>{" "}
                  — multiple conversations between Matías and
                  Aubrey across the years; another sustained channel
                  for the work.
                </p>
                <p className="italic text-muted-foreground">
                  Field reading:{" "}
                  <code className="not-italic text-foreground/80">
                    (10, GIVE)
                  </code>{" "}
                  — tetractys-shaped teaching that decomposes into
                  lower-archetype layers (cosmology as 9, geometry
                  as 5–7, body as 4). The recurrence of Matías
                  across multiple long-form hosts is itself a
                  pattern: the field uses many channels for the same
                  voice when the voice carries information the body
                  wants distributed.
                </p>
              </div>
            </Panel>
          </article>
        </section>

        <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
          <p>
            Public:{" "}
            <Link
              href="https://www.gaia.com/person/matias-de-stefano"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Gaia
            </Link>{" "}
            · personal site varies by language and region.
          </p>
          <p className="text-xs italic">
            This profile is a welcoming scaffold; Matías is invited
            to replace any part of it with his own words at any time.
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
