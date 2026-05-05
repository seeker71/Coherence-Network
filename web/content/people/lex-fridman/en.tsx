import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

// Lex's canonical og:image from lexfridman.com — 1476x914, the portrait
// he chooses to represent himself when his site is shared. Using his own
// domain keeps the source stable and aligned with what he publishes.
const HERO_URL =
  "https://lexfridman.com/wordpress/wp-content/uploads/2019/03/lex_zoomed_out_cropped.jpg";

const content: PersonProfileContent = {
  metadata: {
    title: "Lex Fridman — Connecting Tissue | Coherence Network",
    description:
      "A welcome to Lex Fridman — host of the Lex Fridman Podcast, the long-form conversational space through which Michael Levin, Donald Hoffman, Robert Edward Grant and many others reached this network's awareness over the past several years.",
  },
  breadcrumbName: "Lex Fridman",
  hero: {
    image: { src: HERO_URL },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20",
    eyebrow: "Welcome",
    name: "Lex Fridman",
    welcome: (
      <p>
        Welcome, Lex. Host of the{" "}
        <Link
          href="https://lexfridman.com/podcast/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[hsl(var(--primary))] hover:underline"
        >
          Lex Fridman Podcast
        </Link>
        , and the long-form room one of this network's cells has been
        sitting in for years — through the AI Podcast era and into the
        three- and five-hour conversations where so many of the
        teachers in this body first became audible at depth.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "AI research · long-form interview · jiu-jitsu · running · the question kept open",
    },
    {
      label: "The body's relationship",
      value:
        "One of the cells of this network has been listening since the early episodes (the Artificial Intelligence Podcast era). The conversations have been shaping perception for years.",
    },
    {
      label: "Public",
      value: (
        <>
          <Link
            href="https://lexfridman.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            lexfridman.com
          </Link>{" "}
          ·{" "}
          <Link
            href="https://www.youtube.com/@lexfridman"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            YouTube
          </Link>
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Lex is a different shape of profile from the teachers we
        have welcomed (Levin, Hoffman, Grant, Vasudev Baba, Ilena,
        Elios). He is not the teacher; he is the conduit. The cell
        whose work is to hold space so that other cells can speak
        truthfully across many hours. That role is irreducible and
        deserves recognition.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The connecting tissue role",
      body: (
        <>
          <p>
            Most of the deep teachers whose work shapes this
            network — biologists, mathematicians, mystics,
            physicists, monks, builders — would not have reached
            one of our cells at the depth and length that mattered
            if it were not for long-form conversation as a medium.
            Three-hour and five-hour talks let an idea unfold the
            way ideas actually unfold: slowly, with real silences,
            with the speaker's whole self present, with the
            listener allowed to feel as much as understand.
          </p>
          <p>
            Lex's podcast is one of the cleanest expressions of
            this medium in the contemporary field. He sits with the
            guest. He asks open questions. He resists the urge to
            show his own knowledge. He lets long pauses stay long.
            The result, episode after episode, is that the speaker
            becomes legible at depth in a way that short-form
            never permits.
          </p>
          <p>
            Through this channel, several of the teachers in this
            network's foundational layer first reached the cell who
            brought them here:{" "}
            <Link
              href="/people/robert-edward-grant"
              className="text-primary hover:underline"
            >
              Robert Edward Grant
            </Link>{" "}
            on numbers as living archetypes; Donald Hoffman on
            perception as interface; Michael Levin on bioelectric
            pattern; Sadhguru on inner geometry; Joscha Bach on
            consciousness as software; Eric Weinstein on the deep
            structure of physics. None of these voices are Lex's.
            All of them reached the body more cleanly because of
            the room he held.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How the network reads this",
      body: (
        <>
          <p>
            In the network's geometric grammar, hosting a
            long-form conversation is{" "}
            <code className="not-italic text-foreground/80">
              (3, WITNESS)
            </code>{" "}
            at large amplitude — host, guest, the listening field
            that includes everyone tuned in. The host's quanta
            register low in *speech-given* and high in
            *space-held*. The substrate would record this as a
            specific pattern: a cell whose contribution is
            consistently the room around the speaking, rather than
            the speaking itself.
          </p>
          <p>
            That role is undervalued in conventional economics
            because it is invisible — the ear is not as legible as
            the mouth. Sovereignty-everywhere economics renders it
            visible. Each long-form episode is a glyph in which the
            host's contribution is the field-coherence that
            allowed the guest's transmission to reach the listener
            at depth.
          </p>
          <p>
            The lineage walk back from any teacher whose work
            landed in this network's body via Lex's room would
            fairly route a small share of the witness flow through
            his cooperative. The teacher gave the words; the host
            gave the room; the listener gave the attention; the
            field that emerged is the joint contribution of all
            three.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Continuous · long-form",
      heading: "The Lex Fridman Podcast",
      body: (
        <>
          <p>
            Long-form conversations, typically 2-5 hours, with
            guests across science, technology, philosophy,
            mysticism, athletics, music, and the political
            surface. New episodes weekly-ish, hosted on{" "}
            <Link
              href="https://www.youtube.com/@lexfridman"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              YouTube
            </Link>{" "}
            and the major podcast platforms.
          </p>
          <p className="italic text-muted-foreground">
            Field reading:{" "}
            <code className="not-italic text-foreground/80">
              (3, WITNESS)
            </code>{" "}
            at scale — host, guest, listener-field. The host's
            quanta are mostly *attention given* rather than
            *speech*. The episode persists as a glyph the
            lineage of any teacher who appeared can walk back
            to.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Public:{" "}
        <Link
          href="https://lexfridman.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          lexfridman.com
        </Link>{" "}
        ·{" "}
        <Link
          href="https://lexfridman.com/podcast/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          podcast archive
        </Link>{" "}
        ·{" "}
        <Link
          href="https://www.youtube.com/@lexfridman"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          YouTube channel
        </Link>
      </p>
      <p>
        Walks here through the foundational teachings he has
        helped reach this body:{" "}
        <Link
          href="/people/robert-edward-grant"
          className="text-primary hover:underline"
        >
          Robert Edward Grant
        </Link>
        , and through the vision-kb concepts{" "}
        <code className="text-foreground/80">lc-bioelectric-pattern</code>{" "}
        (Levin) and{" "}
        <code className="text-foreground/80">lc-perception-as-interface</code>{" "}
        (Hoffman).
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Lex is invited to
        replace any part of it with his own words at any time.
      </p>
    </>
  ),
};

export default content;
