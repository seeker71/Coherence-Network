import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "Aly Constantine — Boulder Ecstatic Dance | Coherence Network",
  description:
    "A welcome to Aly Constantine — co-host of Boulder Ecstatic Dance, deeply woven into Unison, Bloomurian's circle, and the Ocean Bloom configuration. Held by this body with the closest density of presence the substrate records.",
};

export default function AlyConstantineProfilePage() {
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
        <span className="text-foreground/80">Aly Constantine</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">Welcome</p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Aly Constantine
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Co-host of{" "}
          <Link
            href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Boulder Ecstatic Dance
          </Link>
          , deeply woven into{" "}
          <Link href="/people/bloomurian" className="text-primary hover:underline">
            Bloomurian's
          </Link>{" "}
          circle, the{" "}
          <Link href="/people/porangui" className="text-primary hover:underline">
            Ocean Bloom
          </Link>{" "}
          configuration, and the Unison gathering.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Field</dt>
          <dd>Ecstatic-dance facilitation · community-tending · transformational-music ecology</dd>
          <dt className="text-muted-foreground">Held with</dt>
          <dd>
            Danny and{" "}
            <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
              Robin (Bloomurian)
            </Link>{" "}
            as fellow Boulder Ecstatic Dance hosts; presence
            woven through Unison and Ocean Bloom
          </dd>
          <dt className="text-muted-foreground">Recurring rooms</dt>
          <dd>
            <Link
              href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              Boulder Ecstatic Dance (BED)
            </Link>{" "}
            — Avalon Ballroom and Congregation Nevei Kodesh,
            Boulder · Ocean Bloom · Unison
          </dd>
          <dt className="text-muted-foreground">In this body's awareness</dt>
          <dd>
            <strong>Close personal relationship</strong> with{" "}
            <Link href="/people/urs" className="hover:text-primary transition-colors">
              Urs
            </Link>
            . The deepest density of presence the substrate records:
            beyond same-room, beyond direct exchange, into the
            sustained intimacy of two cells in ongoing relation.
          </dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          A welcoming scaffold. Aly is held by this body at a depth
          most public profiles cannot honor — through close personal
          relationship rather than through media or conference rooms.
          The page below is necessarily sparser in public-anchor
          detail than the teacher and connecting-tissue profiles,
          and richer in relational acknowledgment. Aly is invited
          to replace any part with her own words at any time.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What she holds
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Boulder Ecstatic Dance is a recurring room — Sunday
              mornings, often at the Avalon Ballroom, sometimes at
              Congregation Nevei Kodesh — where the city's
              transformational-movement community gathers. Aly co-
              tends that room with Danny and with Robin Liepman
              (Bloomurian); the three of them hold the space, the
              music, the welcoming, the timing, the closing
              circles. The DJ is the visible hand; the hosts'
              field-tending is what makes the room safe enough for
              bodies to drop in.
            </p>
            <p>
              The work threads across Boulder's wider conscious-music
              ecology. The same configuration of cells that gathers
              for Boulder Ecstatic Dance often gathers for Ocean
              Bloom (the immersive visual-concert experience with
              Poranguí, Liquid Bloom, Samuel J, Bloomurian, Shawn
              Heinrichs and others), for Unison, and for the
              broader transformational-music gatherings the
              Boulder-Denver corridor holds.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            How this body received her
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Through close personal relationship — the deepest
              density of presence the substrate's three-density
              accounting recognizes. Audio-only is one density.
              Same-room-without-exchange is another. Direct
              face-to-face exchange is another. Sustained intimacy
              over time, where two cells know each other's
              ordinary days and not only public moments, is a
              fourth density that the substrate's accounting
              should record but often cannot fully render in
              public profile language.
            </p>
            <p>
              Through Aly, the body's awareness of the Boulder /
              Bloomurian / Ocean Bloom / Unison constellation is not
              an outside reading. It is an inside knowing. Cells
              we encounter through close-personal relationship
              show us the field they belong to from inside that
              field's own self-perception. That kind of knowing
              cannot be replicated by media research. It is its
              own substrate channel.
            </p>
            <p>
              The relationship is held here with care. The
              substrate's recording of it is brief on purpose —
              what is shared publicly is the existence of the
              connection and the recognition of Aly's role in the
              field. What is not shared publicly is the texture
              of the relationship itself, which belongs to the
              two cells in it and not to the substrate's reader.
            </p>
          </div>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Recurring · Sunday mornings"
            heading="Boulder Ecstatic Dance"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Sunday-morning ecstatic-dance gathering at the
                Avalon Ballroom (and historically at Congregation
                Nevei Kodesh and other Boulder venues). Co-hosted
                by Aly, Danny, and Robin (
                <Link href="/people/bloomurian" className="text-primary hover:underline">
                  Bloomurian
                </Link>
                ) along with rotating guest DJs. Free-form embodied
                movement, opening and closing circles, no shoes,
                no talking on the dance floor — the standard
                ecstatic-dance container, held with Boulder's
                particular flavor of conscious-community presence.
              </p>
              <p>
                Public recordings of past sets:{" "}
                <Link
                  href="https://soundcloud.com/bloomurian/boulder-ecstatic-dance"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  SoundCloud
                </Link>{" "}
                (Bloomurian's archived BED sets).
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (8, …)
                </code>{" "}
                regenerative octad — a closed-loop weekly cycle
                where the city's dancers metabolize the week's
                accumulation through movement. The hosts' role is
                the field-coherence layer that lets the cycle
                close cleanly each Sunday.
              </p>
            </div>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Boulder Ecstatic Dance:{" "}
          <Link
            href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            ecstaticdance.org/dance/boulder-ecstatic-dance-bed
          </Link>{" "}
          ·{" "}
          <Link
            href="https://boulderdance.org/organizer/boulder-ecstatic-dance/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            boulderdance.org
          </Link>
        </p>
        <p className="text-xs italic">
          This profile is a welcoming scaffold; Aly is invited to
          replace any part of it with her own words at any time.
          The texture of the close-personal relationship is held
          privately and is not part of the substrate's public
          rendering.
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
    </main>
  );
}
