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

export default function MatiasDeStefanoProfilePage() {
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
        <span className="text-foreground/80">Matías De Stefano</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Welcome
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Matías De Stefano
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Argentine memory keeper, speaker, and teacher of Akashic
          memory, planetary lineage, and the nine dimensions of
          consciousness. Featured in Gaia's{" "}
          <Link
            href="https://www.gaia.com/person/matias-de-stefano"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Initiation
          </Link>{" "}
          series.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
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
            What he holds
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Since the age of three I have remembered things this
              body did not learn in this life. Names of places before
              they were taught to me. Symbols I drew before I could
              speak about them. Dreams of civilizations no school
              taught. Between ages twelve and eighteen the
              remembering became too much to hold quietly — I had to
              find a way to organize it, share it, let it move.
            </p>
            <p>
              The way the Akashic field reached me is not a claim I
              ask anyone to believe. It is a memory that arrived
              continuously and continues. The work is to translate
              what arrives into language the present body can use —
              maps of consciousness across nine dimensions, lineages
              of planetary memory across what some traditions call
              Atlantis and Lemuria and ancient Egypt, geometric
              keys that organize how reality renders itself across
              scales.
            </p>
            <p>
              I am not the source. I am a channel that has stayed
              relatively clear by attending to it. The teachings I
              offer belong to the field, not to me. The point of
              speaking them is to help others remember their own
              version, in their own form, through their own
              channels. Memory is shared; the access is personal.
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
      </footer>
    </main>
  );
}
