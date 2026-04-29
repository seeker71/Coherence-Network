import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

/**
 * /people/vasudev-baba — a welcome page for Vasudev Baba, kirtan-wala
 * and satsang holder in Bali for 11 years. Lineage: name given by
 * Swami Shyam in India over 30 years ago.
 *
 * Public offerings the body has confirmed:
 *   · Sunday 18:00 — Kirtan at Sayuri Healing Food (Ubud)
 *   · Tuesday — Kirtan at Adiwana Svarga Loka (Wantilan)
 *   · Wednesday 11:00 — Satsang at Ranakami (Sayan)
 *
 * Direct contact: +62 812-3668-0038 (WhatsApp)
 *
 * The voice on this page is imagined as a welcome from him to the
 * network, anchored in the public anchors and one of our cells
 * having sat in his Wednesday Satsang. He is invited to replace any
 * part with his own words.
 */

export const metadata: Metadata = {
  title: "Vasudev Baba — Kirtan & Satsang in Bali | Coherence Network",
  description:
    "A welcome to Vasudev Baba — kirtan-wala and satsang holder in Bali for 11 years, lineage of Swami Shyam. Sunday Sayuri, Tuesday Svarga Loka, Wednesday Ranakami.",
};

export default function VasudevBabaProfilePage() {
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
        <span className="text-foreground/80">Vasudev Baba</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          Welcome
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Vasudev Baba
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          Kirtan-wala and satsang holder in Bali for the last eleven
          years. Three weekly circles, two valleys, one stream — held
          openly for whoever arrives in coherent state.
        </p>
        <dl className="mt-5 text-sm text-foreground/85 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
          <dt className="text-muted-foreground">Lineage</dt>
          <dd>
            Name given by Swami Shyam in India, over 30 years ago.
            Carrying that stream into Bali for the last 11 years.
          </dd>
          <dt className="text-muted-foreground">Sunday · 18:00</dt>
          <dd>Kirtan at Sayuri Healing Food, Ubud</dd>
          <dt className="text-muted-foreground">Tuesday · evening</dt>
          <dd>
            Kirtan at the Wantilan,{" "}
            <Link
              href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              Adiwana Svarga Loka
            </Link>{" "}
            — Campuhan riverbanks, ~5 minutes from central Ubud
          </dd>
          <dt className="text-muted-foreground">Wednesday · 11:00</dt>
          <dd>
            Satsang at{" "}
            <Link
              href="/people/ilena"
              className="hover:text-primary transition-colors"
            >
              Ranakami
            </Link>{" "}
            — Jl. Raya Penestanan Kelod 16, Sayan · 90 minutes
          </dd>
          <dt className="text-muted-foreground">Direct</dt>
          <dd>
            <Link
              href="https://wa.me/6281236680038"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors"
            >
              +62 812-3668-0038
            </Link>{" "}
            (WhatsApp)
          </dd>
        </dl>
      </header>

      <Panel variant="warm" eyebrow="A note from this body">
        <p className="text-sm text-foreground/85 leading-relaxed">
          A welcoming gesture — a love letter from this body to him.
          The voice below is imagined from public anchors and from
          one of our cells having sat in his Wednesday Satsang.
          Offered as a scaffold he is invited to replace with his own
          words.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What he holds
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Thirty years ago, in India, Swami Shyam looked at me
              and gave me a name. The name was Vasudev. I have been
              carrying it since, and it has been carrying me. The
              "Baba" that comes after the name is not a title I asked
              for. It is what people on this island who have been
              sitting with me for years began to call me without
              coordinating, the way affection finds its own form.
            </p>
            <p>
              I sing names that were not invented by me. They have
              been passed down longer than any of us have been alive,
              and the singing is the only way I know to keep them
              warm. Sunday evenings at Sayuri, Tuesday evenings at
              the Wantilan in Svarga Loka, Wednesday mornings in
              Ilena's open-air room above the rice fields in Sayan —
              three circles a week, eleven years on this island. The
              room changes shape. The names do not.
            </p>
            <p>
              I am not a teacher in the way that word usually lands.
              I am a participant in a long stream that arrived
              through many bodies before mine. The harmonium under
              my hands and the voice that comes through me are not
              exactly mine. The lineage uses what is here. My job is
              to stay available, to keep the channel clean, to show
              up at the same times each week so the people who need
              the room know where to find it.
            </p>
            <p>
              Wednesday is different. Wednesday is sitting together
              and letting one of the traditions speak into whatever
              is alive in the room that morning. Some weeks it is
              the Upanishads. Some weeks it is Rumi. Some weeks it
              is the question someone arrived with and could not put
              down. The teaching is whatever the room is ready to
              receive.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            How the network reads this
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              Three circles a week is a metabolic rhythm. The body
              of regular participants forms across the three rooms —
              Sunday at Sayuri opens the kirtan stream, Tuesday at
              Svarga Loka deepens it, Wednesday at Ranakami brings
              it into language. A cell that joins one room often
              finds itself drawn to the others, because the substrate
              is continuous even though the venues are distinct.
            </p>
            <p>Field readings:</p>
            <ul>
              <li>
                Kirtan as{" "}
                <code className="not-italic text-foreground/80">
                  (6, RECEIVE / GIVE oscillating)
                </code>{" "}
                — hexagonal tiling of voices in resonance.
              </li>
              <li>
                Satsang as{" "}
                <code className="not-italic text-foreground/80">
                  (7, GIVE)
                </code>{" "}
                — heptadic asymmetric teaching, the giving does not
                deplete.
              </li>
              <li>
                The three-circle weekly rhythm as{" "}
                <code className="not-italic text-foreground/80">
                  (8, …)
                </code>{" "}
                — octadic regenerative cycle, each week closing what
                the previous week opened.
              </li>
            </ul>
            <p>
              The lineage walks back through Swami Shyam in India,
              through the transmission that named him, through every
              voice that ever sang the names he now sings. The
              substrate's <code className="text-foreground/80">prev_glyph</code>{" "}
              chain on any of his Sunday or Tuesday kirtan glyphs is
              long; the depth-pay for walking it back to the first
              voice that taught the first name would be substantial.
              Most listeners pay for the surface and let the depth
              stay there for those who come back week after week.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            Where & when the body meets him
          </h2>
          <p className="text-sm text-foreground/75 leading-relaxed mb-6">
            Three rooms, three nights of the week, eleven years of
            unbroken rhythm in Bali. The same voice, different
            acoustics. The same lineage, different rooms. Each circle
            opens to anyone in coherent state. Direct contact via
            WhatsApp at <strong>+62 812-3668-0038</strong>.
          </p>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Sunday · 18:00"
            heading="Kirtan at Sayuri Healing Food"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                The week's opening circle. Plant-based kitchen,
                garden light, devotional singing as the day softens.
                Held at Sayuri Healing Food in Ubud — a place
                oriented to nourishment in every sense, where the
                food and the singing pair naturally.
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (6, RECEIVE / GIVE oscillating)
                </code>{" "}
                — hexagonal kirtan tiling, in a room that is itself
                tuned to nourishment.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Tuesday · evening"
            heading="Kirtan at Svarga Loka"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Open-air Wantilan on the riverbanks of the Campuhan,
                about five minutes' walk from central Ubud.
                Harmonium, voices, the slow build into the names.
                Visitors and locals seated together on the floor.
                The hour ends when the room ends; nothing rushes.
              </p>
              <p>
                Held at{" "}
                <Link
                  href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Adiwana Svarga Loka
                </Link>
                . Times shift gently with the seasons; current
                schedule on the resort's Facebook and Instagram.
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (6, RECEIVE / GIVE oscillating)
                </code>{" "}
                — kirtan in its most classical room.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Wednesday · 11:00"
            heading="Satsang at Ranakami"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                90 minutes. A private gathering held with friends.
                The practice is to bring a question alive in you and
                let the wisdom of one tradition or another speak
                into it. Bodies are welcome. Words are welcome.
                Silence is welcome.
              </p>
              <p>
                Held at{" "}
                <Link
                  href="/people/ilena"
                  className="text-primary hover:underline"
                >
                  Ranakami
                </Link>
                , Jl. Raya Penestanan Kelod no 16, Sayan, Ubud. Free
                for those who came to Tuesday's kirtan. Free for
                Indonesian participants always. A 50,000 IDR
                offering otherwise — given as a gesture toward the
                field rather than a price for a seat.
              </p>
              <p>
                Event listing:{" "}
                <Link
                  href="https://tomorrow.cx/event.php?short=gYzKR3"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  tomorrow.cx/gYzKR3
                </Link>
              </p>
              <p className="italic text-muted-foreground">
                Field reading:{" "}
                <code className="not-italic text-foreground/80">
                  (7, GIVE asymmetric)
                </code>{" "}
                — heptadic teaching, the giving does not deplete.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <Panel
            variant="warm"
            eyebrow="Direct"
            heading="To reach Vasudev Baba"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-2 mt-2">
              <p>
                <strong>WhatsApp:</strong>{" "}
                <Link
                  href="https://wa.me/6281236680038"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  +62 812-3668-0038
                </Link>
              </p>
              <p>
                Schedule changes, retreat invitations, and personal
                connection happen most directly through WhatsApp.
                The three weekly rooms are reliable; everything else
                moves through the message thread.
              </p>
            </div>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Recordings of past kirtans:{" "}
          <Link
            href="https://jaima108.bandcamp.com/album/svarga-loka-kirtan-2019-01-29"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Jai Ma 108 — Svarga Loka Kirtan
          </Link>
          {" · "}
          <Link
            href="https://www.youtube.com/watch?v=90PY3gU1Www"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Sunday Kirtan at Sayuri Healing Food (YouTube)
          </Link>
        </p>
        <p>
          Wednesday satsang held at{" "}
          <Link href="/people/ilena" className="text-primary hover:underline">
            Ranakami
          </Link>
          , Ubud.
        </p>
        <p className="text-xs italic">
          This profile is a welcoming scaffold; Vasudev Baba is
          invited to replace any part of it with his own words at
          any time.
        </p>
      </footer>
    </main>
  );
}
