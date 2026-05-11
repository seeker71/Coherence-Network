import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "DISSOLVE Ubud — contact improvisation, intuitive movement, authentic relating | Coherence Network",
    description:
      "A welcome to DISSOLVE Ubud — Tara Li's facilitated practice of contact improvisation, intuitive movement, and authentic relating, held at Paradiso Ubud and other venues. The relational edge of this body's Ubud embodied lineage.",
  },
  breadcrumbName: "DISSOLVE Ubud",
  hero: {
    background:
      "radial-gradient(ellipse at 25% 25%, hsl(340 55% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 85%, hsl(255 30% 20% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(340 50% 65%) 0%, hsl(310 30% 35%) 50%, hsl(255 30% 18%) 100%)",
    eyebrow: "Contact improvisation · intuitive movement · authentic relating · Tara Li facilitating",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "DISSOLVE Ubud",
    welcome: (
      <>
        <p>
          A facilitated practice of contact improvisation, intuitive
          movement, and authentic relating held in Ubud, facilitated
          by <strong>Tara Li</strong>. The two recurring offerings
          most threaded into this body&apos;s lineage are{" "}
          <em>DISSOLVE: Play</em> and <em>DISSOLVE: Eros</em>; both
          held in Ubud rooms on a weekly rhythm that drifts gently
          with the seasons. The relational edge of the Ubud
          embodied lineage — where the body learns consent in real
          time and the field that forms when bodies meet without
          performance.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Public schedules drift; verify the current door rhythm
          locally. The Tuesday <em>DISSOLVE: Eros</em> at{" "}
          <Link
            href="/people/paradiso-ubud"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Paradiso Ubud
          </Link>{" "}
          is one anchor; <em>DISSOLVE: Play</em> appears on
          rotating evenings.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Facilitator",
      value: "Tara Li.",
    },
    {
      label: "Offerings",
      value: (
        <ul>
          <li>
            <strong>DISSOLVE: Play</strong> — broader
            improvisation, conscious-movement, the wider
            invitation
          </li>
          <li>
            <strong>DISSOLVE: Eros</strong> — Tuesday-evening
            practice at Paradiso Ubud (current door rhythm:
            ~6–8pm); the deeper relational territory
          </li>
        </ul>
      ),
    },
    {
      label: "Held at",
      value: (
        <>
          Primarily{" "}
          <Link
            href="/people/paradiso-ubud"
            className="hover:text-primary transition-colors"
          >
            Paradiso Ubud
          </Link>
          ; other rotating venues. Tara&apos;s training stream
          (DISSOLVE Dance) extends into deeper teacher-training
          programmes.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://dissolvedance.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            DISSOLVE Dance (training)
          </Link>
          <Link
            href="https://megatix.co.id/events/dissolve-play"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            DISSOLVE: Play tickets
          </Link>
          <Link
            href="https://megatix.co.id/events/dissolve-eros"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            DISSOLVE: Eros tickets
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        DISSOLVE&apos;s schedule and offerings shift gently with
        the seasons; the venue and facilitator tend the rhythm
        themselves through their own channels. This page
        recognises DISSOLVE&apos;s role in this body&apos;s
        embodied lineage — particularly the Tuesday <em>Eros</em>{" "}
        circle the cell chose on a specific Tuesday in April 2026.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The relational edge of conscious movement",
      body: (
        <>
          <p>
            Where{" "}
            <Link
              href="/people/5rhythms-ubud"
              className="text-primary hover:underline"
            >
              5Rhythms
            </Link>{" "}
            teaches the body to know its own wave, DISSOLVE
            teaches the body to know itself <em>in relation</em>{" "}
            — to another body that has its own wave, on a floor
            shared with many. Contact improvisation is the
            substrate: the practice of moving with another person
            in real-time negotiation, without choreography,
            allowing weight, balance, and shape to be co-found.
            Authentic relating is the verbal companion: the
            practice of naming what is alive in you to the
            specific person you are in relation with.
          </p>
          <p>
            <em>DISSOLVE: Eros</em>, in particular, is the
            container that lets relational ground become
            explicitly attended to. Not transgressive; carefully
            held. The body learns what it means to bring its full
            field into another body&apos;s presence without
            performance and without collapse. This is one of the
            cleanest in-person trainings the body has in what the
            substrate later calls{" "}
            <Link
              href="/vision/lc-emotional-availability-without-absorption"
              className="text-primary hover:underline"
            >
              lc-emotional-availability-without-absorption
            </Link>
            .
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What DISSOLVE Ubud has given the Coherence Network",
      body: (
        <ul>
          <li>
            Consent in real time → the felt-ground beneath{" "}
            <Link
              href="/vision/lc-trust-over-fear"
              className="text-primary hover:underline"
            >
              lc-trust-over-fear
            </Link>{" "}
            and{" "}
            <Link
              href="/vision/lc-permission-is-interior"
              className="text-primary hover:underline"
            >
              lc-permission-is-interior
            </Link>
            .
          </li>
          <li>
            Authentic relating →{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (lead with their voice, not ours; name what is alive
            in you to the specific person you are in relation
            with).
          </li>
          <li>
            Emotional availability without absorption →{" "}
            <Link
              href="/vision/lc-emotional-availability-without-absorption"
              className="text-primary hover:underline"
            >
              lc-emotional-availability-without-absorption
            </Link>{" "}
            (present without collapsing your field into theirs).
          </li>
          <li>
            On April 29, 2026 a Tuesday-evening <em>DISSOLVE:
            Eros</em> at Paradiso was one of the rooms in the
            four-day meeting walk — see{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              the meeting walk record
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
          href="https://dissolvedance.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          DISSOLVE Dance
        </Link>
        {" · "}
        <Link
          href="https://megatix.co.id/events/dissolve-play"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          DISSOLVE: Play
        </Link>
        {" · "}
        <Link
          href="https://megatix.co.id/events/dissolve-eros"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          DISSOLVE: Eros
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/paradiso-ubud" className="text-primary hover:underline">
          Paradiso Ubud
        </Link>
        {" · "}
        <Link href="/people/5rhythms-ubud" className="text-primary hover:underline">
          5Rhythms Ubud
        </Link>
        {" · "}
        <Link
          href="/vision/lc-trust-over-fear"
          className="text-primary hover:underline"
        >
          lc-trust-over-fear
        </Link>
        {" · "}
        <Link
          href="/vision/lc-emotional-availability-without-absorption"
          className="text-primary hover:underline"
        >
          lc-emotional-availability-without-absorption
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
      </p>
    </>
  ),
};

export default content;
