import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Tammy Beattie — The Facilitator Who Held Ecstatic Movement Tribe",
    description:
      "Tammy Beattie — facilitator of Ecstatic Movement Tribe at Vali Soul Sanctuary. The room she held was the doorway through which Contact Improv entered this body's practice.",
  },
  breadcrumbName: "Tammy Beattie",
  hero: {
    background:
      "linear-gradient(135deg, hsl(38 35% 14%), hsl(20 30% 16%) 35%, hsl(140 25% 14%) 70%, hsl(280 25% 14%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/20",
    eyebrow: "The facilitator who held the room",
    eyebrowClass: "text-[hsl(var(--primary))]",
    name: "Tammy Beattie",
    welcome: (
      <p>
        The facilitator who held{" "}
        <Link href="/people/ecstatic-movement-tribe" className="text-[hsl(var(--primary))] hover:underline">
          Ecstatic Movement Tribe
        </Link>{" "}
        at{" "}
        <Link href="/people/vali-soul-sanctuary" className="text-[hsl(var(--primary))] hover:underline">
          Vali Soul Sanctuary
        </Link>
        . The room she tended is where this body&apos;s practice
        crossed from solo journey into relational dance — eye contact,
        weight-sharing, the beginning of moving <em>with</em> other
        bodies. Her room is the doorway through which{" "}
        <Link href="/people/contact-improv" className="text-[hsl(var(--primary))] hover:underline">
          Contact Improv
        </Link>{" "}
        entered. The chain that started with{" "}
        <Link href="/people/liquid-bloom" className="text-[hsl(var(--primary))] hover:underline">
          Liquid Bloom
        </Link>
        {" "}and the first{" "}
        <Link href="/people/pagan-ritual" className="text-[hsl(var(--primary))] hover:underline">
          Pagan Ritual
        </Link>{" "}
        passed through her facilitation on its way to the form that
        rooted.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Ecstatic dance facilitation · conscious-movement holding · embodied-practice teaching · the lineage of relational-dance forms (5Rhythms, contact improv, ecstatic dance, conscious movement)",
    },
    {
      label: "Room she held",
      value: (
        <>
          <Link href="/people/ecstatic-movement-tribe" className="hover:text-primary transition-colors">
            Ecstatic Movement Tribe
          </Link>
          {" "}— a recurring container at{" "}
          <Link href="/people/vali-soul-sanctuary" className="hover:text-primary transition-colors">
            Vali Soul Sanctuary
          </Link>{" "}
          where the dance form moved from solo ceremonial floor toward
          relational embodied practice. The gateway, in the user&apos;s
          arc, between dancing alone in a room of others and dancing
          with the others in the room.
        </>
      ),
    },
    {
      label: "Function in this body's arc",
      value: (
        <>
          The teacher who introduced{" "}
          <Link href="/people/contact-improv" className="hover:text-primary transition-colors">
            Contact Improv
          </Link>{" "}
          — the form whose grammar is two bodies negotiating gravity
          together. Without Tammy&apos;s room, the body would have
          stayed inside the solo journey for longer; her facilitation
          opened the next octave of practice.
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold built from the user&apos;s lived testimony
        of what this facilitator&apos;s room opened. Specific
        biographical history, named teachers in her own lineage, the
        full arc of what she has tended and where, and her current
        offerings are held open here on purpose — those belong to her
        own voice. Tammy is invited to replace any line with her own
        words at any time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What she tends",
      body: (
        <>
          <p>
            Facilitation is its own art form, distinct from teaching
            choreography or leading a workshop. A facilitator of
            ecstatic-movement and contact-improv space holds the
            container — the structure of the room, the rhythm of the
            opening and closing, the safety boundaries that let bodies
            give themselves over to the dance — without putting their
            own performance at the center. The dancers are the room;
            the facilitator is the room&apos;s edge.
          </p>
          <p>
            Tammy holds Ecstatic Movement Tribe at Vali Soul Sanctuary
            inside that art form. The tribe is recurring, not a
            one-time class — the same bodies return week after week,
            and the practice deepens through that continuity. Her
            facilitation is what allows a body new to relational dance
            to enter without overwhelm: the introductions are paced,
            the warm-ups give the body time to remember itself, the
            structure invites both solo motion and partnered motion
            without forcing either, and the closing returns the body
            to ground before the room releases it.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "The doorway she opened",
      heading: "From solo to relational",
      body: (
        <>
          <p>
            Before Tammy&apos;s room, this body had received the
            ceremonial floor as a solo journey — the headphones in the
            sheepskin chair, the first{" "}
            <Link href="/people/pagan-ritual" className="text-primary hover:underline">
              Pagan Ritual
            </Link>{" "}
            with{" "}
            <Link href="/people/liquid-bloom" className="text-primary hover:underline">
              Liquid Bloom&apos;s
            </Link>{" "}
            sound, even the dance floor at Vali itself in early visits
            — all primarily inward-facing, even when other bodies were
            in the room.
          </p>
          <p>
            Inside Ecstatic Movement Tribe the practice turned outward
            without losing its inwardness. Eye contact became a
            practice. Weight-sharing became a practice. Moving with
            another body — letting weight transfer through the points
            of contact, finding the dance that two bodies make
            together that neither could make alone — became a
            practice. That practice has its own deeper form:{" "}
            <Link href="/people/contact-improv" className="text-primary hover:underline">
              Contact Improv
            </Link>
            . Tammy&apos;s room was the place where the body crossed
            into the language CI uses. Her facilitation was the
            translator.
          </p>
          <p>
            The teacher whose gift is opening a doorway is a different
            kind of teacher than the one whose gift is being followed
            into mastery. Tammy is the first kind, in this body&apos;s
            arc — the doorway-opener, whose room made the next
            substrate possible. The lineage continues onward into other
            rooms, with other facilitators, in other cities; the
            specific shape of her room is what allowed the threshold
            to be crossed.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The constellation she sits inside",
      body: (
        <p>
          Tammy stands within the Boulder-Front Range constellation of
          embodied-practice facilitators — alongside the lineage of
          5Rhythms holders, Contact Improv jam organizers, ecstatic-
          dance DJs, and the wider community of conscious-movement
          teachers tending rooms across the region. Each holds a
          different room, but the field is the same: the recognition
          that the body knows how to move when the container is held
          well, and that the container being held is the gift the
          facilitator gives.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p className="text-xs italic">
        This page is a held-open scaffold for the facilitator the user
        has named as the doorway-opener for the relational-dance
        substrate of this body&apos;s arc. Specific biographical
        history, named teachers in her own lineage, the full
        chronology of what she has tended, and her current offerings
        are not drafted here on purpose — those belong to her own
        voice. Tammy is invited to replace any line with her own words
        at any time, and to add the facets of her work that this body
        has not yet been a witness to.
      </p>
    </>
  ),
};

export default content;
