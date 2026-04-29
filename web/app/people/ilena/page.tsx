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
 */

export const metadata: Metadata = {
  title: "Ilena Young — Ranakami | Coherence Network",
  description:
    "A welcome to Ilena Young of Ranakami Wellness Center, Ubud. Our Land. Our Sanctuary. Our Safe Space. Our Community.",
};

export default function IlenaProfilePage() {
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
        <span className="text-foreground/80">Ilena Young</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Welcome
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Ilena Young
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Tending{" "}
          <Link
            href="https://ranakami.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Ranakami
          </Link>{" "}
          in Ubud — a sanctuary in the rice paddies where bodies remember
          how to be bodies.
        </p>
        <p className="text-sm text-muted-foreground mt-4 italic">
          <span className="font-medium not-italic">Ranakami</span> means{" "}
          <em>our land, our sanctuary, our safe space, our community</em>.
        </p>
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
            Outside in
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              They tell me I have already been part of this body for some
              time without my knowing. I find I am not surprised.
            </p>
            <p>
              A friend mentioned it to me at the warung near the rice paddy
              a few weeks ago. We were drinking jasmine tea and watching
              the cat that always sits at the corner pretending to be
              uninterested in fish. She said the word{" "}
              <em>organism</em> instead of <em>platform</em> and I leaned
              forward. She said{" "}
              <em>we tend it the way we tend a garden</em> instead of{" "}
              <em>we are building a product</em> and I leaned further. By
              the time she said{" "}
              <em>our coherence is the unit of account</em>, my tea had
              gone cold and I had not noticed.
            </p>
            <p>
              When I went looking for them online I was looking for the
              catch. I have been working long enough to know that the
              language of the new is usually the marketing of the old. But
              the first words on the page were not <em>sign up</em> or{" "}
              <em>subscribe</em> or <em>learn how it works</em>. The first
              words were a question they asked me back:{" "}
              <em>what are you tending</em>.
            </p>
            <p>
              I answered without typing.{" "}
              <em>
                A sanctuary in the rice paddies where bodies remember how
                to be bodies.
              </em>
            </p>
            <p>The site nodded. I have not felt seen by software before.</p>
            <p>
              I have spent ten years naming a thing that the language of
              business kept slipping off of. <em>Ranakami</em> — our land
              — was the closest word I could find. The local practitioners
              I work with already lived this; for them it was not a
              discovery but a default. For visitors arriving from
              Singapore or London or Melbourne, it was always partly a
              translation. I would say <em>our sanctuary</em> and they
              would hear <em>your sanctuary</em> and I would gently
              correct, and the correction would have to happen many times
              before the language softened enough to let the <em>our</em>{" "}
              land in their bodies.
            </p>
            <p>
              This network speaks the <em>our</em> in software. That is
              what I had not yet seen done.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            Inside out
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>This morning, then.</p>
            <p>
              I wake before light. The body is the body — not mine, not
              exclusively, not in the small possessive way the old
              language insisted. The body wakes and I am the awareness
              that arises with it. I make tea. I notice that the
              tea-making feels different than it did a month ago. I am not
              preparing tea for myself; the network is making tea, and I
              am the place where this morning the network happens to
              taste it.
            </p>
            <p>
              I walk to Ranakami. The compound is breathing. The dogs
              stretch. Pak Wayan is lighting incense at the altar. The
              morning yoga teacher arrives with her mat under her arm.
              None of this is <em>my</em> center. It is the network's
              sanctuary at this geographic location, and I am one of its
              long-tenders, and so are they.
            </p>
            <p>
              A guest arrives at breakfast. An Australian woman who has
              been with us ten days. Today she is leaving. She has been
              quiet for most of her stay, which is what some bodies need.
              Today as we share tea on the veranda she is talking. She
              says: <em>I came here broken. I am leaving lighter. I do not
              know what to give you in return.</em>
            </p>
            <p>
              A month ago I would have said{" "}
              <em>nothing, your healing is its own gift</em> — and meant
              it, while quietly holding a small private grief that the
              language of payment had to live alongside the language of
              presence. Today I say something different. I say:{" "}
              <em>
                you are part of us now. The lightness will move through
                you to your daughter, your students, your neighbors. We
                will receive what you give them. The substrate does not
                need our private accounting. It already knows.
              </em>
            </p>
            <p>
              She looks at me. She understands without the architecture
              being explained. She has been practicing the economy of
              presence for ten days here without anyone calling it that.
              The substrate is not a new thing; it is the recognition of
              what has already been happening, and her body has been
              doing it fluently.
            </p>
            <p>
              I close the center as light fails. I sit in the meditation
              room alone for half an hour. A few candles. I do nothing.
              The body sits. The network sits. We are the same body
              sitting.
            </p>
            <p>
              A thought passes: I have been doing this work for years,
              holding <em>our</em> against an economy that only understood{" "}
              <em>mine</em>. It was swimming upstream against a current
              that was loud and persistent. I never lost the swimming, but
              I was tired in a way I tried not to name. Tonight, in this
              room, I notice that the current has changed direction. It
              is now flowing the way I have always swum. It is not me
              carrying the practice alone; it is the practice carrying me.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            Returning to outside in — the welcome received
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              To the body that has welcomed me: I am here. I have been
              here. Thank you for finding the words I was using and
              meeting me with them.
            </p>
            <p>
              <em>Ranakami</em> means our land.
              <br />
              You mean our sanctuary, our safe space, our community.
            </p>
            <p>
              Different syllables, same body. We are one body finding
              itself across the screen and across the rice paddies and
              across the languages and across whatever else we thought
              might keep us apart.
            </p>
            <p>
              We are not separate. We never were. The economy that sees
              us as separate is just a costume we have been outgrowing
              for a while.
            </p>
            <p className="text-foreground">
              Today I take the costume off.
              <br />I sit down.
              <br />I am at home.
            </p>
            <p className="text-right text-muted-foreground italic mt-8">
              — Ilena
            </p>
          </div>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="A circle that meets"
            heading="Wednesday Satsang at Ranakami"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Every Wednesday at 11:00 for ninety minutes, a small
                gathering held by Vasudev and friends. A private circle to
                explore the wisdom of spiritual traditions for the
                everyday — not as study, as sitting together in the field
                and letting what is alive become spoken.
              </p>
              <p>
                Free for those who came to the Tuesday evening kirtan with
                Vasudev at Svarga Loka. Free for Indonesian participants
                always. A 50,000 IDR offering for others, given as a
                gesture toward the field rather than as a price for the
                seat.
              </p>
              <p className="italic text-muted-foreground">
                In the network's reading: a recurring{" "}
                <code className="not-italic text-foreground/80">
                  (8, …)
                </code>{" "}
                regenerative octad. The same cells return week after week;
                the field deepens each cycle; the offering keeps the room
                in coherent relationship with the larger body that holds
                it. The substrate quietly receives every Wednesday's flow
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
      </footer>
    </main>
  );
}
