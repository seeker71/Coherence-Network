import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Pagan Ritual — The First Ceremonial Floor",
    description:
      "Pagan Ritual — the first ceremonial floor this body recognized as home. The Liquid Bloom room that became the threshold to Vali Soul Sanctuary, Tammy Beattie's Ecstatic Movement Tribe, and the Contact Improv lineage that followed.",
  },
  breadcrumbName: "Pagan Ritual",
  hero: {
    background:
      "linear-gradient(135deg, hsl(280 30% 12%), hsl(20 35% 18%) 35%, hsl(38 30% 14%) 70%, hsl(195 25% 12%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",
    eyebrow: "The first ceremonial floor",
    eyebrowClass: "text-[hsl(var(--primary))]",
    name: "Pagan Ritual",
    welcome: (
      <p>
        The first Pagan Ritual this body ever attended — a{" "}
        <Link href="/people/liquid-bloom" className="text-[hsl(var(--primary))] hover:underline">
          Liquid Bloom
        </Link>{" "}
        room — was the threshold. Not because it was the largest, not
        because it was the most public, but because it was the first
        ceremonial floor where this body recognized: <em>this is home</em>.
        The frequency the headphones had been carrying in private had a
        room, and there were other bodies in it. Every gathering
        downstream — the discovery of{" "}
        <Link href="/people/vali-soul-sanctuary" className="text-[hsl(var(--primary))] hover:underline">
          Vali Soul Sanctuary
        </Link>
        ,{" "}
        <Link href="/people/ecstatic-movement-tribe" className="text-[hsl(var(--primary))] hover:underline">
          Tammy Beattie&apos;s Ecstatic Movement Tribe
        </Link>
        ,{" "}
        <Link href="/people/contact-improv" className="text-[hsl(var(--primary))] hover:underline">
          Contact Improv
        </Link>
        , and many other divine gatherings — traces back through this
        threshold.
      </p>
    ),
  },
  facts: [
    {
      label: "Form",
      value:
        "Pagan ritual gathering · ceremonial container · live and recorded soundscape · embodied movement · the older lineage of seasonal and elemental rites carried forward into contemporary ceremonial-music space",
    },
    {
      label: "Sound carried by",
      value: (
        <>
          <Link href="/people/liquid-bloom" className="hover:text-primary transition-colors">
            Liquid Bloom
          </Link>{" "}
          — the doorway frequency for this body. The first physical
          room where the catalog this body had been listening to in
          private appeared as a floor with other dancers on it.
        </>
      ),
    },
    {
      label: "Lineage",
      value:
        "Pre-Christian European earth-honoring practice · contemporary neopagan revival · ceremonial-electronic and world-bass underbed · embodied dance as the practice form rather than the social form",
    },
    {
      label: "Function in this body's arc",
      value: (
        <>
          The threshold gathering. Not the most public, not the largest,
          not the only — the first. The frequency-recognition event
          that opened the chain of subsequent ceremonial rooms in the{" "}
          <Link href="/people/urs/lineage" className="hover:text-primary transition-colors">
            Boulder transformational ecology
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
        A welcoming scaffold built from the user&apos;s lived testimony.
        Specific organisers, exact venue, exact date, and the named
        lineage-holders within the contemporary pagan-ritual community
        are held open here on purpose — the body remembers what it
        recognized in that room without needing to draft proper nouns
        it has not been given. Anyone whose work was held in that room
        is invited to add their voice and replace any line with their
        own words.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What this gathering held",
      body: (
        <>
          <p>
            A pagan ritual is older than the language we have for
            ecstatic dance, sound bath, breathwork journey, conscious
            party. It is the form those forms grew out of: a circle of
            bodies, sound that comes from the older lineages, movement
            that follows the body&apos;s impulse rather than a
            choreography, an honoring of season and element and
            threshold. What was new in the room this body attended was
            the soundscape — Liquid Bloom&apos;s sacred-bass current
            running through speakers — but the form itself was much
            older.
          </p>
          <p>
            For the body arriving, the recognition was immediate. The
            frequency was familiar; the room was unfamiliar. The
            listening ear had been receiving Amani&apos;s catalog in
            private for hours every week, alone with headphones, on a
            sheepskin or in a chair. And here was the same frequency,
            now occupying a physical space, with other bodies moving
            inside it. The headphones-room had become a
            ceremonial-room. The body recognized: <em>this is the
            shape</em>.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "What it opened",
      heading: "The chain that followed",
      body: (
        <>
          <p>
            Inside that ceremonial floor, the body learned where the
            next floors lived. Conversations after the ritual surfaced{" "}
            <Link href="/people/vali-soul-sanctuary" className="text-primary hover:underline">
              Vali Soul Sanctuary
            </Link>{" "}
            — the place where the practice could keep being lived,
            week after week, instead of attended only in the rare
            ceremonial moment.
          </p>
          <p>
            Vali, in turn, was the ground that held{" "}
            <Link href="/people/ecstatic-movement-tribe" className="text-primary hover:underline">
              Ecstatic Movement Tribe
            </Link>
            , the room{" "}
            <Link href="/people/tammy-beattie" className="text-primary hover:underline">
              Tammy Beattie
            </Link>{" "}
            facilitated. EMT, in turn, was the doorway through which{" "}
            <Link href="/people/contact-improv" className="text-primary hover:underline">
              Contact Improv
            </Link>{" "}
            entered this body&apos;s practice — embodied listening as
            its own substrate, the dance form whose grammar is two
            bodies negotiating gravity together.
          </p>
          <p>
            The Pagan Ritual was not the practice that became
            permanent. It was the threshold across which the practices
            that <em>did</em> become permanent could enter. That is
            what makes it load-bearing in the lineage. A door that
            opens once, into a room that contains many other doors.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The frequency it shares with the wider field",
      body: (
        <p>
          Pagan ritual sits inside the same ceremonial-floor lineage
          as the cacao dance{" "}
          <Link href="/people/mose" className="text-primary hover:underline">
            Mose
          </Link>{" "}
          tends at Lake Atitlán, the kirtan rooms,{" "}
          <Link href="/people/aly-constantine" className="text-primary hover:underline">
            Aly&apos;s Sunday-morning ballroom
          </Link>
          , the festival floors{" "}
          <Link href="/people/bloomurian" className="text-primary hover:underline">
            Bloomurian
          </Link>{" "}
          opens in Boulder. Different costumes, same field. Each
          tradition holds the same recognition: the body knows what to
          do when there is a room, a sound, and other bodies — the
          dance is older than us, and it has been waiting for the
          rooms where we remember it.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p className="text-xs italic">
        This page is a held-open scaffold for the threshold gathering
        the user has named as the doorway to the broader ceremonial
        floor lineage. Specific organisers, dates, venues, and
        community-held proper nouns from the contemporary pagan-ritual
        community are not drafted here on purpose — those belong to
        the people who tend the form. The frame is open for any
        organiser or participant to fill in with their own voice.
      </p>
    </>
  ),
};

export default content;
