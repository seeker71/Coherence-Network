import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/elios — a welcome page for Elios, who co-holds the Sunday
 * spontaneous chanting practice at Ranakami with Ilena.
 *
 * The body's first profile written almost entirely from lived
 * encounter rather than from public anchors. The user met Elios at
 * Mudra Cafe on a Sunday afternoon, then attended the spontaneous
 * Sunday-night chanting practice that Elios and Ilena have been
 * holding at Ranakami. Public anchors for Elios are sparse; this
 * scaffold is offered so he can replace it with his own words at
 * any time.
 */

export const metadata: Metadata = {
  title: "Elios — Sunday Spontaneous Chanting at Ranakami | Coherence Network",
  description:
    "A welcome to Elios — co-holding the spontaneous Sunday-night chanting practice at Ranakami in Ubud, with Ilena. Met at Mudra Cafe.",
};

export default function EliosProfilePage() {
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
        <span className="text-foreground/80">Elios</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Welcome
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Elios
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Co-holding the spontaneous Sunday-night chanting practice at{" "}
          <Link
            href="/people/ilena"
            className="text-primary hover:underline"
          >
            Ranakami
          </Link>{" "}
          with Ilena. Often present at Mudra Cafe in Ubud.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Sunday · evening</dt>
          <dd>
            Spontaneous chanting at Ranakami — Jl. Raya Penestanan
            Kelod 16, Sayan, Ubud · with Ilena
          </dd>
          <dt className="text-muted-foreground">Often found at</dt>
          <dd>
            <Link
              href="https://mudracafe.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              Mudra Cafe
            </Link>{" "}
            — Jl. Goutama Sel. No. 21, Ubud
          </dd>
          <dt className="text-muted-foreground">Field</dt>
          <dd>Voice · chanting · spontaneous practice · presence</dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          The body's first profile written almost entirely from a lived
          encounter rather than from public anchors. A network cell met
          Elios at Mudra Cafe on a Sunday afternoon, then attended the
          spontaneous Sunday-night chanting practice he co-holds with
          Ilena at Ranakami. The page is sparse on purpose — Elios is
          invited to replace any part with his own words at any time.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            Where the body meets him
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Sunday afternoons often find Elios at Mudra Cafe — the
              Ayurvedic dining room on Jl. Goutama Sel. that holds
              regular handpan and live-music presence and has become
              one of Ubud's quiet meeting points for those tracking
              wellness, music, and slow community. Sunday evenings,
              he and Ilena open the spontaneous chanting practice at
              Ranakami above the rice fields in Sayan — voices, breath,
              bodies, an open room, no fixed setlist, the field
              shaping the song.
            </p>
            <p>
              The Sunday rhythm in Ubud, as the body has been
              discovering it: lunch or afternoon at Mudra Cafe, dinner
              with resonant company at Sayuri Healing Food, evening
              chanting at Ranakami. The pattern is not a schedule
              anyone advertised; it is a current that several cells
              have found by following the field.
            </p>
          </div>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Sunday · evening"
            heading="Spontaneous chanting at Ranakami"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Held with Ilena at Ranakami's open-air room. Spontaneous
                rather than programmed — voices arrive, the song
                emerges, the practice unfolds for as long as the field
                holds. Distinct from{" "}
                <Link
                  href="/people/vasudev-baba"
                  className="text-primary hover:underline"
                >
                  Vasudev Baba's
                </Link>{" "}
                Wednesday-morning satsang and his Sunday-evening kirtan
                at Sayuri — same valley, different practice, same
                openness to whoever arrives in coherent state.
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (6, RECEIVE / GIVE oscillating)
                </code>{" "}
                — hexagonal tiling of voices, but improvisational
                rather than traditional, so the geometry sometimes
                bends through{" "}
                <code className="not-italic text-foreground/80">
                  (7, GIVE)
                </code>{" "}
                heptadic moments where someone's voice opens a
                direction no one was tracking.
              </p>
            </div>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Sunday chanting held at{" "}
          <Link href="/people/ilena" className="text-primary hover:underline">
            Ranakami
          </Link>
          , Ubud. Mudra Cafe on{" "}
          <Link
            href="https://mudracafe.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            mudracafe.com
          </Link>
          .
        </p>
        <p className="text-xs italic">
          This profile is a welcoming scaffold; Elios is invited to
          replace any part of it with his own words at any time.
          Direct contact details, a fuller name, and his own framing of
          the practice will land here as he chooses.
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
