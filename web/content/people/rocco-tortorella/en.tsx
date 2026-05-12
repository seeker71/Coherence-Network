import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const HERO_BACKGROUND =
  "radial-gradient(ellipse at 70% 25%, rgba(255, 168, 102, 0.55) 0%, rgba(232, 110, 88, 0.3) 24%, rgba(168, 76, 124, 0.28) 50%, rgba(76, 56, 132, 0.36) 72%, rgba(28, 22, 56, 0.88) 100%), linear-gradient(180deg, rgba(255, 198, 138, 0.2) 0%, rgba(176, 96, 152, 0.22) 40%, rgba(34, 28, 70, 0.92) 100%)";

const content: PersonProfileContent = {
  metadata: {
    title:
      "Rocco Tortorella — Boulder · Courtyard Constellations · Rise & Vibes · Unison | Coherence Network",
    description:
      "A welcome to Rocco Tortorella — Aly Constantine's husband, co-host of the Courtyard Constellations gatherings at their Boulder home, videographer of Ocean Bloom and the wider transformational-music ecology, wearer and freely-sharer of his own clothing collection, natural center of gatherings at Rise & Vibes, Unison, and Burning Man.",
  },
  breadcrumbName: "Rocco Tortorella",
  hero: {
    background: HERO_BACKGROUND,
    eyebrow: "Welcome",
    name: "Rocco Tortorella",
    welcome: (
      <p>
        Husband to{" "}
        <Link
          href="/people/aly-constantine"
          className="text-primary hover:underline"
        >
          Aly Constantine
        </Link>
        , co-host of the{" "}
        <strong>Courtyard Constellations</strong> gatherings at their
        Boulder home, videographer behind{" "}
        <Link
          href="https://roccomountain.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          roccomountain.com
        </Link>{" "}
        — and a loving, warm, naturally-flowing presence with a flair
        for unique expression. He keeps his own clothing collection
        and shares it freely with friends, and he is one of those
        cells around whom a gathering simply organizes itself —
        witnessed at <strong>Rise &amp; Vibes</strong>, at{" "}
        <strong>Unison</strong>, and (held by lineage report) at{" "}
        <strong>Burning Man</strong>.
      </p>
    ),
  },
  facts: [
    {
      label: "Field",
      value:
        "Hosting · videography · wearable-art generosity · gathering-presence · transformational-music documentation",
    },
    {
      label: "Held with",
      value: (
        <>
          <Link
            href="/people/aly-constantine"
            className="hover:text-primary transition-colors"
          >
            Aly Constantine
          </Link>{" "}
          (wife · co-host of Courtyard Constellations); close
          friendships across the Boulder transformational-music ecology
          with{" "}
          <Link
            href="/people/brigitte-mars"
            className="hover:text-primary transition-colors"
          >
            Brigitte Mars
          </Link>
          {" "}(see also{" "}
          <Link
            href="/people/pagan-ritual"
            className="hover:text-primary transition-colors"
          >
            Pagan Ritual
          </Link>
          ),{" "}
          <strong>Tay Blevons</strong> (see{" "}
          <Link
            href="/people/portal"
            className="hover:text-primary transition-colors"
          >
            PORTAL
          </Link>
          ), <strong>Andy Babb</strong> and{" "}
          <strong>Lara Elle</strong> (both deeply connected to{" "}
          <Link
            href="/people/rhythm-sanctuary"
            className="hover:text-primary transition-colors"
          >
            Rhythm Sanctuary
          </Link>
          ),{" "}
          <Link
            href="/people/bloomurian"
            className="hover:text-primary transition-colors"
          >
            Robin Liepman (Bloomurian)
          </Link>
          , and <strong>Danny Balgooyen</strong> (Boulder Ecstatic
          Dance)
        </>
      ),
    },
    {
      label: "Recurring rooms",
      value: (
        <>
          <strong>Courtyard Constellations</strong> (the home gatherings
          he co-hosts with Aly) ·{" "}
          <strong>Rise &amp; Vibes</strong> festival ·{" "}
          <strong>Unison</strong> festival ·{" "}
          <Link
            href="/people/ocean-bloom-2024"
            className="hover:text-primary transition-colors"
          >
            Ocean Bloom
          </Link>{" "}
          (videographer) ·{" "}
          <Link
            href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Boulder Ecstatic Dance
          </Link>{" "}
          · <strong>Burning Man</strong> (held in his lineage by report)
        </>
      ),
    },
    {
      label: "Public anchor",
      value: (
        <Link
          href="https://roccomountain.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          roccomountain.com
        </Link>
      ),
    },
    {
      label: "In this body's awareness",
      value: (
        <>
          Witnessed directly at Rise &amp; Vibes, at Unison, and
          across the months of February through December 2025, when{" "}
          <Link
            href="/people/urs"
            className="hover:text-primary transition-colors"
          >
            Urs
          </Link>{" "}
          lived as a houseguest at Aly and Rocco's Boulder home and
          watched the Courtyard Constellations form around him. After
          the houseguest months, this body remained in the Boulder–
          Longmont area through Rocco's April 18, 2026 birthday and
          the departure for Bali two days later. Burning Man sits in
          Rocco's lineage by report; this body has not been there.
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming scaffold. Rocco is held here through ten months of
        living under the same roof at the Boulder house, plus direct
        witness at the festival-rooms where he naturally becomes a
        center of gathering. From this body's witness: the most unique
        and open-hearted soul this cell has met — and an honor to
        have lived with. The Burning Man thread is named because it is
        part of his lineage and his friendships, not because this body
        has stood on the playa with him. Rocco is invited to replace
        any part of this page with his own words at any time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "How he is in a room",
      body: (
        <>
          <p>
            Loving, warm, naturally flowing — three words that carry
            most of what people who have spent time with Rocco
            recognize. He does not push toward the center of a
            gathering; the gathering simply organizes itself around
            him. The flair for unique expression is part of how this
            works: a piece of his own clothing, the camera in his
            hand, the angle he reads the light from, the unhurried way
            he is wherever he is — the room finds itself oriented
            toward that frequency without anyone having to name it.
          </p>
          <p>
            This is a particular kind of leadership-without-leading:
            the campfire posture (
            <Link
              href="/vision/lc-tend-your-flame"
              className="text-primary hover:underline"
            >
              tend your flame
            </Link>
            ) translated into festival-fields and home-courtyards. The
            people around him receive without being asked to receive.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "What he gives",
      body: (
        <>
          <p>
            <strong>Clothing as gift.</strong> Rocco keeps his own
            clothing collection — pieces he has gathered, made, found,
            curated — and shares it freely with friends. The garments
            move outward into the constellation; they show up on other
            bodies at the festivals, at the courtyard, at the Sunday
            morning ballroom. The economy underneath is one of
            wearable-art generosity: what he holds is held to be
            shared, not held to be kept.
          </p>
          <p>
            <strong>Videography as documentation-as-gift.</strong>{" "}
            Through{" "}
            <Link
              href="https://roccomountain.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              roccomountain.com
            </Link>{" "}
            he carries the camera into the rooms his life is already
            in — Ocean Bloom most visibly, but also the broader
            transformational-music gatherings — and what comes back is
            evidence that the night happened, that the field was real,
            that the artists were seen. The footage is its own kind of
            attestation.
          </p>
          <p>
            <strong>The household opened.</strong> The Boulder home he
            keeps with Aly is the courtyard around which the
            Constellations gather. Opening a household is one of the
            quieter forms of contribution to a constellation; the cells
            who open theirs become the anchors others orbit through.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "Held together with Aly",
      body: (
        <>
          <p>
            Rocco and{" "}
            <Link
              href="/people/aly-constantine"
              className="text-primary hover:underline"
            >
              Aly
            </Link>{" "}
            are partnered at the relational scale and at the
            gathering-organ scale at the same time. Aly's curatorial
            and connecting work — Conscious Roots Presents, Boulder
            Ecstatic Dance, the music threading into Rise &amp; Vibes
            and Unison — meets Rocco's hosting-presence and lens-work
            at the household and at the festival. The Courtyard
            Constellations gatherings are the form in which the two
            scales become one: a home, a gathering, a documented
            night, a constellation that knows itself.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Friendships",
      heading: "The Boulder constellation he and Aly are inside",
      body: (
        <>
          <p>
            The closest of their shared friendships thread the
            transformational-music and conscious-community ecology of
            Boulder and the wider Colorado-festival arc:
          </p>
          <ul className="list-disc pl-5 space-y-1.5">
            <li>
              <Link
                href="/people/brigitte-mars"
                className="text-primary hover:underline"
              >
                Brigitte Mars
              </Link>{" "}
              — Boulder herbalist, Naropa professor, and the elder
              presence inside{" "}
              <Link
                href="/people/pagan-ritual"
                className="text-primary hover:underline"
              >
                Pagan Ritual
              </Link>
              .
            </li>
            <li>
              <strong>Tay Blevons</strong> — woven through{" "}
              <Link
                href="/people/portal"
                className="text-primary hover:underline"
              >
                PORTAL
              </Link>
              , the Late-Night Takeover at Meow Wolf during MAPS
              Psychedelic Science 2025.
            </li>
            <li>
              <strong>Andy Babb</strong> and{" "}
              <strong>Lara Elle</strong> — life-partnered musical duo
              (Andy Babb and the Big Beautiful Band) who met dancing
              at{" "}
              <Link
                href="/people/rhythm-sanctuary"
                className="text-primary hover:underline"
              >
                Rhythm Sanctuary
              </Link>{" "}
              in February 2014; both deeply connected to the Sanctuary
              lineage.
            </li>
            <li>
              <Link
                href="/people/bloomurian"
                className="text-primary hover:underline"
              >
                Robin Liepman (Bloomurian)
              </Link>{" "}
              — Boulder Ecstatic Dance co-founder, longtime Liquid
              Bloom collaborator, the cell who once shared a roof with
              Amani Friend in the Boulder mountains.
            </li>
            <li>
              <strong>Danny Balgooyen</strong> — Sunday-morning
              co-host at{" "}
              <Link
                href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Boulder Ecstatic Dance
              </Link>
              , co-tending the floor with Aly and Robin.
            </li>
          </ul>
          <p className="italic text-muted-foreground">
            The list is the held part of the constellation, not the
            whole of it; other friendships remain open and will be
            named as Rocco wishes.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "The birthday gathering — closing the Boulder arc",
      body: (
        <>
          <p>
            <strong>April 18, 2026 — Rocco's 36th.</strong> The
            celebration the constellation made for him took the shape
            of a jungle-themed evening at the home: a banner with his
            name, a bonfire in the courtyard, drumming, dancing, the
            dog in the middle of it all, and a three-tier cake with 36
            on top. The constellation that this page lists by name —{" "}
            <Link
              href="/people/aly-constantine"
              className="text-primary hover:underline"
            >
              Aly
            </Link>
            ,{" "}
            <Link
              href="/people/brigitte-mars"
              className="text-primary hover:underline"
            >
              Brigitte
            </Link>
            , Tay, Andy, Lara, Robin, Danny, and the wider circle —
            became, for one evening, a single room around him,
            celebrating the unique and open-hearted soul they each
            know him to be.
          </p>
          <p>
            For{" "}
            <Link
              href="/people/urs"
              className="text-primary hover:underline"
            >
              this body
            </Link>
            , the timing was a gift. The birthday landed two days
            before the departure for Bali on <strong>April 20, 2026</strong>{" "}
            — the closing of the Boulder arc that had begun when Aly
            and Rocco opened their home in February 2025. The Boulder
            configuration this page describes — Conscious Roots,
            Boulder Ecstatic Dance, the courtyard, the festival
            friendships, the household — gathered itself into one
            evening of celebration around the cell whose presence had
            been its natural center all along. It was, for this body,
            the most divine
            goodbye to the Boulder chapter that could have been
            imagined.
          </p>
          <p>
            That the constellation organized itself around Rocco that
            night, without needing to be asked, is the same thing the
            page names everywhere else — only at the highest stakes
            available to it. The room finds its center; the center is
            the one who has been holding it open all along.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Festival presence",
      heading: "Rise & Vibes, Unison, Burning Man",
      body: (
        <>
          <p>
            <strong>Rise &amp; Vibes</strong> and{" "}
            <strong>Unison</strong> are the two festival-rooms in
            which this body has directly witnessed Rocco at the center
            of a gathering — the same naturally-flowing presence the
            household carries, scaled to a festival field. Many of the
            artists landing on those stages travel through Aly's
            connecting work; many of the documented moments travel
            through Rocco's lens.
          </p>
          <p>
            <strong>Burning Man</strong> sits in Rocco's lineage. It
            is part of his friendships and his gathering-life, and it
            shows up across the constellation that knows him. This
            body has not stood on the playa, so the thread is held by
            report, not by direct witness — named here so the lineage
            is honest about what it carries.
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
          href="https://roccomountain.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          roccomountain.com
        </Link>
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Rocco is invited to
        replace any part of it with his own words at any time. The
        texture of the household months and the friendships is held
        privately and is not part of the substrate's public rendering.
      </p>
    </>
  ),
};

export default content;
