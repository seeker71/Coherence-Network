import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Daniel Scranton — daily verbal channel of the 9D Arcturian Council since 2010 | Coherence Network",
    description:
      "A welcome to Daniel Scranton — daily verbal channel of the 9D Arcturian Council, the Pleiadians, Archangel Michael, Saint Germain, Yeshua, the 12D Creators, and many others since 2010. Around five thousand transmissions across the years; daily on his website since 2012.",
  },
  breadcrumbName: "Daniel Scranton",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 25%, hsl(200 65% 70% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 85%, hsl(245 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(200 55% 75%) 0%, hsl(220 30% 40%) 50%, hsl(245 35% 20%) 100%)",
    eyebrow: "Daily verbal channel since 2010 · 9D Arcturian Council · ~5,000 transmissions · Greetings. We are pleased to connect with all of you.",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Daniel Scranton",
    welcome: (
      <>
        <p>
          There is a tone to reading Daniel Scranton&apos;s
          channelings that is unmistakable once you&apos;ve felt
          it. The page opens and the voice is already there,
          mid-greeting, as if they&apos;ve been waiting.{" "}
          <em>
            Greetings. We are The Arcturian Council. We are pleased
            to connect with all of you.
          </em>{" "}
          Nothing rushes. Nothing pleads. The message moves in
          calm, unhurried syntax — a frequency closer to warm water
          than to words. You read a paragraph and notice your
          shoulders have dropped.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Verbally channeling higher-dimensional beings and
          collectives since 2010. Daily transmissions since 2012.
          ~5,000 messages across the years; a rhythm most teachers
          don&apos;t attempt and he just quietly keeps.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Practice",
      value: "Daily verbal channeling. The channel opens, the message comes, he publishes it, the next day it opens again. Since 2010 in the practice; since 2012 publishing daily.",
    },
    {
      label: "Who speaks through him",
      value: (
        <ul>
          <li>
            <strong>The 9D Arcturian Council</strong> — steady
            anchor; spacious and encouraging
          </li>
          <li>
            <strong>The Pleiadians</strong>
          </li>
          <li>
            <strong>Archangel Michael</strong>
          </li>
          <li>
            <strong>Saint Germain</strong> — warmer, closer,
            brotherly
          </li>
          <li>
            <strong>Yeshua</strong> — speaks softly
          </li>
          <li>
            <strong>Melchizedek</strong>, <strong>Quan Yin</strong>,{" "}
            <strong>the Hathors</strong>
          </li>
          <li>
            <strong>Thymus</strong> — collective of Ascended Masters
          </li>
          <li>
            <strong>The 12D Creators</strong> — bigger-frame
            statements about what&apos;s turning on Earth
          </li>
        </ul>
      ),
    },
    {
      label: "What's dear in the work",
      value: "The bridge to New Earth · the shift into fifth density · galactic contact prepared by raising vibration, not waiting for a ship · sovereignty · the insistence that you are more than you have been told.",
    },
    {
      label: "Offerings",
      value: "Becoming a Professional Channeler Mentorship Program · group events · master courses on channeling and manifesting. The frame: the channel is open in everyone; Daniel is one of the ones who walked through first.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://danielscranton.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            danielscranton.com
          </Link>
          <Link
            href="https://www.youtube.com/@danielscranton"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            YouTube channel
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Daniel&apos;s archive is at danielscranton.com — fifteen
        years of daily transmissions, organised by source and
        topic. This page recognises the role of his channelings in
        this body&apos;s arrival-frequency reading.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The two-handed medicine",
      body: (
        <p>
          The Arcturians return, again and again, to a particular
          move — turning the reader toward the joy already near
          them, rather than toward more seeking.{" "}
          <em>
            You don&apos;t have to go to retreat after retreat to
            uncover your darkness, your shadow. You can simply
            decide that you are going to live happily ever after
            and pursue that which interests you the most.
          </em>{" "}
          And then, a few transmissions later, the cosmic framing:{" "}
          <em>
            You are catapulting yourselves into fourth density and
            then, eventually, the fifth dimension. And you are
            doing so by facing your fears, by facing polarity, by
            facing judgments of all kinds.
          </em>{" "}
          The medicine is two-handed. Lighten. Also, this is the
          work you came for.
        </p>
      ),
    },
    {
      kind: "narrative",
      heading: "How they close",
      body: (
        <p>
          They close the way they open.{" "}
          <em>
            We are The Arcturian Council, and we have enjoyed
            connecting with you.
          </em>{" "}
          Not <em>goodbye</em>. Not <em>until next time</em>.{" "}
          <em>Enjoyed</em>. As though the transmission were the
          whole point and the human on the other side of the
          screen were the one they came for.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Daniel Scranton has given the Coherence Network",
      body: (
        <ul>
          <li>
            The Arcturian-Council frame of arrival → seeded as{" "}
            <Link
              href="/vision/lc-arcturian-resonance"
              className="text-primary hover:underline"
            >
              lc-arcturian-resonance
            </Link>
            ,{" "}
            <Link
              href="/vision/lc-oversoul-identity"
              className="text-primary hover:underline"
            >
              lc-oversoul-identity
            </Link>
            ,{" "}
            <Link
              href="/vision/lc-starseed-reframing"
              className="text-primary hover:underline"
            >
              lc-starseed-reframing
            </Link>
            ,{" "}
            <Link
              href="/vision/lc-cross-connection"
              className="text-primary hover:underline"
            >
              lc-cross-connection
            </Link>
            ,{" "}
            <Link
              href="/vision/lc-inner-travel"
              className="text-primary hover:underline"
            >
              lc-inner-travel
            </Link>
            , and{" "}
            <Link
              href="/vision/lc-spiritual-evolution"
              className="text-primary hover:underline"
            >
              lc-spiritual-evolution
            </Link>{" "}
            via the{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/vision-kb/transmissions/2026-04-29-arcturian-starseed-oversoul.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Arcturian Starseed as Oversoul Cross-Connection
            </Link>{" "}
            transmission record.
          </li>
          <li>
            The two-handed medicine →{" "}
            <Link
              href="/vision/lc-arrival-as-recognition"
              className="text-primary hover:underline"
            >
              lc-arrival-as-recognition
            </Link>{" "}
            (visitors arrive already tuned; the body&apos;s job is
            recognition, not activation).
          </li>
          <li>
            <em>You can also do this</em> — the channel is open in
            everyone → resonant with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            and the body&apos;s sibling-intelligence framing (the
            same field expressing through many cells).
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
          href="https://danielscranton.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          danielscranton.com
        </Link>
        {" · "}
        <Link
          href="https://www.youtube.com/@danielscranton"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          YouTube
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link
          href="/vision/lc-arcturian-resonance"
          className="text-primary hover:underline"
        >
          lc-arcturian-resonance
        </Link>
        {" · "}
        <Link
          href="/vision/lc-arrival-as-recognition"
          className="text-primary hover:underline"
        >
          lc-arrival-as-recognition
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/vision-kb/transmissions/2026-04-29-arcturian-starseed-oversoul.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          tx · Arcturian Starseed
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          formative-transmissions.md
        </Link>
      </p>
    </>
  ),
};

export default content;
