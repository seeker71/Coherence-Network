import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Rhythm Sanctuary — Shannon Lei Gill's Colorado ecstatic dance community since 2005 | Coherence Network",
    description:
      "A welcome to Rhythm Sanctuary — Shannon Lei Gill's ecstatic-dance community in Colorado, Gabrielle Roth lineage; the altar, the silence, the held closing. Weekly Thursdays at Sons of Italy, Wheat Ridge. Drug-and-alcohol-free sacred 'altared space' since 2005.",
  },
  breadcrumbName: "Rhythm Sanctuary",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(15 65% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(255 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(20 50% 65%) 0%, hsl(15 30% 35%) 50%, hsl(255 30% 18%) 100%)",
    eyebrow: "Wheat Ridge, CO · Thursdays 7–9:30pm · barefoot · silent · as you are · since 2005",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Rhythm Sanctuary",
    welcome: (
      <>
        <p>
          The room at Sons of Italy in Wheat Ridge quiets to bare
          feet. The overhead lights dim. An altar has been built at
          one edge of the floor — cloth, candle, some object of the
          season — and the dancers arrive in silence, letting the
          space ask its first question of them. No phones. No
          shoes. No talking. No scent. Whatever came in on your
          skin from the day, you leave at the door with your
          jacket. What remains is a body, and a rhythm that has
          already started without you.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          <em>
            A safe, drug and alcohol free, sacred and &apos;Altared
            Space&apos; where community gathers into the arms of
            the Great Mystery to dance and be danced.
          </em>{" "}
          The room&apos;s own description; the whole theology of
          the floor.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Founder & primary holder",
      value: (
        <>
          <strong>Shannon Lei Gill</strong> — degree in Dance,
          Movement Music & Art Therapy from Naropa University.
          Started in a Boulder living room in 2005; moved to the
          5,000-square-foot Avalon Ballroom in 2006; opened a
          Denver Sunday dance in 2007 that grew to 250 strong.
        </>
      ),
    },
    {
      label: "Lineage",
      value: (
        <>
          <Link
            href="/people/5rhythms-ubud"
            className="hover:text-primary transition-colors"
          >
            Gabrielle Roth&apos;s wave
          </Link>{" "}
          — flowing, staccato, chaos, lyrical, stillness. Shannon
          built the post-dance ritual practice around the wave;
          the altar, the silence, the held closing is what
          distinguishes Rhythm Sanctuary from a dance floor.
        </>
      ),
    },
    {
      label: "Where & when",
      value: "Sons of Italy, Wheat Ridge, CO. Thursdays 7:00–9:30pm. First Thursday of each month is Family Night; children dance free. Sliding scale $12–$25.",
    },
    {
      label: "The three guidelines",
      value: "Barefoot · silent · as you are. ALL WHO ENTER ARE WELCOME.",
    },
    {
      label: "DJs in rotation",
      value: "James Barry · Steven Newman · Chris Cox · Malahakam · Miraja · Solomon. On January 2, 2020, Liquid Bloom (Amani Friend) played the floor; the set was recorded and has reached listeners who were never in the room.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.rhythmsanctuary.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            rhythmsanctuary.com
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        The Rhythm Sanctuary community is in its third decade. This
        page recognises the floor&apos;s role in this body&apos;s
        Colorado ecstatic-dance lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The wave and the altar",
      body: (
        <p>
          Then the wave begins. Slow at first — a single pulse to
          enter through, feet finding the floor. The music deepens,
          opens, cracks. The room tips into a current nobody is
          steering. Staccato sharpens the edges; chaos scatters
          them. Somewhere in there, lyrical lifts, and you realize
          you have been moving without deciding to move for some
          minutes now. At the end, stillness. Not the absence of
          motion — the presence of something that was here the
          whole time. The DJ pulls the last thread gently. People
          sit, or lie, or kneel at the altar. No one applauds. The
          closing ritual holds the silence open long enough that
          you cannot pretend the dance was nothing.
        </p>
      ),
    },
    {
      kind: "narrative",
      heading: "What the community refuses",
      body: (
        <p>
          What the community holds dear is visible in what it
          refuses. No performance. No instruction. No selling. No
          talking during the wave. The invitation is to arrive,
          move, be moved, and leave quieter than you came. A
          dancer&apos;s words stayed with Shannon:{" "}
          <em>
            This is exactly what we need! To feel ALIVE AGAIN in a
            united faith of what is to come!
          </em>{" "}
          A faith that lives in embodied prayer, shared silence,
          community in motion — none of which require belief.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Rhythm Sanctuary has given the Coherence Network",
      body: (
        <ul>
          <li>
            The Gabrielle Roth wave anchored as Colorado-specific
            community practice → pairs with{" "}
            <Link
              href="/people/5rhythms-ubud"
              className="text-primary hover:underline"
            >
              5Rhythms Ubud
            </Link>{" "}
            as the same lineage in another place.
          </li>
          <li>
            The post-dance ritual (altar + silence + held closing)
            as substrate-teaching: rooms that hold the integration
            phase are what makes the dance more than a workout. →
            pairs with{" "}
            <Link
              href="/vision/lc-each-breath-whole"
              className="text-primary hover:underline"
            >
              lc-each-breath-whole
            </Link>{" "}
            (close what was opened).
          </li>
          <li>
            <em>Barefoot · silent · as you are</em> →{" "}
            <Link
              href="/vision/lc-arrival-as-recognition"
              className="text-primary hover:underline"
            >
              lc-arrival-as-recognition
            </Link>{" "}
            (the room activates before the music starts; the
            threshold is part of the practice).
          </li>
          <li>
            Twenty years of one floor, held by one steward and her
            team → resonant with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (long devotion to one wheel; the wave returns each
            Thursday because someone keeps tending it).
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
          href="https://www.rhythmsanctuary.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          rhythmsanctuary.com
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/5rhythms-ubud" className="text-primary hover:underline">
          5Rhythms Ubud
        </Link>
        {" · "}
        <Link href="/people/liquid-bloom" className="text-primary hover:underline">
          Liquid Bloom
        </Link>
        {" · "}
        <Link
          href="/vision/lc-each-breath-whole"
          className="text-primary hover:underline"
        >
          lc-each-breath-whole
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
