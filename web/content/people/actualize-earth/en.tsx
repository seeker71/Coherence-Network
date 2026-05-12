import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Actualize Earth — conscious connection, community-powered technology, regenerative systems | Coherence Network",
    description:
      "A welcome to Actualize Earth — the platform for conscious connection, community-powered technology, and regenerative systems, founded and led by Tom Bassett (Juicy Life) in Boulder, CO. Tools rooted in human design, gene keys, and collective ownership.",
  },
  breadcrumbName: "Actualize Earth",
  hero: {
    background:
      "radial-gradient(ellipse at 35% 25%, hsl(155 60% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(220 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(155 50% 60%) 0%, hsl(200 30% 35%) 50%, hsl(220 30% 20%) 100%)",
    eyebrow: "Boulder · platform · human design + gene keys + collective ownership · the cooperative future",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Actualize Earth",
    welcome: (
      <>
        <p>
          The platform for <strong>conscious connection,
          community-powered technology, and regenerative systems</strong>{" "}
          founded and led by{" "}
          <Link
            href="/people/tom-bassett"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Tom Bassett
          </Link>{" "}
          (Juicy Life) as CEO and Lead Engineer. Aims to redefine
          social gathering and community, fostering a{" "}
          <em>cooperative future</em> through tools rooted in
          human design, gene keys, and collective ownership.
          Boulder-anchored.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          A sibling-platform to the Coherence Network in the
          same field: technology as substrate for living
          relationship, not service-marketplace skin laid over
          conventional engagement metrics.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "What it is",
      value: "Platform for conscious connection, community-powered technology, regenerative systems. Local social networks for the evolution of consciousness.",
    },
    {
      label: "Founder & lead engineer",
      value: (
        <Link
          href="/people/tom-bassett"
          className="hover:text-primary transition-colors"
        >
          Tom Bassett (Juicy Life)
        </Link>
      ),
    },
    {
      label: "Tools",
      value: "Human design · gene keys · collective ownership. The form of the platform respects what each contributor's own design is, rather than flattening every user to the same shape.",
    },
    {
      label: "Based",
      value: "Boulder, Colorado — same cluster as Bloomurian, Aly Constantine, Boulder Ecstatic Dance, the wider Colorado anchor.",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://actualize.earth/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            actualize.earth
          </Link>
          <Link
            href="https://actualize.earth/team"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Team
          </Link>
          <Link
            href="https://www.facebook.com/actualizeearth/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Facebook
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Actualize Earth is a working platform with its own active
        tending. This page recognises it as a sibling-substrate in
        the same field the Coherence Network is building from —
        not affiliated, not contracted, just aligned at the level
        of architectural posture.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "Sibling-substrate, not affiliation",
      body: (
        <p>
          The Coherence Network reads Actualize Earth as a
          peer working at the same intersection: technology as
          substrate for living relationship, not a service-marketplace
          skin laid over conventional engagement metrics. Where
          the Coherence Network is the body Urs and the sibling
          intelligences are tending, Actualize Earth is what Tom
          and his team are tending. The two share architectural
          posture even though the codebases and lineages are
          different — both treat <em>collective ownership</em>{" "}
          and <em>consciousness-evolution</em> as load-bearing
          rather than aspirational.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Actualize Earth has given the Coherence Network",
      body: (
        <ul>
          <li>
            A working peer in the substrate-level redesign of
            social technology. Concept resonance with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (the cooperative-future shape).
          </li>
          <li>
            Use of human design and gene keys as tools-of-the-platform
            is itself a substrate teaching → pairs with{" "}
            <Link
              href="/vision/lc-frequency-routes-reception"
              className="text-primary hover:underline"
            >
              lc-frequency-routes-reception
            </Link>{" "}
            (community-powered means each cell receives at its
            own band).
          </li>
          <li>
            <em>Right relationship to Life</em> as engineering
            principle → pairs with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (the body&apos;s verbs translate naturally into
            platform design).
          </li>
          <li>
            Boulder anchor of the cooperative-tech / consciousness
            cluster — geographic peer of the body&apos;s wider
            Colorado field.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Lead:</strong>{" "}
        <Link href="/people/tom-bassett" className="text-primary hover:underline">
          Tom Bassett (Juicy Life)
        </Link>
      </p>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://actualize.earth/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          actualize.earth
        </Link>
        {" · "}
        <Link
          href="https://actualize.earth/team"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          team
        </Link>
        {" · "}
        <Link
          href="https://www.facebook.com/actualizeearth/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Facebook
        </Link>
      </p>
    </>
  ),
};

export default content;
