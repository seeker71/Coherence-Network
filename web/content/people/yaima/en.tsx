import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "YAIMA — Masaru Higasa + Pepper Proud · ten-year elemental arc of albums | Coherence Network",
    description:
      "A welcome to YAIMA — the duo of Masaru Higasa and Pepper Proud, formed in Seattle 2014. Their music as a finely tuned container — handpan, vocals, flutes, world-percussion. The Pellucidity / OvO / Antidote / Earth Trilogy / CEREMONIA / Moongate arc.",
  },
  breadcrumbName: "YAIMA",
  hero: {
    background:
      "radial-gradient(ellipse at 65% 25%, hsl(180 55% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 85%, hsl(155 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(180 50% 70%) 0%, hsl(160 40% 45%) 50%, hsl(155 30% 20%) 100%)",
    eyebrow: "Seattle 2014 → · handpan, vocals, flutes, world-percussion · the elements as albums",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "YAIMA",
    welcome: (
      <>
        <p>
          There is a quality to YAIMA&apos;s music that arrives
          before you can name it — a feeling of walking into a
          room where the air is already holding something.
          Handpan bells thread through layered vocals. A low drum
          settles your spine. Flutes from somewhere you can&apos;t
          quite place enter and leave like breath. The duo
          describes what they make as a{" "}
          <strong>finely tuned container for their audience</strong>
          , and that is what it feels like: sound built as a
          vessel, not a performance.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          YAIMA emerges from two sources — one from the Mapudungun
          language meaning <em>that which water runs through</em>,
          and the other from the culturally preserved Yaeyama
          District of Okinawa, Japan. Two lineages naming water
          and place; two people making one sound.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Who",
      value: (
        <>
          <strong>Masaru Higasa</strong> — producer and
          multi-instrumentalist (guitar, flutes, handpan, bombo,
          didjeridoo); deep-listening sensibility.{" "}
          <strong>Pepper Proud</strong> — vocalist and lyricist,
          guitar in hand; writes words that reach for reverence
          without performing it. Formed in Seattle, 2014.
        </>
      ),
    },
    {
      label: "Discography",
      value: (
        <ul>
          <li>
            <em>Pellucidity</em> (2014) — given to <strong>water</strong>
          </li>
          <li>
            <em>OvO</em> (2016) — concept album for <strong>wind</strong>
          </li>
          <li>
            <em>Antidote</em> (2018) — given to <strong>fire</strong>
          </li>
          <li>
            <em>CEREMONIA</em> (2020) — fully acoustic, with bassist
            Jared May and percussionist John De Kadt; recorded at
            London Bridge Studios
          </li>
          <li>
            <em>Earth Trilogy</em> — <em>One</em> & <em>Two</em>{" "}
            (2021), <em>Three</em> (2022) — for{" "}
            <strong>earth</strong>
          </li>
          <li>
            <em>Moongate</em> (2024) — ten-year anniversary album;
            thirteen songs for the thirteen moons; fusion of the
            four elements
          </li>
        </ul>
      ),
    },
    {
      label: "Stated intention",
      value: (
        <>
          <em>
            To create a bridge between Nature and Humankind, an
            expansive experience that encourages growth and
            graceful passage for the hearts and minds of their
            listeners.
          </em>
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.yaimamusic.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            yaimamusic.com
          </Link>
          <Link
            href="https://yaima.bandcamp.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Bandcamp
          </Link>
          <Link
            href="https://open.spotify.com/artist/4tT8h7sUKmKcXgFnHnIxa3"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Spotify
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        YAIMA&apos;s archive is at yaimamusic.com, with the full
        discography on Bandcamp and Spotify. This page recognises
        their role in this body&apos;s conscious-music lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The elemental arc as practice",
      body: (
        <p>
          Their practice has moved through the elements like a
          long prayer spoken in parts. <em>Pellucidity</em> for
          water — created for <em>the peaceful being inside of us
          all</em>. <em>OvO</em> for wind — a concept album
          following a seed through the turning of a year.{" "}
          <em>Antidote</em> for fire — <em>the dance of passion
          and renewal, the deep inner work of intention and the
          cultivated patience of devotion</em>. The{" "}
          <em>Earth Trilogy</em> followed in three chapters —
          matter, human life finding collective purpose, and the
          Earth herself as one body. Woven between, <em>CEREMONIA</em>
          {" "}— their first fully acoustic offering, recorded at
          London Bridge Studios. In 2024 they released{" "}
          <em>Moongate</em>, the ten-year anniversary: thirteen
          songs for the thirteen moons of an Earth cycle, each
          one re-worked, re-recorded, re-mixed, re-mastered —{" "}
          <strong>re-visioned</strong>. A full turn of the wheel
          coming back around to itself.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What YAIMA has given the Coherence Network",
      body: (
        <ul>
          <li>
            Sustained, patient devotion to craft and earth as
            living practice → pairs with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (ten years of one project at one wheel).
          </li>
          <li>
            Sound built as a vessel, not a performance →{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
            </Link>{" "}
            (build at the actual tone; trust the routing).
          </li>
          <li>
            Two-lineage naming (Mapudungun + Yaeyama) → resonant
            with the body&apos;s practice of holding plural
            sources without flattening them. Pairs with{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>
            .
          </li>
          <li>
            Elemental arc as practice → resonant with{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (each album whole at its scale; the arc emerges from
            the sequence).
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
          href="https://www.yaimamusic.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          yaimamusic.com
        </Link>
        {" · "}
        <Link
          href="https://yaima.bandcamp.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Bandcamp
        </Link>
        {" · "}
        <Link
          href="https://open.spotify.com/artist/4tT8h7sUKmKcXgFnHnIxa3"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Spotify
        </Link>
      </p>
    </>
  ),
};

export default content;
