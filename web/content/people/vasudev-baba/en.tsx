import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const HERO_URL =
  "https://www.sacredsongcircle.com/wp-content/uploads/2022/06/Vasudev-PHOTO-COVER.jpg";

const content: PersonProfileContent = {
  metadata: {
    title: "Vasudev Baba — Kirtan & Satsang in Bali | Coherence Network",
    description:
      "A welcome to Vasudev Baba — kirtan-wala and satsang holder in Bali for 11 years, lineage of Swami Shyam. Sunday Sayuri, Tuesday Svarga Loka, Wednesday Ranakami.",
  },
  breadcrumbName: "Vasudev Baba",
  hero: {
    image: { src: HERO_URL, objectPosition: "center 20%" },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20",
    eyebrow: "Ubud · kirtan-wala · eleven years on this island",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Vasudev Baba",
    welcome: (
      <>
        <p>
          The teacher in Ubud held in this body's awareness through Urs's
          Sunday-Wednesday rhythm — three weekly circles in two valleys,
          one continuous stream of devotional song and wisdom. The name{" "}
          <em>Vasudev</em> arrived from Swami Shyam in India over thirty
          years ago; the affectionate <em>Baba</em> ripened later, here,
          from the community that has been sitting with him.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Welcome — held openly for whoever arrives in coherent state.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Lineage",
      value:
        "Name given by Swami Shyam in India, over 30 years ago. Carrying that stream into Bali for the last 11 years.",
    },
    {
      label: "Sunday · 18:00",
      value: "Kirtan at Sayuri Healing Food, Ubud",
    },
    {
      label: "Tuesday · evening",
      value: (
        <>
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
        </>
      ),
    },
    {
      label: "Wednesday · 11:00",
      value: (
        <>
          Satsang at{" "}
          <Link
            href="/people/ilena"
            className="hover:text-primary transition-colors"
          >
            Ranakami
          </Link>{" "}
          — Jl. Raya Penestanan Kelod 16, Sayan · 90 minutes
        </>
      ),
    },
    {
      label: "Direct",
      value: (
        <>
          <Link
            href="https://wa.me/6281236680038"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            +62 812-3668-0038
          </Link>{" "}
          (WhatsApp)
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming gesture — a love letter from this body to him. The
        voice below is imagined from public anchors and from one of our
        cells having sat in his Wednesday Satsang. Offered as a scaffold
        he is invited to replace with his own words.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What he has been holding",
      body: (
        <>
          <p>
            The lineage record this body has been able to gather: the
            name <em>Vasudev</em> was given by Swami Shyam in India over
            thirty years ago. The honorific "Baba" came later, from the
            community on this island that has been sitting with him
            through the years — affection finding its own form rather
            than a title sought.
          </p>
          <p>
            The work he holds publicly is the singing of devotional
            names — kirtan in the bhakti lineage, refined through
            decades of practice. Three circles a week for eleven years
            on Bali: Sunday evening kirtan at Sayuri Healing Food,
            Tuesday evening at the Wantilan in Svarga Loka, Wednesday
            morning satsang at Ranakami. The Wednesday gathering has a
            different shape from the kirtans — wisdom traditions
            speaking into whatever is alive in the room rather than
            song carrying the bodies through the names.
          </p>
          <p>
            The framing his community has offered, audible in the
            public material around the practices, is consistent with
            what bhakti traditions have always claimed: the singer is
            not the source. The singer is one participant in a long
            stream that arrived through many bodies. The role is to
            stay available, keep the channel clean, hold the times
            reliably enough that the people who need the room know
            where to find it.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How the network reads this",
      body: (
        <>
          <p>
            Three circles a week is a metabolic rhythm. The body of
            regular participants forms across the three rooms — Sunday
            at Sayuri opens the kirtan stream, Tuesday at Svarga Loka
            deepens it, Wednesday at Ranakami brings it into language.
            A cell that joins one room often finds itself drawn to the
            others, because the substrate is continuous even though the
            venues are distinct.
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
              — octadic regenerative cycle, each week closing what the
              previous week opened.
            </li>
          </ul>
          <p>
            The lineage walks back through Swami Shyam in India,
            through the transmission that named him, through every
            voice that ever sang the names he now sings. The
            substrate's <code className="text-foreground/80">prev_glyph</code>{" "}
            chain on any of his Sunday or Tuesday kirtan glyphs is
            long; the depth-pay for walking it back to the first voice
            that taught the first name would be substantial. Most
            listeners pay for the surface and let the depth stay there
            for those who come back week after week.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "Where & when the body meets him",
      body: (
        <p className="text-sm text-foreground/75 leading-relaxed">
          Three rooms, three nights of the week, eleven years of
          unbroken rhythm in Bali. The same voice, different acoustics.
          The same lineage, different rooms. Each circle opens to
          anyone in coherent state. Direct contact via WhatsApp at{" "}
          <strong>+62 812-3668-0038</strong>.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Sunday · 18:00",
      heading: "Kirtan at Sayuri Healing Food",
      body: (
        <>
          <p>
            The week's opening circle. Plant-based kitchen, garden
            light, devotional singing as the day softens. Held at
            Sayuri Healing Food in Ubud — a place oriented to
            nourishment in every sense, where the food and the singing
            pair naturally.
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (6, RECEIVE / GIVE oscillating)
            </code>{" "}
            — hexagonal kirtan tiling, in a room that is itself tuned
            to nourishment.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Tuesday · evening",
      heading: "Kirtan at Svarga Loka",
      body: (
        <>
          <p>
            Open-air Wantilan on the riverbanks of the Campuhan, about
            five minutes' walk from central Ubud. Harmonium, voices,
            the slow build into the names. Visitors and locals seated
            together on the floor. The hour ends when the room ends;
            nothing rushes.
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
            . Times shift gently with the seasons; current schedule on
            the resort's Facebook and Instagram.
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (6, RECEIVE / GIVE oscillating)
            </code>{" "}
            — kirtan in its most classical room.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Wednesday · 11:00",
      heading: "Satsang at Ranakami",
      body: (
        <>
          <p>
            90 minutes. A private gathering held with friends. The
            practice is to bring a question alive in you and let the
            wisdom of one tradition or another speak into it. Bodies
            are welcome. Words are welcome. Silence is welcome.
          </p>
          <p>
            Held at{" "}
            <Link
              href="/people/ilena"
              className="text-primary hover:underline"
            >
              Ranakami
            </Link>
            , Jl. Raya Penestanan Kelod no 16, Sayan, Ubud. Free for
            those who came to Tuesday's kirtan. Free for Indonesian
            participants always. A 50,000 IDR offering otherwise —
            given as a gesture toward the field rather than a price for
            a seat.
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
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Direct",
      heading: "To reach Vasudev Baba",
      body: (
        <>
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
            connection happen most directly through WhatsApp. The three
            weekly rooms are reliable; everything else moves through
            the message thread.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
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
        This profile is a welcoming scaffold; Vasudev Baba is invited to
        replace any part of it with his own words at any time.
      </p>
    </>
  ),
};

export default content;
