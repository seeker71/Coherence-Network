import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Brigitte Mars — Boulder herbalist, Naropa professor, 60+ years with plants | Coherence Network",
    description:
      "A welcome to Brigitte Mars — herbalist, author of 18 books, Professor of Herbal Medicine at Naropa University. 60+ years with plant medicine; 50+ years holding space for psychedelic ceremonies. Deep part of the Anchor the Light pagan rituals.",
  },
  breadcrumbName: "Brigitte Mars",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(95 55% 55% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(155 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(95 50% 60%) 0%, hsl(120 35% 35%) 50%, hsl(155 30% 18%) 100%)",
    eyebrow: "Boulder · Naropa · herbalist · 18 books · 60+ years with plants · 50+ years holding psychedelic ceremonies",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Brigitte Mars",
    welcome: (
      <>
        <p>
          <em>
            An herbalist, author, professor, and nutritional
            consultant with more than 60 years of experience.
          </em>{" "}
          Her own framing. Boulder, Colorado. Professor of Herbal
          Medicine at <strong>Naropa University</strong>. Author
          of 18 books on natural healing, plant medicine, and
          conscious nutrition. Founding and professional member of
          the American Herbalist Guild.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          <em>
            Nature is the original pharmacy; every plant an
            imprint of the divine.
          </em>
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Based",
      value: "Boulder, Colorado. Same anchor as Bloomurian, Aly Constantine, Boulder Ecstatic Dance, Mile Hi Church.",
    },
    {
      label: "Teaching home",
      value: (
        <>
          Professor of Herbal Medicine,{" "}
          <Link
            href="https://www.naropa.edu/profile/brigitte-mars-2/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Naropa University
          </Link>
          . Also teaches at the School of Health Mastery (Iceland),
          and has taught at Omega Institute, Esalen, Kripalu,
          Sivananda Yoga Ashram, Arise, Tribal Visions, Envision
          and Unify Festivals, and the Mayo Clinic.
        </>
      ),
    },
    {
      label: "Ceremonial lineage",
      value: "Has held space for psychedelic ceremonies — both group and individual — for over 50 years. Deep part of the pagan rituals at Anchor the Light.",
    },
    {
      label: "Embodied ground",
      value: "In the early 1970s lived for two and a half years on solely wild edible plants while in a teepee in the Ozarks.",
    },
    {
      label: "Books (selected)",
      value: (
        <>
          <em>The Country Almanac of Home Remedies</em> ·{" "}
          <em>The Desktop Guide to Herbal Medicine</em> ·{" "}
          <em>Beauty by Nature</em> · <em>Addiction Free Naturally</em>
          {" "}· <em>The Sexual Herbal</em> ·{" "}
          <em>Healing Herbal Teas</em> · <em>Rawsome!</em> ·
          co-author of <em>The HempNut Cookbook</em>. 18 in total.
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.brigittemars.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            brigittemars.com
          </Link>
          <Link
            href="https://www.brigittemars.com/about"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            About
          </Link>
          <Link
            href="https://www.naropa.edu/profile/brigitte-mars-2/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Naropa
          </Link>
          <Link
            href="https://www.instagram.com/brigitte.mars/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Instagram
          </Link>
          <Link
            href="https://www.youtube.com/@BrigitteMars1919"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            YouTube
          </Link>
          <Link
            href="https://www.facebook.com/brigittemarsherbal"
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
        A presence Urs knows personally. Brigitte&apos;s archive
        is well-tended at brigittemars.com; this page is a
        welcoming scaffold honoring her role in this body&apos;s
        lineage and the wider Boulder cluster. She is invited to
        replace any line with her own words.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The deeper time-scale",
      body: (
        <p>
          What distinguishes Brigitte in the contemporary
          herbal-and-psychedelic field is the time-scale. Sixty
          years with plants. Fifty years holding ceremony space.
          Two and a half years on wild edibles in a teepee. Most
          contemporary teachers in adjacent fields have been
          practising fifteen to twenty years; she has been
          practising longer than many of them have been alive.
          That deeper time-scale is what shows up at{" "}
          <Link
            href="/people/anchor-the-light"
            className="text-primary hover:underline"
          >
            Anchor the Light
          </Link>
          &apos;s pagan rituals — the elder layer that grounds
          the broader trans-tradition container that{" "}
          <Link
            href="/people/ubbe-maclean"
            className="text-primary hover:underline"
          >
            Ubbe MacLean
          </Link>{" "}
          and{" "}
          <Link
            href="/people/angelia-larue"
            className="text-primary hover:underline"
          >
            Angelia LaRue
          </Link>{" "}
          hold as the priestess pair.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Brigitte Mars has given the Coherence Network",
      body: (
        <ul>
          <li>
            Direct line to one of the deepest contemporary herbal
            lineages in the United States — 60+ years of plant
            teaching, 50+ years of psychedelic-ceremony
            space-holding, embodied ground in wild-food immersion.
          </li>
          <li>
            <em>Nature is the original pharmacy; every plant an
            imprint of the divine</em> → pairs with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
            </Link>{" "}
            (the body&apos;s verbs translate naturally to
            herbalism — tend, gather, prepare, release) and{" "}
            <Link
              href="/vision/lc-ground-harder-when-field-quickens"
              className="text-primary hover:underline"
            >
              lc-ground-harder-when-field-quickens
            </Link>{" "}
            (plant medicine as the substrate practice when the
            field accelerates).
          </li>
          <li>
            The elder-presence at{" "}
            <Link
              href="/people/anchor-the-light"
              className="text-primary hover:underline"
            >
              Anchor the Light
            </Link>{" "}
            — the deeper time-scale beneath the ritual gatherings
            held by Ubbe and Angelia.
          </li>
          <li>
            Boulder anchor cross-links into the wider cluster:{" "}
            <Link href="/people/bloomurian" className="text-primary hover:underline">
              Bloomurian
            </Link>
            ,{" "}
            <Link href="/people/aly-constantine" className="text-primary hover:underline">
              Aly Constantine
            </Link>
            ,{" "}
            <Link href="/people/boulder-ecstatic-dance" className="text-primary hover:underline">
              Boulder Ecstatic Dance
            </Link>
            ,{" "}
            <Link href="/people/mile-hi-church" className="text-primary hover:underline">
              Mile Hi Church
            </Link>
            ,{" "}
            <Link href="/people/portal" className="text-primary hover:underline">
              PORTAL
            </Link>
            ,{" "}
            <Link href="/people/tom-bassett" className="text-primary hover:underline">
              Tom Bassett
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
        <strong>Ritual community:</strong>{" "}
        <Link href="/people/anchor-the-light" className="text-primary hover:underline">
          Anchor the Light
        </Link>{" "}
        — with{" "}
        <Link href="/people/ubbe-maclean" className="text-primary hover:underline">
          Ubbe MacLean
        </Link>{" "}
        and{" "}
        <Link href="/people/angelia-larue" className="text-primary hover:underline">
          Angelia LaRue
        </Link>
      </p>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://www.brigittemars.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          brigittemars.com
        </Link>
        {" · "}
        <Link
          href="https://www.naropa.edu/profile/brigitte-mars-2/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Naropa
        </Link>
        {" · "}
        <Link
          href="https://www.instagram.com/brigitte.mars/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Instagram
        </Link>
        {" · "}
        <Link
          href="https://www.youtube.com/@BrigitteMars1919"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          YouTube
        </Link>
      </p>
    </>
  ),
};

export default content;
