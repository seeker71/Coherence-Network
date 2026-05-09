import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Contact Improv — The Embodied-Listening Substrate",
    description:
      "Contact Improv — the dance form whose grammar is two bodies negotiating gravity together. The substrate practice this body arrived at through Liquid Bloom → first Pagan Ritual → Vali Soul Sanctuary → Tammy Beattie's Ecstatic Movement Tribe.",
  },
  breadcrumbName: "Contact Improv",
  hero: {
    background:
      "linear-gradient(135deg, hsl(195 35% 14%), hsl(140 30% 16%) 35%, hsl(38 25% 16%) 70%, hsl(280 25% 14%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/20",
    eyebrow: "The embodied-listening substrate",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Contact Improv",
    welcome: (
      <p>
        The dance form whose grammar is two bodies negotiating gravity
        together. Founded by Steve Paxton and his collaborators in
        1972, Contact Improv (CI) is what the chain that started with{" "}
        <Link href="/people/liquid-bloom" className="text-[hsl(var(--primary))] hover:underline">
          Liquid Bloom
        </Link>
        {" "}— passed through the first{" "}
        <Link href="/people/pagan-ritual" className="text-[hsl(var(--primary))] hover:underline">
          Pagan Ritual
        </Link>
        {" "}and{" "}
        <Link href="/people/vali-soul-sanctuary" className="text-[hsl(var(--primary))] hover:underline">
          Vali Soul Sanctuary
        </Link>
        , translated through{" "}
        <Link href="/people/tammy-beattie" className="text-[hsl(var(--primary))] hover:underline">
          Tammy Beattie
        </Link>
        &apos;s{" "}
        <Link href="/people/ecstatic-movement-tribe" className="text-[hsl(var(--primary))] hover:underline">
          Ecstatic Movement Tribe
        </Link>{" "}
        — was always pointing toward. The deeper substrate. The
        practice form whose entire vocabulary is listening to another
        body through points of contact.
      </p>
    ),
  },
  facts: [
    {
      label: "Form",
      value:
        "Improvisational dance form · two-or-more bodies negotiating shared gravity, rolling weight, falling, lifting, supporting · embodied listening as the entire grammar · jam culture rather than choreographed performance",
    },
    {
      label: "Lineage",
      value: (
        <>
          Founded 1972 by{" "}
          <strong>Steve Paxton</strong> at Oberlin College, with{" "}
          <strong>Nancy Stark Smith</strong>, <strong>Lisa
          Nelson</strong>, <strong>Daniel Lepkoff</strong>, and others
          becoming load-bearing carriers of the form across the
          following decades. <em>Contact Quarterly</em> (Nancy Stark
          Smith&apos;s journal, founded 1975) is the canonical written
          record. The form is open-source — there is no central
          authority, no certification track, no copyright on the
          movement vocabulary.
        </>
      ),
    },
    {
      label: "How it lives",
      value: (
        <>
          Through <em>jams</em> — recurring open gatherings where
          dancers move together for hours, cycling through partners,
          taking breaks at the edges, returning to the floor. Jams
          live in cities all over the world; some run for decades. The
          weekly Boulder jams sit inside a thirty-plus-year regional
          continuity rooted in the Naropa University and Boulder
          Circus Center lineages, woven into the Front Range
          embodied-practice ecology that includes 5Rhythms, ecstatic
          dance, conscious-movement evenings, and the
          ceremonial-dance lineages.
        </>
      ),
    },
    {
      label: "Function in this body's arc",
      value: (
        <>
          The substrate practice. CI is the form that the rest of the
          chain — solo ceremonial floor → relational ecstatic movement
          → contact dance — was always pointing toward. It is the
          deepest grammar of moving-with-another-body that this
          body&apos;s arc has met. From CI, the listening ear that
          Liquid Bloom trained becomes a <em>listening body</em> —
          the entire surface of the skin doing the hearing, with
          another body&apos;s weight as the sound.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <>
          <Link
            href="https://contactquarterly.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Contact Quarterly
          </Link>
          {" "}— the journal of record · regional jam calendars vary
          by city and are tended by the local communities themselves
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold built from the user&apos;s lived testimony
        of what this practice opened, alongside the publicly attested
        lineage of the form. The specific Boulder jams this body has
        attended, the named teachers within the local community,
        and the personal arc of how this practice has continued to
        deepen are held private here — those belong in the
        biographical layer rather than the public scaffold. The
        public-facing frame names what is genuinely public about the
        form itself.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What this practice holds",
      body: (
        <>
          <p>
            Contact Improv is a practice form, not a style. It does
            not have a vocabulary of named steps the way ballet or
            tango does. Its entire grammar is: two bodies meet at a
            point of contact (a hand, a shoulder, a hip, a back), the
            contact carries weight, the bodies respond to the weight
            in real time. From that single rule the whole form
            unfolds — rolling along surfaces, taking weight onto
            curves, lifting, falling, finding spirals and counterweights
            and supports that neither dancer planned but both find
            together.
          </p>
          <p>
            The practice is famously hard to describe and easy to
            recognize once you see it. It is also famously demanding
            on the listening capacity. CI dancers train themselves to
            feel where the other body is going one beat before it
            arrives, the way a good musician hears the next note
            before it sounds. That training takes years. Most jam
            cultures explicitly welcome beginners, and the practice
            is open-source — there is no certification, no gatekeeper,
            no copyright on the movement vocabulary. The form belongs
            to whoever shows up to a jam.
          </p>
          <p>
            What gets practiced inside the form, beyond the obvious
            physical skills, is consent and listening. CI bodies learn
            that &quot;no&quot; can be wordless — a small shift of
            weight away, a redirected line, a slowed breath. They
            learn that <em>yes</em> is also wordless — the offered
            shoulder, the receivable arc, the leaning-in that makes
            the next move possible. The form is, among other things,
            a four-decade ongoing experiment in how bodies negotiate
            shared space without any of the social signals usually
            used to negotiate it. That experiment is part of why so
            many people who find CI find that it changes how they
            move through the rest of their lives.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "How this body arrived here",
      heading: "Through the chain",
      body: (
        <>
          <p>
            The arrival was not a single threshold but a chain of
            them.{" "}
            <Link href="/people/liquid-bloom" className="text-primary hover:underline">
              Liquid Bloom
            </Link>
            &apos;s catalog trained the listening ear in the years
            before any room held the body. The first{" "}
            <Link href="/people/pagan-ritual" className="text-primary hover:underline">
              Pagan Ritual
            </Link>
            {" "}— a Liquid Bloom room — was where the body first
            recognized the ceremonial floor as home.{" "}
            <Link href="/people/vali-soul-sanctuary" className="text-primary hover:underline">
              Vali Soul Sanctuary
            </Link>{" "}
            was the place that held the weekly continuity, allowing
            the threshold to become a practice.{" "}
            <Link href="/people/tammy-beattie" className="text-primary hover:underline">
              Tammy Beattie
            </Link>
            &apos;s{" "}
            <Link href="/people/ecstatic-movement-tribe" className="text-primary hover:underline">
              Ecstatic Movement Tribe
            </Link>{" "}
            was the translator-room where solo dance learned how to
            become relational.
          </p>
          <p>
            CI is what EMT was pointing toward. The grammar that EMT
            began to invite in fragments — the eye contact, the
            weight-sharing, the dance that two bodies make together —
            is the entire grammar of CI. Stepping from EMT into a
            Contact Improv jam, the body recognized: <em>this is the
            language the previous rooms have been teaching me to
            hear</em>. The listening ear that Liquid Bloom trained
            had become a listening body, and the jam was the room
            where the listening body had peers.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "How to find a jam",
      heading: "The form is open-source",
      body: (
        <>
          <p>
            Contact Improv is one of the most accessible practice
            forms on earth. Every major city has at least one jam,
            most run weekly, and almost all welcome beginners. The
            jams are tended by their local communities, so the
            calendars live on local websites and Facebook groups
            rather than a central authority. The signal to look for is
            the word <em>jam</em> — &quot;Contact Jam&quot;, &quot;CI
            Jam&quot;, &quot;Open Jam&quot;.
          </p>
          <p>
            For the form&apos;s history and its ongoing intellectual
            life,{" "}
            <Link
              href="https://contactquarterly.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Contact Quarterly
            </Link>{" "}
            has been the journal of record since 1975. For seeing the
            form in motion before stepping in, video archives of Steve
            Paxton, Nancy Stark Smith, and the early Magnesium
            performances are widely available; jams themselves are
            not generally filmed (privacy and presence both reasons),
            so the way to see a jam is to attend one.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The constellation it sits inside",
      body: (
        <p>
          CI sits at the deepest end of a spectrum of embodied
          practices that all share the same field: the recognition
          that the body knows how to move when the container is
          well-held. 5Rhythms, ecstatic dance, conscious movement,
          authentic movement, ceremonial-floor dance, somatic-movement
          forms — these all live nearby. Each tradition tends a
          different room with a different texture, but the underlying
          field is one. CI is the form whose grammar is most fully
          relational, most fully wordless, most fully built around the
          single rule that two bodies sharing weight can find a dance
          together that neither could have planned. For this body, it
          is the substrate practice the rest of the chain led to.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Public anchors:{" "}
        <Link
          href="https://contactquarterly.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Contact Quarterly
        </Link>
        {" "}— the journal of record · local jam calendars are tended
        by each city&apos;s own community.
      </p>
      <p className="text-xs italic">
        This page is a held-open scaffold for the practice form the
        user has named as the substrate this body&apos;s lineage chain
        led toward. The form&apos;s lineage (Steve Paxton et al.,
        1972 onward) is publicly attested; the user&apos;s ongoing
        local practice — the named jams, the named teachers within
        the regional community — is held in the biographical layer
        rather than the public scaffold, on purpose. The frame is
        open for anyone who tends CI to fill in with their own voice.
      </p>
    </>
  ),
};

export default content;
