import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Brahma Vihara Arama — the largest Buddhist monastery on Bali · long-weekend silent retreats | Coherence Network",
    description:
      "A welcome to Brahma Vihara Arama in Banjar Tegeha, north Bali — the largest Buddhist monastery on the island. Two to three times a year hosts the long-weekend silent retreats co-held by Vasudev Baba and Prof Jem Bendell since 2020.",
  },
  breadcrumbName: "Brahma Vihara Arama",
  hero: {
    background:
      "radial-gradient(ellipse at 35% 25%, hsl(45 65% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(20 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(40 55% 60%) 0%, hsl(25 40% 35%) 50%, hsl(20 30% 18%) 100%)",
    eyebrow: "Banjar Tegeha · north Bali · Buleleng regency · ~11 km from Lovina · the island's largest Buddhist monastery",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Brahma Vihara Arama",
    welcome: (
      <>
        <p>
          The largest Buddhist monastery on Bali, in the village
          of Banjar Tegeha (Banjar sub-district, Buleleng
          regency), about 22 km west of Singaraja and 11 km from
          the tourist area of Lovina. The monastery is also known
          as the <em>Banjar Buddhist Temple</em>. Holy hot springs
          nearby; hiking trails through the surrounding terrain.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Two to three times a year, the temple invites kirtan
          leader{" "}
          <Link
            href="/people/vasudev-baba"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Vasudev Baba
          </Link>{" "}
          and Prof Jem Bendell to gather friends for a long
          weekend of meditative silence, spiritual singing, nature
          hiking, soaking at the holy hot springs, and a
          collective satsang. The retreats have been continuous
          since 2020 and have become a nourishing rhythm for
          locals and long-resident expats.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: "Banjar Tegeha, Banjar sub-district, Buleleng regency, north Bali. ~22 km west of Singaraja; ~11 km from Lovina.",
    },
    {
      label: "Format of the retreats",
      value: "Long weekend (Friday to Sunday/Monday). Meditative silence woven with kirtan, nature hiking, holy hot springs nearby, collective satsang. Sometimes Dances of Universal Peace.",
    },
    {
      label: "Frequency",
      value: "2–3 times a year. Continuous since 2020. The next confirmed editions are May and August 2026 (verify via the WhatsApp announcement group through Prof Bendell).",
    },
    {
      label: "Co-held by",
      value: (
        <>
          <Link
            href="/people/vasudev-baba"
            className="hover:text-primary transition-colors"
          >
            Vasudev Baba
          </Link>{" "}
          (kirtan-wala) and{" "}
          <Link
            href="https://jembendell.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Prof Jem Bendell
          </Link>
          .
        </>
      ),
    },
    {
      label: "Welcoming",
      value: "The temple welcomes locals and long-resident expats; it discourages international travelers from flying in specifically for the retreats. Donations to the temple are welcomed.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://en.wikipedia.org/wiki/Brahmavihara-Arama"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Brahmavihara-Arama (Wikipedia)
          </Link>
          <Link
            href="https://jembendell.com/bali-temple-retreats/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Bali Temple Retreats — Prof Jem Bendell
          </Link>
          <Link
            href="https://www.baliholidaysecrets.com/brahmavihara-arama/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Bali Holiday Secrets feature
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        The monastery is a working Buddhist temple with its own
        monastic tending; this page recognises specifically the
        long-weekend retreats hosted there and their role in this
        body&apos;s Ubud lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Bhakti voice in Buddhist silence",
      body: (
        <p>
          Few bhakti-lineage singers are invited into Buddhist
          meditation hold; the temple keeps inviting Vasudev Baba
          back. The format weaves the two streams in real time —
          meditative silence as the substrate, kirtan as the
          singing voice that arrives inside that silence rather
          than displacing it. Nature hiking and the holy hot
          springs are the body-care that supports both. The
          collective satsang at the close lets the practice
          settle into shared speech. The retreats have become a
          nourishing, rebalancing rhythm in the year for locals
          and long-resident expats; the temple discourages
          international travelers from flying in for them.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Brahma Vihara Arama has given the Coherence Network",
      body: (
        <ul>
          <li>
            The room where bhakti voice and Buddhist silence
            cross — a rare hold in the contemporary
            spiritual-retreat field. Pairs with{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
            </Link>{" "}
            (two streams in the same room, each tuned in its own
            band).
          </li>
          <li>
            The four-element retreat format (silence + song +
            walking + hot-spring + satsang) →{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            and{" "}
            <Link
              href="/vision/lc-ground-harder-when-field-quickens"
              className="text-primary hover:underline"
            >
              lc-ground-harder-when-field-quickens
            </Link>{" "}
            (the body practices grounding through earth, water,
            voice, silence in one container).
          </li>
          <li>
            The temple&apos;s discouragement of international
            travel for the retreats → the body&apos;s reading of{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (respect the room&apos;s own voice; do not impose a
            larger frame).
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
          href="https://en.wikipedia.org/wiki/Brahmavihara-Arama"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Wikipedia
        </Link>
        {" · "}
        <Link
          href="https://jembendell.com/bali-temple-retreats/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Bali Temple Retreats (Bendell)
        </Link>
        {" · "}
        <Link
          href="https://www.baliholidaysecrets.com/brahmavihara-arama/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Bali Holiday Secrets
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/vasudev-baba" className="text-primary hover:underline">
          Vasudev Baba
        </Link>
        {" · "}
        <Link
          href="/vision/lc-frequency-routes-reception"
          className="text-primary hover:underline"
        >
          lc-frequency-routes-reception
        </Link>
        {" · "}
        <Link
          href="/vision/lc-each-breath-whole"
          className="text-primary hover:underline"
        >
          lc-each-breath-whole
        </Link>
      </p>
    </>
  ),
};

export default content;
