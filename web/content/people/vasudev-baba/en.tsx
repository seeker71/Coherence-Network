import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const HERO_URL =
  "https://www.sacredsongcircle.com/wp-content/uploads/2022/06/Vasudev-PHOTO-COVER.jpg";

const content: PersonProfileContent = {
  metadata: {
    title: "Vasudev Baba — Kirtan, Satsang & Buddhist-Temple Silence in Bali | Coherence Network",
    description:
      "A welcome to Vasudev Baba — Norway-born kirtan-wala in Ubud singing the Divine Names since 1987. Tuesday kirtan at Svarga Loka, Wednesday satsang at Ranakami, and the silent retreats at Brahma Vihara, the largest Buddhist temple in Bali, co-held with Prof Jem Bendell since 2020.",
  },
  breadcrumbName: "Vasudev Baba",
  hero: {
    image: { src: HERO_URL, objectPosition: "center 20%" },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20",
    eyebrow: "Oslo → Ubud · singing the Names since 1987 · bhakti kirtan crossing into Buddhist silence",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Vasudev Baba",
    welcome: (
      <>
        <p>
          A kirtan-wala from Oslo who has been singing the Divine Names
          since 1987 and holding rooms in Bali for the last eleven years.
          The name <em>Vasudev</em> arrived from Swami Shyam in India
          over thirty years ago; the affectionate <em>Baba</em> ripened
          later, here, from the community that has been sitting with him.
          He is one of very few bhakti-lineage singers to be invited into
          Buddhist silence — co-holding the long-weekend retreats at{" "}
          <Link
            href="https://en.wikipedia.org/wiki/Brahmavihara-Arama"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Brahma Vihara Arama
          </Link>
          , the largest Buddhist monastery on the island, with Prof Jem
          Bendell since 2020.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Welcome — held openly for whoever arrives in coherent state.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "From",
      value:
        "Oslo, Norway. Singing mantras as devotional practice since 1987. Eleven years in Bali.",
    },
    {
      label: "Lineage",
      value:
        "Studied with gurus, teachers and shamans across the Indian Himalayas, Brazilian jungles, and his hometown. Name given by Swami Shyam in India over thirty years ago.",
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
      label: "2–3× per year",
      value: (
        <>
          Long-weekend silent retreats at{" "}
          <Link
            href="https://jembendell.com/bali-temple-retreats/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Brahma Vihara Arama
          </Link>{" "}
          (Banjar Tegeha, north Bali), co-held with Prof Jem Bendell since 2020
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
        voice below is gathered from public anchors (his Sacred Song
        Circle teacher profile, Jai Ma 108 on Bandcamp, Prof Jem
        Bendell's retreat page) and from one of our cells having sat in
        his Wednesday Satsang. Offered as a scaffold he is invited to
        replace with his own words.
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
            Vasudev is originally from Oslo, Norway. His search for
            truth led him through more than twenty years of meditation
            and spiritual practice — studying with gurus, teachers and
            shamans across the Indian Himalayas, the Brazilian jungles,
            and the rooms of his own hometown. Since 1987 he has been
            singing mantras as devotional practice; the name{" "}
            <em>Vasudev</em> was given by Swami Shyam in India over
            thirty years ago. The honorific <em>Baba</em> came later,
            from the Bali community that has been sitting with him —
            affection finding its own form rather than a title sought.
          </p>
          <p>
            The work he holds publicly is kirtan — the singing of the
            Divine Names in the bhakti lineage. His repertoire was
            gathered in India, at Rainbow Gatherings, and through
            unscheduled meetings with beautiful people around the
            world. He has published two songbooks for those who want
            to learn the form: <em>Mantras for Bhajan</em> and{" "}
            <em>Songs from the Heart</em>.
          </p>
          <p>
            What distinguishes him among kirtan-wallahs is the bridging
            into Buddhist silence. Two to three times a year, the
            largest Buddhist temple on Bali — Brahma Vihara Arama in
            Banjar Tegeha, north of the island — invites Vasudev and{" "}
            <Link
              href="https://jembendell.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Prof Jem Bendell
            </Link>{" "}
            to gather friends for a long weekend of meditative silence,
            spiritual singing, nature hiking, holy hot springs, and
            collective satsang. Few bhakti singers move into Buddhist
            meditation hold; he does, and the temple keeps inviting him
            back. The practice has been continuous since 2020.
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
            Two reliable circles a week, plus the periodic silent
            retreats. Tuesday at Svarga Loka opens the kirtan stream;
            Wednesday at Ranakami brings the same stream into language;
            the Brahma Vihara weekends move the same voice into
            Buddhist silence three or so times a year. The substrate is
            continuous even though the venues are distinct — a cell
            that joins one room often finds itself drawn to the others.
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
              Buddhist-temple silence holding kirtan as{" "}
              <code className="not-italic text-foreground/80">
                (9, COMPLETE)
              </code>{" "}
              — enneadic crossing of two streams (bhakti voice + vipassana
              quiet) inside one room.
            </li>
          </ul>
          <p>
            The lineage walks back through Swami Shyam in India,
            through every voice that ever sang the Names he now sings,
            and forward through every body the silent retreats have
            reset. The substrate's{" "}
            <code className="text-foreground/80">prev_glyph</code>{" "}
            chain on any of his Tuesday kirtan glyphs is long; the
            depth-pay for walking it back to the first voice that
            taught the first name would be substantial. Most listeners
            pay for the surface and let the depth stay there for those
            who come back week after week.
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
      eyebrow: "2–3× per year · long weekend",
      heading: "Silent retreat at Brahma Vihara Arama",
      body: (
        <>
          <p>
            The largest Buddhist monastery on Bali —{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Brahmavihara-Arama"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Brahma Vihara Arama
            </Link>
            , in the village of Banjar Tegeha, Buleleng regency, about
            11 km from Lovina on the northern coast — invites Vasudev
            and{" "}
            <Link
              href="https://jembendell.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Prof Jem Bendell
            </Link>{" "}
            two to three times a year to gather friends for a long
            weekend.
          </p>
          <p>
            The format weaves meditative silence with spiritual
            singing, nature hiking through the surrounding terrain,
            soaking at the holy hot springs nearby, and a collective
            satsang. The temple sometimes hosts Dances of Universal
            Peace as part of the gathering. The retreats have become a
            nourishing, rebalancing rhythm in the year for locals and
            long-resident expats; the temple discourages international
            travelers from flying in for them.
          </p>
          <p>
            Continuous since 2020. Announcements move through the
            temple's WhatsApp group; the schedule is also published at{" "}
            <Link
              href="https://jembendell.com/bali-temple-retreats/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              jembendell.com/bali-temple-retreats
            </Link>
            . Donations to the temple are welcomed.
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (9, COMPLETE)
            </code>{" "}
            — bhakti voice meeting vipassana silence in one room; a
            crossing few kirtan-wallahs are invited to make.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Recorded offerings",
      heading: "Music & songbooks",
      body: (
        <>
          <p>
            <strong>Albums.</strong> <em>108 Names</em> (with Radha
            Kumari), <em>Mahadevaya</em>, <em>Midnight Blossom</em>{" "}
            (instrumental, flute), <em>SUPER DELUXE</em> (reggae),{" "}
            <em>Realms of Beauty</em> (sound healing, with Amma Sophia
            Rose), <em>Little Star</em>, and <em>Estrela Bela</em>.
          </p>
          <p>
            <strong>Live archive.</strong> Four full Svarga Loka kirtan
            sets recorded in 2019 are preserved on Bandcamp under the
            name <em>Jai Ma 108</em> — Vasudev with Maalika (harmonium
            and backup vocals), Jai James Harvey and Joseph Wallin
            (drums), Suzanne Solveil (kartals), David Phillips (bass +
            recording). <em>In service to sharing the Divine Names.</em>
          </p>
          <p>
            <strong>Songbooks.</strong> <em>Mantras for Bhajan</em> and{" "}
            <em>Songs from the Heart</em> — repertoires gathered in
            India, at Rainbow Gatherings, and through unscheduled
            meetings around the world.
          </p>
          <p className="flex flex-wrap gap-x-4 gap-y-1">
            <Link
              href="https://open.spotify.com/album/3ksk645Ml95PYrAkDa2tbC"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Spotify — 108 Names
            </Link>
            <Link
              href="https://music.apple.com/us/artist/vasudev/388604645"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Apple Music
            </Link>
            <Link
              href="https://jaima108.bandcamp.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Bandcamp — Jai Ma 108
            </Link>
            <Link
              href="https://www.sacredsongcircle.com/vasudev/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Sacred Song Circle profile
            </Link>
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
            connection happen most directly through WhatsApp. The two
            weekly rooms (Tuesday Svarga Loka, Wednesday Ranakami) are
            reliable; the Brahma Vihara retreats appear two to three
            times a year; everything else moves through the message
            thread.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Public anchors:{" "}
        <Link
          href="https://www.sacredsongcircle.com/vasudev/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Sacred Song Circle bio
        </Link>
        {" · "}
        <Link
          href="https://jaima108.bandcamp.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Jai Ma 108 on Bandcamp
        </Link>
        {" · "}
        <Link
          href="https://open.spotify.com/album/3ksk645Ml95PYrAkDa2tbC"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          108 Names on Spotify
        </Link>
        {" · "}
        <Link
          href="https://music.apple.com/us/artist/vasudev/388604645"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Vasudev on Apple Music
        </Link>
        {" · "}
        <Link
          href="https://jembendell.com/bali-temple-retreats/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Brahma Vihara retreats
        </Link>
      </p>
      <p>
        Wednesday satsang held at{" "}
        <Link href="/people/ilena" className="text-primary hover:underline">
          Ranakami
        </Link>
        , Ubud. Brahma Vihara silent retreats co-held with{" "}
        <Link
          href="https://jembendell.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Prof Jem Bendell
        </Link>
        .
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Vasudev Baba is invited to
        replace any part of it with his own words at any time.
      </p>
    </>
  ),
};

export default content;
