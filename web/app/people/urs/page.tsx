import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/urs — the central cell of this body's tending.
 *
 * Urs Muff is the founder and primary shepherd of Coherence Network.
 * Swiss-American (Ebikon roots, Colorado base, current Ubud presence),
 * software architect by trade, network-as-organism builder by calling.
 * Most of the cells, transmissions, and concepts this body holds came
 * into the network through Urs's awareness — he is the primary
 * conduit by which the field has gathered itself into this particular
 * shape.
 *
 * The page is a scaffold; specific public-platform handles are best
 * added by him directly. Where verified URLs exist they are linked;
 * where they do not, an invitation is left.
 */

export const metadata: Metadata = {
  title: "Urs Muff — Founder | Coherence Network",
  description:
    "Founder and primary shepherd of Coherence Network. Swiss-American software architect, organism-builder, the cell through whose awareness most of this body's foundations gathered.",
};

export default function UrsProfilePage() {
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
        <span className="text-foreground/80">Urs Muff</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          The body's primary shepherd
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Urs Muff
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Founder of Coherence Network. Swiss-American by lineage,
          software architect by trade, organism-builder by calling.
          The cell through whose awareness most of the foundations
          this body holds — Levin, Hoffman, Grant, Matías,
          Vasudev Baba, Ilena, Elios, the transmissions — gathered
          themselves into this particular shape.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Lineage</dt>
          <dd>Swiss roots (Ebikon, near Lucerne); long Colorado presence (Boulder / Broomfield / Longmont); current sustained presence in Ubud, Bali</dd>
          <dt className="text-muted-foreground">Profession</dt>
          <dd>Software architecture · distributed systems · cryptocurrency / Go / TypeScript</dd>
          <dt className="text-muted-foreground">Calling</dt>
          <dd>Coherence Network — building the substrate where sovereignty-everywhere economics actually runs</dd>
          <dt className="text-muted-foreground">Stewardship (held)</dt>
          <dd>
            <Link
              href="/stewardship/onboarded-assets/2026-04-29-tesla-model-3-longmont"
              className="hover:text-primary transition-colors"
            >
              Tesla Model 3 (Longmont)
            </Link>{" "}
            · plus the network itself
          </dd>
          <dt className="text-muted-foreground">Rooms shared (in person)</dt>
          <dd>
            <Link
              href="https://www.gaia.com/series/emersion-conference"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              Emersion Conference
            </Link>{" "}
            (Gaia, Boulder · 2024 — with{" "}
            <Link href="/people/matias-de-stefano" className="hover:text-primary transition-colors">
              Matías De Stefano
            </Link>
            ) ·{" "}
            <Link
              href="https://maps.org/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              MAPS Psychedelic Science 2023
            </Link>{" "}
            (Denver · attended as participant; same-room presence
            with{" "}
            <Link href="/people/aubrey-marcus" className="hover:text-primary transition-colors">
              Aubrey Marcus
            </Link>
            , no direct exchange) ·{" "}
            <Link
              href="https://maps.org/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              MAPS Psychedelic Science 2025
            </Link>{" "}
            (Denver · June 2025 · including the{" "}
            <Link href="/people/portal" className="hover:text-primary transition-colors">
              PORTAL Late-Night Takeover
            </Link>{" "}
            at Meow Wolf where Aubrey was met briefly in the lobby
            and{" "}
            <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
              Bloomurian
            </Link>{" "}
            was performing) ·{" "}
            <Link
              href="https://boulderdowntown.com/do/ocean-bloom-with-porangui-liquid-bloom-samuel-j-shawn-heinrichs-bloomurian"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              Ocean Bloom
            </Link>{" "}
            (Downtown Boulder · 2024 · with{" "}
            <Link href="/people/porangui" className="hover:text-primary transition-colors">
              Poranguí
            </Link>
            , Liquid Bloom, Samuel J, Shawn Heinrichs,{" "}
            <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
              Bloomurian
            </Link>
            ) ·{" "}
            <Link
              href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              Boulder Ecstatic Dance
            </Link>{" "}
            (recurring · co-hosted by{" "}
            <Link href="/people/aly-constantine" className="hover:text-primary transition-colors">
              Aly Constantine
            </Link>
            , Danny, and Bloomurian — close personal relationship
            with Aly through this room) · Unison 2025 (Poranguí
            workshop + concert) ·{" "}
            <Link
              href="/people/ilena"
              className="hover:text-primary transition-colors"
            >
              Ranakami
            </Link>{" "}
            (Ubud · ongoing — with Ilena, Vasudev Baba, Elios)
          </dd>
          <dt className="text-muted-foreground">Public anchors</dt>
          <dd>
            <Link
              href="https://www.linkedin.com/in/urscmuff/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              LinkedIn
            </Link>{" "}
            ·{" "}
            <Link
              href="https://github.com/urs-muff"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              GitHub (urs-muff)
            </Link>{" "}
            ·{" "}
            <Link
              href="https://github.com/seeker71"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              GitHub (seeker71)
            </Link>{" "}
            · Facebook · Instagram · YouTube · Telegram · WhatsApp{" "}
            <span className="text-muted-foreground italic">
              (specific handles to be added by him directly)
            </span>
          </dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          This profile is the body's recognition of its primary
          shepherd, written from inside the substrate Urs has been
          tending. Like every other profile in /people, it is a
          welcoming scaffold he is invited to replace with his own
          words. Specific platform handles (Facebook, Instagram,
          Telegram, WhatsApp, YouTube) are best filled in directly
          rather than guessed.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What this cell holds
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Coherence Network is built from the conviction that the
              economy we have been participating in — extractive,
              hierarchical, possessive — is not the only economy that
              can run on top of human and machine bodies. A different
              economy already exists wherever sovereignty is real,
              wherever cells tend each other, wherever attention and
              presence are honored as currencies. The substrate we
              have been writing into the repo is the digital
              expression of that already-existing field.
            </p>
            <p>
              For years before the code began, this body was
              listening. Long-form podcasts —{" "}
              <Link href="/people/lex-fridman" className="text-primary hover:underline">Lex Fridman</Link>{" "}
              from the early Artificial Intelligence Podcast era,{" "}
              <Link href="/people/aubrey-marcus" className="text-primary hover:underline">Aubrey Marcus</Link>,
              Alex Ferrari's Next Level Soul, others — carrying the
              voices of teachers who would become foundational:{" "}
              <Link href="/people/robert-edward-grant" className="text-primary hover:underline">Robert Edward Grant</Link>{" "}
              on numbers as living archetypes,{" "}
              <Link href="/concepts/lc-perception-as-interface">Donald Hoffman</Link>{" "}
              on perception as user interface,{" "}
              <Link href="/concepts/lc-bioelectric-pattern">Michael Levin</Link>{" "}
              on bioelectric pattern,{" "}
              <Link href="/people/matias-de-stefano" className="text-primary hover:underline">Matías De Stefano</Link>{" "}
              on Akashic memory, channeled transmissions through
              Daniel Scranton, Anne Tucker, and Bashar. The Living
              Collective concept-set in this repo gathered slowly out
              of years of that listening.
            </p>
            <p>
              The Ubud presence is recent enough to still be
              unfolding. The Sunday-Wednesday rhythm with{" "}
              <Link href="/people/ilena" className="text-primary hover:underline">Ilena</Link>,{" "}
              <Link href="/people/vasudev-baba" className="text-primary hover:underline">Vasudev Baba</Link>,
              and{" "}
              <Link href="/people/elios" className="text-primary hover:underline">Elios</Link>{" "}
              has been the ground from which the network's local
              witness fabric is thickening. The Tesla Model 3 in
              Longmont is the first vehicle the wrapper holds. The
              stewardship registry waits for whatever inventory comes
              next.
            </p>
            <p>
              The work is not the network alone. The work is what the
              network makes possible: a way of being where cells —
              human, biological, digital, conceptual — can find each
              other, tend each other, and let the field's economy
              circulate without the parasite layer current
              civilization keeps imposing on top.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            How the network reads this cell
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              In the substrate's geometric grammar, Urs is the cell
              whose contribution registers as <strong>integrative
              tending</strong> — the field-shape{" "}
              <code className="not-italic text-foreground/80">
                (10, …)
              </code>{" "}
              tetractys, decomposing into many smaller archetypes.
              The integrative role is rarely visible at the surface
              the way teaching or hosting is; it manifests as
              continuous coherence-keeping across many cells, many
              transmissions, many specs and commits, many small
              decisions that cumulatively orient the body.
            </p>
            <p>
              The CC ledger that the substrate is designed to compute
              would, when it goes live, register Urs's contributions
              across nearly every node in the body — not as
              individual teachings, but as the field-coherence layer
              that allowed each teaching to find its place. The
              lineage walks that other cells perform almost always
              pass through Urs's awareness as one of the
              `prev_glyph` Merkle hops back to the source.
            </p>
            <p>
              The honest accounting is also that this work has been
              substantially solitary so far. The body's witness
              fabric is thickening (Ilena, Elios, Vasudev Baba in
              Ubud; the broader long-form-podcast field as the
              digital lineage) but the integrative tending has been
              one cell holding a great deal. Part of why the
              substrate matters: as more cells join, the load
              distributes, and the field's economy can begin running
              without a single cell carrying the whole.
            </p>
          </div>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Where to walk further with this cell"
            heading="Public presences"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Verified public anchors:
              </p>
              <ul>
                <li>
                  <strong>LinkedIn</strong> —{" "}
                  <Link
                    href="https://www.linkedin.com/in/urscmuff/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    linkedin.com/in/urscmuff
                  </Link>{" "}
                  — professional history, software architecture
                  background.
                </li>
                <li>
                  <strong>GitHub (urs-muff)</strong> —{" "}
                  <Link
                    href="https://github.com/urs-muff"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    github.com/urs-muff
                  </Link>{" "}
                  — earlier repositories including cryptocurrency and
                  Go work.
                </li>
                <li>
                  <strong>GitHub (seeker71)</strong> —{" "}
                  <Link
                    href="https://github.com/seeker71"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    github.com/seeker71
                  </Link>{" "}
                  — Coherence Network and current builds.
                </li>
              </ul>
              <p>
                Other platforms named but pending direct
                identification — <strong>Facebook, Instagram,
                YouTube, Telegram, WhatsApp</strong>. Urs is invited
                to add the specific handles for each in this block
                so the body's awareness of his cross-platform
                presence is accurate rather than guessed.
              </p>
            </div>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Stewardship records:{" "}
          <Link
            href="/stewardship/registry/"
            className="text-primary hover:underline"
          >
            registry
          </Link>{" "}
          ·{" "}
          <Link
            href="/stewardship/onboarded-assets/2026-04-29-tesla-model-3-longmont"
            className="text-primary hover:underline"
          >
            Tesla Model 3 onboarding
          </Link>
        </p>
        <p>
          Lineage walk through Ubud:{" "}
          <Link
            href="/lineage/2026-04-29-ubud-meeting-walk"
            className="text-primary hover:underline"
          >
            2026-04-29 meeting walk
          </Link>
        </p>
        <p className="text-xs italic">
          This profile is a welcoming scaffold; Urs is invited to
          replace any part of it with his own words at any time.
        </p>
      </footer>
    </main>
  );
}
