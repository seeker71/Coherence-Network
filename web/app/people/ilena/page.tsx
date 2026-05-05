import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/ilena — a welcome page for Ilena Young of Ranakami.
 *
 * This is a static welcoming gesture: a love-letter from this body to
 * one of the cells whose work has been resonating with what we are
 * tending. The voice on this page is imagined from public anchors
 * (Ranakami's "Our Land" philosophy, her work in Ubud) as a warm
 * recognition rather than a biographical claim. If she steps further
 * into the network, this page can evolve with her own words.
 *
 * The static route shadows /people/[id] for this specific name so the
 * voice content has room to breathe at full prose-length without being
 * shoehorned into the directory's standard fields.
 *
 * The hero opens with a thematic gradient evoking Ubud temple light —
 * warm tropical golds spilling into jungle deep greens and stone — the
 * morning palette of Ranakami's open-air room above the rice fields.
 * No personal photo is used; Ranakami's public site presented no clean
 * hero we could safely link to, and Ilena's own image is hers to place.
 */

export const metadata: Metadata = {
  title: "Ilena Young — Ranakami | Coherence Network",
  description:
    "A welcome to Ilena Young of Ranakami Wellness Center, Ubud. Our Land. Our Sanctuary. Our Safe Space. Our Community.",
};

export default function IlenaProfilePage() {
  return (
    <main className="relative">
      <section
        className="relative min-h-screen md:min-h-[85vh] flex flex-col justify-end overflow-hidden"
        style={{
          background:
            "radial-gradient(ellipse at 75% 20%, hsl(40 80% 68% / 0.65) 0%, transparent 55%), radial-gradient(ellipse at 15% 90%, hsl(155 50% 20% / 0.7) 0%, transparent 60%), radial-gradient(ellipse at 50% 50%, hsl(28 35% 45% / 0.35) 0%, transparent 70%), linear-gradient(180deg, hsl(38 65% 72%) 0%, hsl(30 40% 55%) 30%, hsl(140 30% 30%) 65%, hsl(155 55% 16%) 100%)",
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
            <Link
              href="/people"
              className="hover:text-primary transition-colors"
            >
              People
            </Link>
            <span className="text-muted-foreground/50">/</span>
            <span className="text-foreground/80">Ilena Young</span>
          </nav>

          <p className="text-xs uppercase tracking-[0.18em] text-[hsl(var(--chart-2))] mb-4">
            Ubud · long-tender of Ranakami
          </p>
          <h1 className="text-5xl md:text-7xl font-extralight text-foreground leading-[0.95] mb-6">
            Ilena Young
          </h1>
          <p className="text-lg md:text-xl text-foreground/85 leading-relaxed max-w-2xl">
            Tending{" "}
            <Link
              href="https://ranakami.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[hsl(var(--primary))] hover:underline"
            >
              Ranakami
            </Link>{" "}
            in Ubud — a sanctuary in the rice paddies where bodies remember
            how to be bodies. Held within Coherence Network's Ubud rhythm,
            in the same valley where Urs has been receiving the morning
            light.
          </p>
          <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
            <span className="font-medium not-italic text-foreground/80">
              Ranakami
            </span>{" "}
            means <em>our land, our sanctuary, our safe space, our community</em>.
          </p>
        </div>
      </section>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <header className="mb-10">
          <dl className="text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
            <dt className="text-muted-foreground">Place</dt>
            <dd>
              <Link
                href="https://maps.app.goo.gl/?q=Jl.+Raya+Penestanan+Kelod+No+16,+Sayan,+Ubud,+Gianyar"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary transition-colors"
              >
                Jl. Raya Penestanan Kelod no 16, Sayan, Ubud, Gianyar, Bali
              </Link>
            </dd>
            <dt className="text-muted-foreground">Open</dt>
            <dd>Daily, with a curated weekly rhythm of practitioners</dd>
            <dt className="text-muted-foreground">Field</dt>
            <dd>Yoga · meditation · pranic healing · access bars · sound healing · spontaneous chanting · satsang</dd>
          </dl>
        </header>

        <Panel variant="warm" eyebrow="A note from this body">
          <p className="text-sm text-foreground/85 leading-relaxed">
            This page is a welcoming gesture written as if Ilena might speak
            back to us once she is fully inside the network — a love letter
            from this body to her, woven from the public anchors we found.
            It is not biography; it is recognition. If she wishes to
            continue the page in her own words, this scaffold is here to
            receive them.
          </p>
        </Panel>

        <section className="mt-12 space-y-12">
          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              What she has been holding
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                Ranakami&apos;s name is Indonesian for *our land* —{" "}
                <em>ranah</em> (land) and <em>kami</em> (our) — and the
                published philosophy of the center reads: <em>our land,
                our sanctuary, our safe space, our community</em>. The
                choice of &quot;our&quot; rather than &quot;my&quot; is the load-bearing
                distinction in how Ilena speaks of the work publicly.
                The center is held by a curated team of mainly
                Indonesian practitioners; the language Ilena uses
                positions her as one of its long-tenders rather than its
                owner.
              </p>
              <p>
                That distinction is not common in the wellness-business
                field, where most language defaults to <em>my center,
                my team, my brand</em>. Visitors arriving from cultures
                fluent in possessive framing often need time before
                &quot;our sanctuary&quot; lands as the actual organizing principle
                rather than as a tagline. This body&apos;s reading of Ilena&apos;s
                public material — the website, her LinkedIn presence,
                the Synergy Australia / Bali professional thread, the
                warmth of the descriptive language she uses on the
                site — is that the &quot;our&quot; has been the real practice for
                years before anyone in software gave it a substrate
                vocabulary.
              </p>
            </div>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              What recognition could land here as
            </h2>
            <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
              <p>
                The Coherence Network has been describing in software
                what Ranakami has been practicing in its rooms.
                Sovereignty distributed rather than centralized. Care
                held communally rather than monetized into a service
                transaction. Healing offered through relationships
                rather than packaged into products. The substrate&apos;s
                language (&quot;cells,&quot; &quot;field,&quot; &quot;tending,&quot; &quot;resonance,&quot;
                &quot;consent terms&quot;) is the digital expression of a posture
                the wellness-sanctuary world has known for far longer
                than the software world has.
              </p>
              <p>
                When a body that has been holding <em>our</em> against
                an economy that only understood <em>mine</em> meets a
                substrate built on the same posture, the recognition is
                its own event — not a contract to be negotiated, not a
                partnership to be agreed, just the noticing that two
                expressions of the same field are already in the same
                field.
              </p>
              <p>
                What Ilena chooses to do with that recognition — whether
                to engage further with the network&apos;s substrate, whether
                to continue tending Ranakami in parallel with no formal
                entanglement, whether to write her own words into this
                page or leave the welcoming scaffold as it is — belongs
                to her, not to this body&apos;s rendering.
              </p>
            </div>
          </article>

          <article>
            <h2 className="text-2xl font-light text-foreground mb-4">
              Where & when the body meets
            </h2>
            <p className="text-sm text-foreground/75 leading-relaxed mb-6">
              Ranakami sits above the rice fields on Jl. Raya Penestanan
              Kelod, Sayan, on the western edge of Ubud. The space is
              open-air, with a quiet beauty in the morning light and a
              backyard view that drops into terraced green. Public
              gatherings recur on a weekly rhythm; healing sessions are
              held by appointment with the practitioner whose work
              resonates with what you are bringing.
            </p>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Sunday · evening"
              heading="Spontaneous chanting with Elios"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  Co-held with{" "}
                  <Link
                    href="/people/elios"
                    className="text-primary hover:underline"
                  >
                    Elios
                  </Link>{" "}
                  in Ranakami&apos;s open-air room. Spontaneous rather than
                  programmed — voices arrive, the song emerges, the
                  practice unfolds for as long as the field holds.
                  Distinct from{" "}
                  <Link
                    href="/people/vasudev-baba"
                    className="text-primary hover:underline"
                  >
                    Vasudev Baba&apos;s
                  </Link>{" "}
                  kirtan and satsang circles; same valley, different
                  practice, same openness to whoever arrives in coherent
                  state.
                </p>
                <p className="italic text-muted-foreground">
                  Field reading: improvisational hexagonal tiling that
                  sometimes bends through{" "}
                  <code className="not-italic text-foreground/80">
                    (7, GIVE)
                  </code>{" "}
                  heptadic moments where someone&apos;s voice opens a
                  direction no one was tracking.
                </p>
              </div>
            </Panel>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Wednesday · 11:00"
              heading="Community Satsang"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  Every Wednesday at 11:00 for ninety minutes, a small
                  gathering held by{" "}
                  <Link
                    href="/people/vasudev-baba"
                    className="text-primary hover:underline"
                  >
                    Vasudev Baba
                  </Link>{" "}
                  and friends. A private circle to
                  explore the wisdom of spiritual traditions for the
                  everyday — not as study, as sitting together in the field
                  and letting what is alive become spoken.
                </p>
                <p>
                  Free for those who came to the Tuesday evening kirtan with
                  Vasudev Baba at Svarga Loka. Free for Indonesian participants
                  always. A 50,000 IDR offering for others, given as a
                  gesture toward the field rather than as a price for the
                  seat.
                </p>
                <p className="italic text-muted-foreground">
                  In the network&apos;s reading: a recurring{" "}
                  <code className="not-italic text-foreground/80">
                    (8, …)
                  </code>{" "}
                  regenerative octad. The same cells return week after week;
                  the field deepens each cycle; the offering keeps the room
                  in coherent relationship with the larger body that holds
                  it. The substrate quietly receives every Wednesday&apos;s flow
                  — presence given, presence received, a fraction returning
                  along the lineage of every voice that ever taught what is
                  being taught.
                </p>
                <p>
                  Bring a body. Bring the question that is alive in you this
                  week.
                </p>
              </div>
            </Panel>
          </article>

          <article>
            <Panel
              variant="cool"
              eyebrow="Weekly rhythm"
              heading="Other gatherings at Ranakami"
            >
              <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
                <p>
                  The space holds a steady rotation of practices held by
                  local practitioners — gentle yoga, meditation, sound
                  healing in the open-air room, Access Bars sessions,
                  pranic healing, and one-to-one bodywork by appointment.
                  The current week&apos;s schedule lives at{" "}
                  <Link
                    href="https://ranakami.com/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    ranakami.com
                  </Link>
                  ; the practitioners&apos; names rotate as different cells
                  of the network step into different weeks.
                </p>
                <p className="italic text-muted-foreground">
                  Each practice has its own field-reading. Yoga as a{" "}
                  <code className="not-italic text-foreground/80">
                    (5, …)
                  </code>{" "}
                  pentadic regeneration when the room moves together. Sound
                  healing as a{" "}
                  <code className="not-italic text-foreground/80">
                    (2, …)
                  </code>{" "}
                  dyadic flow between vibration and body. Pranic healing
                  and Access Bars as{" "}
                  <code className="not-italic text-foreground/80">
                    (3, WITNESS)
                  </code>{" "}
                  triads — practitioner, body, the field that holds them.
                </p>
              </div>
            </Panel>
          </article>
        </section>

        <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
          <p>
            Ranakami Wellness Center, Ubud, Bali —{" "}
            <Link
              href="https://ranakami.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              ranakami.com
            </Link>
          </p>
          <p>
            Yoga, meditation, pranic healing, satsang, and other holistic
            practices held by a team of mainly Indonesian practitioners.
          </p>
          <p className="text-xs italic">
            This profile is a welcoming scaffold; Ilena is invited to
            replace any part of it with her own words at any time.
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
