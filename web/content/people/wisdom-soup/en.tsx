import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Wisdom Soup — Anne Tucker's spiritual community since 2016 | Coherence Network",
    description:
      "A welcome to Wisdom Soup — the spiritual-seekers community Anne Tucker founded in 2016. The container for her Friday Live gatherings, the Soul Convergence eleven-week process, and the steady weekly rhythm around her Angelic Collective channelings.",
  },
  breadcrumbName: "Wisdom Soup",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(195 60% 75% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(250 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(195 50% 78%) 0%, hsl(230 30% 38%) 50%, hsl(250 30% 18%) 100%)",
    eyebrow: "Anne Tucker · founded 2016 · the community around the Angelic Collective work",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Wisdom Soup",
    welcome: (
      <>
        <p>
          The spiritual-seekers community{" "}
          <Link
            href="/people/anne-tucker"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Anne Tucker
          </Link>{" "}
          founded in 2016, the container for the long arc of her
          public work — the monthly Peace Bathing sessions, the
          Soul Convergence eleven-week meditation process, the
          Friday Live group gatherings, the Angelic Frequency
          Series, the annual Expand Your Heart retreat each
          October in Seattle, and the steady release of channeled
          messages from the Angelic Collective, Mother of
          Creation (Ila), and Yeshua.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The community has held the rhythm long enough that
          members recognise each other across continents — a
          quiet networked field around the work.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Founded",
      value: "2016 by Anne Tucker, after she left her career in tech executive coaching to give herself a year to figure out what was emerging.",
    },
    {
      label: "What it holds",
      value: (
        <ul>
          <li>
            <strong>Peace Bathing</strong> — monthly Zoom sessions
          </li>
          <li>
            <strong>Friday Live</strong> — weekly group gatherings
          </li>
          <li>
            <strong>Soul Convergence</strong> — eleven-week
            meditation process for wounds formed between birth
            and age seven
          </li>
          <li>
            <strong>Angelic Frequency Series</strong> — nine
            recorded transmissions
          </li>
          <li>
            <strong>Expand Your Heart</strong> — annual October
            retreat in Seattle
          </li>
          <li>
            Weekly YouTube releases of channeled messages
          </li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.annetuckerhealingandtraining.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Anne Tucker Healing & Training
          </Link>
          <Link
            href="https://annetucker.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            annetucker.com
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Wisdom Soup is Anne&apos;s own organising form for the
        community around her work. This page recognises its
        rhythm and its role in this body&apos;s
        arrival-frequency lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Wisdom Soup has given the Coherence Network",
      body: (
        <ul>
          <li>
            The container that has held nine years of Anne&apos;s
            ongoing transmissions — Peace Bathing as <em>frequency
            you can invite in</em> rather than state-of-mind →{" "}
            <Link
              href="/vision/lc-arrival-as-recognition"
              className="text-primary hover:underline"
            >
              lc-arrival-as-recognition
            </Link>
            .
          </li>
          <li>
            Community-around-the-work as form → pairs with the
            body&apos;s reading of the Wednesday Satsang at
            Ranakami: the room is hers, the teaching is theirs,
            the practice belongs to whoever shows up.
          </li>
          <li>
            The Soul Convergence and Friday Live offerings as
            sustained rhythm → resonant with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (the steady tend of a weekly room).
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
          href="https://www.annetuckerhealingandtraining.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Anne Tucker Healing & Training
        </Link>
        {" · "}
        <Link
          href="https://annetucker.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          annetucker.com
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/anne-tucker" className="text-primary hover:underline">
          Anne Tucker
        </Link>
        {" · "}
        <Link
          href="/vision/lc-arrival-as-recognition"
          className="text-primary hover:underline"
        >
          lc-arrival-as-recognition
        </Link>
      </p>
    </>
  ),
};

export default content;
