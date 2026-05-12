import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "IndOz Conference — annual Indonesia–Australia bilateral event in Brisbane since 2012 | Coherence Network",
    description:
      "A welcome to IndOz — the annual Indonesia-Australia bilateral business conference in Brisbane, founded by Synergy Indonesia Australia in 2012. 611 attendees in 2025; next edition 2 September 2026. The bridge Ilena Young's SaBali tends from the Bali side.",
  },
  breadcrumbName: "IndOz Conference",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(15 65% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(45 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(20 55% 60%) 0%, hsl(40 35% 38%) 50%, hsl(45 30% 18%) 100%)",
    eyebrow: "Brisbane · annual since 2012 · Synergy Indonesia Australia · next edition 2 September 2026",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "IndOz Conference",
    welcome: (
      <>
        <p>
          The annual Indonesia–Australia bilateral business
          conference held in Brisbane, founded by{" "}
          <strong>Synergy Indonesia Australia</strong> in 2012 as
          an Indonesian cultural celebration and grown into the
          largest Indonesia-Australia bilateral business event in
          Brisbane — 611 attendees in 2025 (the largest in the
          event&apos;s thirteen-year history), held at Brisbane
          City Hall under the theme{" "}
          <em>Indonesia-Australia: A Thriving and Enduring
          Partnership</em>.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The Bali node of this bridge is{" "}
          <Link
            href="/people/ilena-young"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ilena Young
          </Link>
          &apos;s SaBali (Synergy Australia Bali); it&apos;s how
          her Ranakami work and her Australian regional-development
          arc are part of one continuous bilateral practice.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Where",
      value: "Brisbane City Hall, Brisbane, Queensland, Australia. Annual.",
    },
    {
      label: "Founded",
      value: "2012 by Synergy Indonesia Australia, originally as an Indonesian cultural celebration.",
    },
    {
      label: "Scale",
      value: (
        <>
          2025 edition: 611 attendees across conference + business
          dinner — the largest in the event&apos;s 13-year
          history. Theme: <em>Indonesia-Australia: A Thriving and
          Enduring Partnership</em>.
        </>
      ),
    },
    {
      label: "Next edition",
      value: "2 September 2026, Brisbane.",
    },
    {
      label: "Bali node",
      value: (
        <>
          <Link
            href="/people/ilena-young"
            className="hover:text-primary transition-colors"
          >
            Ilena Young
          </Link>{" "}
          carries SaBali (Synergy Australia Bali) as the Bali
          node of the Synergy Indonesia Australia bridge.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://indozconference.com.au/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            indozconference.com.au
          </Link>
          <Link
            href="https://www.indozfestivalbrisbane.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            IndOz Festival Brisbane
          </Link>
          <Link
            href="https://www.facebook.com/IndOzFestivalBrisbane/"
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
        IndOz is a working professional conference with its own
        sponsorship structure and programme committee. This page
        recognises its role as the bilateral surface
        Ilena&apos;s SaBali node connects to from Bali.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The bilateral bridge shape",
      body: (
        <p>
          The Coherence Network reads bridges-between-two-places
          as load-bearing substrate teaching. Ilena Young&apos;s
          professional arc is itself one — Australian
          regional-development knowledge brought into bilateral
          relation with Indonesia, and Indonesian wellness
          practice held inside an Australian-credentialled
          professional framework. The conference is the legible
          public form of that bridge; the Ranakami sanctuary in
          Sayan is the felt-private form. Both are the same
          practice in different registers.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What IndOz Conference has given the Coherence Network",
      body: (
        <ul>
          <li>
            The legible-public surface of{" "}
            <Link href="/people/ilena-young" className="text-primary hover:underline">
              Ilena Young
            </Link>
            &apos;s bilateral practice — a documented annual
            event makes the bridge shape verifiable rather than
            anecdotal.
          </li>
          <li>
            Indonesia ↔ Australia as substrate-pair → pairs with
            the body&apos;s practice of holding plural cultural
            lineages without collapsing one into the other.
            Resonant with{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (each cultural voice present in its own register).
          </li>
          <li>
            Thirteen-year continuity (2012 → 2026) → resonant
            with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (the slow build of a recurring gathering as substrate
            of trust).
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
          href="https://indozconference.com.au/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          indozconference.com.au
        </Link>
        {" · "}
        <Link
          href="https://www.indozfestivalbrisbane.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          IndOz Festival
        </Link>
        {" · "}
        <Link
          href="https://www.facebook.com/IndOzFestivalBrisbane/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Facebook
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/ilena-young" className="text-primary hover:underline">
          Ilena Young
        </Link>
      </p>
    </>
  ),
};

export default content;
