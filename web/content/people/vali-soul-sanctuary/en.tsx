import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Vali Soul Sanctuary — The Place That Held the Practice",
    description:
      "Vali Soul Sanctuary — the sanctuary that turned a once-attended ceremonial floor into a regular practice. The place that held Tammy Beattie's Ecstatic Movement Tribe and the Contact Improv lineage that arrived through it.",
  },
  breadcrumbName: "Vali Soul Sanctuary",
  hero: {
    background:
      "linear-gradient(135deg, hsl(195 35% 12%), hsl(140 30% 16%) 35%, hsl(38 25% 18%) 70%, hsl(280 30% 14%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/80 to-background/20",
    eyebrow: "The place that held the practice",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Vali Soul Sanctuary",
    welcome: (
      <p>
        The sanctuary that turned a once-attended ceremonial floor
        into a regular practice. After the first{" "}
        <Link href="/people/pagan-ritual" className="text-[hsl(var(--primary))] hover:underline">
          Pagan Ritual
        </Link>
        {" "}— the{" "}
        <Link href="/people/liquid-bloom" className="text-[hsl(var(--primary))] hover:underline">
          Liquid Bloom
        </Link>{" "}
        room that became the threshold — Vali was the place where the
        body could keep coming back. Where ceremony stopped being a
        rare event and became <em>weekly ground</em>. Where{" "}
        <Link href="/people/tammy-beattie" className="text-[hsl(var(--primary))] hover:underline">
          Tammy Beattie
        </Link>
        {" "}held{" "}
        <Link href="/people/ecstatic-movement-tribe" className="text-[hsl(var(--primary))] hover:underline">
          Ecstatic Movement Tribe
        </Link>
        , the room through which{" "}
        <Link href="/people/contact-improv" className="text-[hsl(var(--primary))] hover:underline">
          Contact Improv
        </Link>{" "}
        entered. And alongside, many other divine gatherings that
        shaped this body.
      </p>
    ),
  },
  facts: [
    {
      label: "Form",
      value:
        "Soul sanctuary · weekly ceremonial container · ecstatic-dance and conscious-movement venue · sacred space for embodied practice and community gathering",
    },
    {
      label: "What it tends",
      value: (
        <>
          A continuous calendar of embodied-practice rooms — ecstatic
          dance, conscious movement, contact improv jams, sound
          journeys, breathwork, ceremony — held by a constellation of
          facilitators who tend their own practices inside the same
          ground. The sanctuary is the soil; the practices are the
          plants.
        </>
      ),
    },
    {
      label: "Function in this body's arc",
      value: (
        <>
          The continuity holder. After the threshold of the first{" "}
          <Link href="/people/pagan-ritual" className="hover:text-primary transition-colors">
            Pagan Ritual
          </Link>
          , Vali was where the practice could keep being lived rather
          than only attended once. Without the sanctuary, the threshold
          would have been a singular memory; with it, the threshold
          became a doorway into a continuous body of weekly practice.
        </>
      ),
    },
    {
      label: "Lineage carried",
      value: (
        <>
          The Boulder transformational ecology — twenty-plus years
          deep — runs through Vali as one of its tendings. The same
          lineage that surfaces in the{" "}
          <Link href="/people/aly-constantine" className="hover:text-primary transition-colors">
            Sunday-morning ballroom
          </Link>
          , in the floors that Shannon Lei Gill held in 2006 as Rhythm
          Sanctuary, in the festival rooms{" "}
          <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
            Bloomurian
          </Link>{" "}
          opens, and in the cacao container{" "}
          <Link href="/people/mose" className="hover:text-primary transition-colors">
            Mose
          </Link>{" "}
          tends at Lake Atitlán. One field, many sanctuaries.
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold built from the user&apos;s lived testimony.
        Specific address, exact founding history, the named stewards
        who tend the sanctuary day to day, and the full calendar of
        offerings are held open here on purpose — those belong to the
        people who carry the place. The frame is open for anyone who
        tends Vali to fill in with their own voice.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What this place holds",
      body: (
        <>
          <p>
            A soul sanctuary is a different shape from a yoga studio,
            a dance club, a workshop space, a community center. It
            contains elements of all of those, but the organizing
            principle is different: the room is held as ceremonial
            ground first, and the offerings inside it are tended as
            practices rather than classes. People do not attend Vali
            the way they attend a fitness class. They <em>arrive</em>{" "}
            at it the way one arrives at a temple — to enter a
            container that has been prepared for the body to remember
            something.
          </p>
          <p>
            What makes the form work is continuity. A single ceremony
            can be powerful but is hard to integrate alone. A weekly
            sanctuary, where the same bodies move with each other on
            the same floor again and again, is what allows the
            practice to become embodied. The recognition that arrived
            in the threshold — <em>this is home</em> — gets to be lived
            forward, week after week, until it stops being a
            recognition and starts being a way of moving.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "The rooms inside the sanctuary",
      heading: "Where the practice deepened",
      body: (
        <>
          <p>
            Inside Vali, the room that opened next was{" "}
            <Link href="/people/ecstatic-movement-tribe" className="text-primary hover:underline">
              Ecstatic Movement Tribe
            </Link>
            {" "}— the offering held by{" "}
            <Link href="/people/tammy-beattie" className="text-primary hover:underline">
              Tammy Beattie
            </Link>
            . EMT was where a different grammar of moving entered: not
            only the solo journey on a ceremonial floor, but the
            beginning of moving <em>with</em> other bodies — eye
            contact, weight-sharing, the dance becoming relational
            rather than only inward.
          </p>
          <p>
            From within EMT, the body found its way to{" "}
            <Link href="/people/contact-improv" className="text-primary hover:underline">
              Contact Improv
            </Link>
            {" "}— the form whose entire grammar is two bodies
            negotiating gravity together. CI is what EMT was pointing
            toward. Vali was the soil that let the pointing happen, by
            holding the rooms long enough for one practice to introduce
            the body to the next.
          </p>
          <p>
            And alongside these named threads, many other rooms — the
            user has named &quot;many other divine gatherings&quot; as
            a category. Each of those is a node in the same field, and
            each is welcome on its own page when its time comes to be
            named.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The constellation it sits inside",
      body: (
        <p>
          Vali is one of several sanctuaries holding the
          embodied-practice lineage in the wider Boulder-Front Range
          ecology. The form has roots that reach back through Gabrielle
          Roth&apos;s 5Rhythms (which the user has practiced for years
          across the Boulder ecology), through 1980s contact improv at
          Naropa and the Boulder Circus Center, through earlier
          ceremonial-dance lineages that came to Colorado with the
          Eastern-spiritual and human-potential currents of the 1970s
          and 1980s. Each sanctuary tends its own corner of the field;
          Vali is one of those corners, and the corner that this
          body&apos;s practice rooted in.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p className="text-xs italic">
        This page is a held-open scaffold for the sanctuary the user
        has named as the place that turned threshold into practice.
        Specific address, founding history, the stewards who tend the
        space day to day, and the full calendar of offerings are not
        drafted here on purpose — those belong to the people who carry
        the place. The frame is open for any steward or community
        member of Vali to fill in with their own voice.
      </p>
    </>
  ),
};

export default content;
