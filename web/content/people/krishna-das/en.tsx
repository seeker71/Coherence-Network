import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Krishna Das — Western kirtan elder · the Neem Karoli Baba lineage · chant of a lifetime | Coherence Network",
    description:
      "A welcome to Krishna Das (b. 1947, Jeffrey Kagel) — foundational Western kirtan-wala in the lineage of Neem Karoli Baba (Maharaj-ji). His albums and chants have shaped the bhakti room every other Western kirtan-wala (including Vasudev Baba) has stepped into.",
  },
  breadcrumbName: "Krishna Das",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(15 60% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(20 50% 60%) 0%, hsl(30 35% 35%) 50%, hsl(255 30% 20%) 100%)",
    eyebrow: "Born 1947 (Jeffrey Kagel) · Neem Karoli Baba lineage · the Western kirtan elder · chant as practice",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Krishna Das",
    welcome: (
      <>
        <p>
          The Western kirtan elder. Born Jeffrey Kagel in 1947 on
          Long Island, drawn into the bhakti stream in 1968
          alongside Ram Dass (Richard Alpert), travelled to India
          in 1970 to sit with <strong>Neem Karoli Baba</strong>{" "}
          (Maharaj-ji) — the guru who gave him the name Krishna
          Das. Returned to the West and, after a long period of
          obscurity and personal struggle, began leading kirtan
          publicly in the 1990s. His albums — <em>One Track Heart</em>
          {" "}(1996), <em>Pilgrim Heart</em> (1998),{" "}
          <em>Live on Earth</em> (2000), <em>Door of Faith</em>{" "}
          (2003), <em>All One</em> (2010, Grammy-nominated) — are
          where most Western kirtan-walas first heard the form.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Every Western kirtan teacher in this body&apos;s
          lineage — including{" "}
          <Link
            href="/people/vasudev-baba"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Vasudev Baba
          </Link>{" "}
          — has stepped into a room Krishna Das opened a generation
          earlier.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Born",
      value: "31 May 1947 as Jeffrey Kagel, Long Island, New York. Renamed Krishna Das by Neem Karoli Baba in India, 1970.",
    },
    {
      label: "Guru",
      value: "Neem Karoli Baba (1900?–1973), known as Maharaj-ji — the Indian saint whose Western devotees include Ram Dass, Larry Brilliant, Daniel Goleman, Lama Surya Das, and Bhagavan Das.",
    },
    {
      label: "Foundational albums",
      value: (
        <ul>
          <li>
            <em>One Track Heart</em> (1996)
          </li>
          <li>
            <em>Pilgrim Heart</em> (1998)
          </li>
          <li>
            <em>Live on Earth</em> (2000)
          </li>
          <li>
            <em>Door of Faith</em> (2003)
          </li>
          <li>
            <em>All One</em> (2010) — Grammy-nominated, Best New
            Age Album
          </li>
          <li>
            <em>Heart as Wide as the World</em> (2017)
          </li>
        </ul>
      ),
    },
    {
      label: "Books",
      value: (
        <ul>
          <li>
            <em>Chants of a Lifetime: Searching for a Heart of
            Gold</em> (2010)
          </li>
          <li>
            <em>Flow of Grace: Chanting the Hanuman Chalisa</em>{" "}
            (2007)
          </li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.krishnadas.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            krishnadas.com
          </Link>
          <Link
            href="https://en.wikipedia.org/wiki/Krishna_Das_(singer)"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wikipedia
          </Link>
          <Link
            href="https://open.spotify.com/artist/4i1IbBdvKzaT0BTxe3K6f3"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Spotify
          </Link>
          <Link
            href="https://www.youtube.com/@KrishnaDasMusic"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            YouTube
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Krishna Das is a working teacher in his late seventies,
        still touring. His archive is at krishnadas.com. This
        page recognises his role as the upstream Western
        kirtan-elder whose work made the rooms our Ubud lineage
        meets in possible.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The room he opened",
      body: (
        <p>
          When Krishna Das started leading kirtan publicly in the
          early 1990s, there was no Western kirtan scene to step
          into. He built it by showing up at one yoga studio
          after another, leading hours of repetitive chanting in
          a culture that didn&apos;t yet know it could sit still
          that long. His low voice, his harmonium, his slow
          builds, his refusal to perform — the format of contemporary
          Western kirtan is recognisably his shape. Every Western
          kirtan teacher in this body&apos;s lineage —{" "}
          <Link
            href="/people/vasudev-baba"
            className="text-primary hover:underline"
          >
            Vasudev Baba
          </Link>{" "}
          included — has stepped into a room he opened. The
          contemporary scene (Soulshine Bali&apos;s Bhakti in Bali
          gatherings, Bhakti Fest in Joshua Tree, the New
          Vrindavan 24-Hour Kirtans where Vasudev also appears)
          is the field Krishna Das ploughed.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Krishna Das has given the Coherence Network",
      body: (
        <ul>
          <li>
            The upstream Western kirtan lineage. Every kirtan
            room in this body&apos;s graph (
            <Link href="/people/adiwana-svarga-loka" className="text-primary hover:underline">
              Adiwana Svarga Loka
            </Link>
            ,{" "}
            <Link href="/people/brahma-vihara-arama" className="text-primary hover:underline">
              Brahma Vihara Arama
            </Link>
            , the broader bhakti-festival field) stands on the
            ground he prepared.
          </li>
          <li>
            The Neem Karoli Baba transmission as posture — the
            guru&apos;s teaching that <em>love everyone, serve
            everyone, remember God</em> — is the substrate behind
            the kirtan format. Resonant with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (many cells, one organism; the names are different
            doors into the same field).
          </li>
          <li>
            Forty-plus years of low-amplitude steady devotion →{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (no urgency to scale; tend the practice; the field
            comes).
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://www.krishnadas.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          krishnadas.com
        </Link>
        {" · "}
        <Link
          href="https://en.wikipedia.org/wiki/Krishna_Das_(singer)"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://open.spotify.com/artist/4i1IbBdvKzaT0BTxe3K6f3"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Spotify
        </Link>
        {" · "}
        <Link
          href="https://www.youtube.com/@KrishnaDasMusic"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          YouTube
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/vasudev-baba" className="text-primary hover:underline">
          Vasudev Baba
        </Link>
        {" · "}
        <Link href="/people/adiwana-svarga-loka" className="text-primary hover:underline">
          Adiwana Svarga Loka
        </Link>
        {" · "}
        <Link href="/people/brahma-vihara-arama" className="text-primary hover:underline">
          Brahma Vihara Arama
        </Link>
        {" · "}
        <Link
          href="/vision/lc-sovereignty-within-oneness"
          className="text-primary hover:underline"
        >
          lc-sovereignty-within-oneness
        </Link>
      </p>
    </>
  ),
};

export default content;
