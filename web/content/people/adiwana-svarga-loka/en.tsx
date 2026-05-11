import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Adiwana Svarga Loka — Wantilan kirtan venue on the Campuhan riverbanks | Coherence Network",
    description:
      "A welcome to Adiwana Svarga Loka — wellness resort in Ubud on the Campuhan riverbanks whose open-air Wantilan room hosts Vasudev Baba's Tuesday-evening kirtan. The classical bhakti room in this body's Ubud lineage.",
  },
  breadcrumbName: "Adiwana Svarga Loka",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(165 55% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(225 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(170 45% 60%) 0%, hsl(200 30% 40%) 50%, hsl(225 35% 18%) 100%)",
    eyebrow: "Wellness resort · open-air Wantilan · Tuesday kirtan with Vasudev Baba · Campuhan riverbanks",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Adiwana Svarga Loka",
    welcome: (
      <>
        <p>
          A wellness resort in Ubud on the Campuhan riverbanks
          whose open-air <strong>Wantilan</strong> room — a
          traditional Balinese open-walled pavilion — hosts the
          Tuesday-evening kirtan held by{" "}
          <Link
            href="/people/vasudev-baba"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Vasudev Baba
          </Link>{" "}
          and friends. About five minutes&apos; walk from central
          Ubud through the rice fields. The classical bhakti room
          in this body&apos;s Ubud lineage.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          <em>Svarga Loka</em> in Sanskrit means <em>heavenly
          realm</em>. The resort is a hospitality container; the
          kirtan is a community offering held inside it.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: "Adiwana Svarga Loka Resort, Campuhan riverbanks, Ubud, Bali. ~5 minutes from central Ubud.",
    },
    {
      label: "The Wantilan",
      value: "Open-air traditional-Balinese pavilion. Polished wood floor, gamelan-style proportions, no walls — sound travels into the rice fields and back. The room is itself part of the kirtan instrument.",
    },
    {
      label: "Tuesday kirtan",
      value: (
        <>
          Weekly kirtan held by{" "}
          <Link
            href="/people/vasudev-baba"
            className="hover:text-primary transition-colors"
          >
            Vasudev Baba
          </Link>{" "}
          and friends. Harmonium, voices, the slow build into the
          names. Visitors and locals seated together on the
          floor. Hours shift gently with the seasons; the resort
          publishes current rhythm on its social channels.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Adiwana Svarga Loka (official)
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Adiwana Svarga Loka is a working wellness resort; this
        page recognises specifically the open-air Wantilan room
        and the Tuesday kirtan held inside it, and how both
        thread into this body&apos;s Ubud embodied lineage.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Why the room matters",
      body: (
        <p>
          Kirtan can happen in any room with bodies and voices,
          but a few rooms hold the practice especially well. The
          open-air Wantilan at Svarga Loka is one of those — its
          proportions, its acoustics, its place between the
          rice-field humidity and the river-canyon air all
          contribute to a specific resonance. The same names sung
          in this room sound different than they would sung
          anywhere else; the room is part of the instrument.
          Long-term participants speak of the Wantilan with the
          recognition of musicians speaking about a particular
          venue with great sound.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Adiwana Svarga Loka has given the Coherence Network",
      body: (
        <ul>
          <li>
            The Wantilan as venue holding Vasudev Baba&apos;s
            Tuesday kirtan — one of the two reliable weekly rooms
            anchoring his lineage in this body. See{" "}
            <Link
              href="/people/vasudev-baba"
              className="text-primary hover:underline"
            >
              his presence page
            </Link>{" "}
            for the broader frame.
          </li>
          <li>
            <em>The room is part of the instrument</em> →
            architectural recognition that{" "}
            <Link
              href="/vision/lc-attuned-spaces"
              className="text-primary hover:underline"
            >
              spaces have their own attunement
            </Link>
            ; the form of the room shapes the practice it can
            hold.
          </li>
          <li>
            On Tuesday April 28, 2026, this Tuesday-kirtan venue
            was one of the rooms named in{" "}
            <Link
              href="/people/ilena-young"
              className="text-primary hover:underline"
            >
              Ilena Young
            </Link>
            &apos;s invitation that opened the door this body
            walked through — see{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              the four-day meeting walk
            </Link>
            .
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
          href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Adiwana Svarga Loka (official)
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/vasudev-baba" className="text-primary hover:underline">
          Vasudev Baba
        </Link>
        {" · "}
        <Link href="/people/ilena-young" className="text-primary hover:underline">
          Ilena Young
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ubud-meeting-walk.md
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/ubud-embodied-lineage.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ubud-embodied-lineage.md
        </Link>
      </p>
    </>
  ),
};

export default content;
