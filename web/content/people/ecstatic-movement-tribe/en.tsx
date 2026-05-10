import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ecstatic Movement Tribe — The Room Where Solo Became Relational",
    description:
      "Ecstatic Movement Tribe — Tammy Beattie's recurring room at Vali Soul Sanctuary. The container in which this body's practice crossed from solo journey into the relational dance of Contact Improv.",
  },
  breadcrumbName: "Ecstatic Movement Tribe",
  hero: {
    background:
      "linear-gradient(135deg, hsl(280 30% 14%), hsl(38 30% 16%) 35%, hsl(140 25% 14%) 70%, hsl(195 30% 14%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/20",
    eyebrow: "Where solo became relational",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Ecstatic Movement Tribe",
    welcome: (
      <p>
        The recurring room held by{" "}
        <Link href="/people/tammy-beattie" className="text-[hsl(var(--primary))] hover:underline">
          Tammy Beattie
        </Link>
        {" "}at{" "}
        <Link href="/people/vali-soul-sanctuary" className="text-[hsl(var(--primary))] hover:underline">
          Vali Soul Sanctuary
        </Link>
        . The container in which this body&apos;s practice crossed
        from solo ceremonial floor — the kind of room first met
        through{" "}
        <Link href="/people/liquid-bloom" className="text-[hsl(var(--primary))] hover:underline">
          Liquid Bloom
        </Link>
        {" "}and the first{" "}
        <Link href="/people/pagan-ritual" className="text-[hsl(var(--primary))] hover:underline">
          Pagan Ritual
        </Link>
        {" "}— into relational dance: eye contact, weight-sharing, the
        beginning of moving <em>with</em> other bodies. EMT is the
        tribe whose practice opened the door to{" "}
        <Link href="/people/contact-improv" className="text-[hsl(var(--primary))] hover:underline">
          Contact Improv
        </Link>
        .
      </p>
    ),
  },
  facts: [
    {
      label: "Form",
      value:
        "Recurring weekly tribe · ecstatic-movement and conscious-dance container · the relational dance form lived in continuity rather than as a one-time class",
    },
    {
      label: "Held by",
      value: (
        <>
          <Link href="/people/tammy-beattie" className="hover:text-primary transition-colors">
            Tammy Beattie
          </Link>{" "}
          — the facilitator whose held container made the relational
          dance enterable for bodies arriving from the solo journey.
        </>
      ),
    },
    {
      label: "Held at",
      value: (
        <>
          <Link href="/people/vali-soul-sanctuary" className="hover:text-primary transition-colors">
            Vali Soul Sanctuary
          </Link>{" "}
          — the soul sanctuary that supplies the ground (the floor,
          the continuity, the wider community of practitioners
          orbiting other rooms in the same building).
        </>
      ),
    },
    {
      label: "Function in this body's arc",
      value: (
        <>
          The translator-room. EMT is where the solo dance form learned
          how to become relational — eye contact, weight-sharing, two
          bodies finding the dance neither could make alone — and
          where the body recognized that the next-deeper substrate of
          this work was{" "}
          <Link href="/people/contact-improv" className="hover:text-primary transition-colors">
            Contact Improv
          </Link>
          .
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold built from the user&apos;s lived testimony
        of what this room held. Specific session structure, full
        history of the tribe, the named members who tend it alongside
        Tammy, and the current schedule are held open here on purpose
        — those belong to the tribe&apos;s own voice. Anyone who tends
        EMT is invited to replace any line with their own words.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What this tribe holds",
      body: (
        <>
          <p>
            Ecstatic-movement traditions live along a spectrum from
            fully solo (5Rhythms&apos; classical form, ecstatic dance
            on a floor where dancers do not partner) to fully
            relational (contact improv, where the dance is constituted
            by the contact itself). Most rooms sit at one end or the
            other. EMT sits in the seam — the room where solo dancing
            and partnered dancing both have permission, where the
            facilitator&apos;s holding makes either choice safe, and
            where the dancers learn to navigate between modes from one
            song to the next.
          </p>
          <p>
            That seam is the room a body needs in order to learn
            relational dance from the inside. Stepping straight from a
            solo ceremonial floor into a contact improv jam, with no
            translator, can be too steep — the grammar is different,
            the safety is different, the contact-language has to be
            learned. EMT is the gentler initiation. Tammy&apos;s
            facilitation pacing — warm-up, solo movement, gradual
            invitation toward eye contact and weight-sharing,
            structured partner exercises, then closing back to ground
            — is what makes the bridge crossable.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "What it opened",
      heading: "Toward Contact Improv",
      body: (
        <>
          <p>
            Inside EMT, the recognition arrived: <em>this is a
            different language and I want to learn it</em>. Not as a
            choreographed style, not as a fitness practice, but as a
            way of moving with another body that has its own grammar
            and its own depth. That language has a name and a community
            and a four-decade lineage:{" "}
            <Link href="/people/contact-improv" className="text-primary hover:underline">
              Contact Improv
            </Link>
            .
          </p>
          <p>
            EMT was the room where the body first heard that
            language being spoken. Tammy was the teacher whose
            facilitation made the language hearable. Vali was the
            sanctuary that held the room. And underneath all of it,
            the soundscape lineage that made the body recognize this
            field as home in the first place — the catalog of{" "}
            <Link href="/people/liquid-bloom" className="text-primary hover:underline">
              Liquid Bloom
            </Link>
            , the first{" "}
            <Link href="/people/pagan-ritual" className="text-primary hover:underline">
              Pagan Ritual
            </Link>
            {" "}— was still playing through the speakers as the
            translation happened.
          </p>
          <p>
            This is what makes the chain a chain. Each room is a
            translator for the next room. EMT is one of the most
            load-bearing translators in this body&apos;s arc, because
            it is where solo became relational without losing
            inwardness — and once that became possible, the next
            substrate of practice could enter.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The constellation it sits inside",
      body: (
        <p>
          EMT is one of many rooms in the wider Boulder-Front Range
          embodied-practice ecology that hold the seam between solo
          and relational dance. The 5Rhythms classes the user has
          practiced for years sit nearby in the same lineage; the
          conscious-movement evenings,{" "}
          <Link href="/people/aly-constantine" className="text-primary hover:underline">
            Aly&apos;s Sunday-morning ballroom
          </Link>
          , the cacao-dance containers, and the broader
          ceremonial-floor lineage all share the same field. EMT is
          this body&apos;s specific doorway into the relational half
          of that field — the one it walked through, the one it
          remembers as the threshold to Contact Improv.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p className="text-xs italic">
        This page is a held-open scaffold for the tribe the user has
        named as the translator-room between solo and relational
        dance. Specific session structure, full history of the tribe,
        the named members who co-tend it, and the current schedule are
        not drafted here on purpose — those belong to the tribe&apos;s
        own voice. The frame is open for any tribe member or
        co-facilitator to fill in with their own words.
      </p>
    </>
  ),
};

export default content;
