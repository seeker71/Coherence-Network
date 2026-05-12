import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Angelia LaRue — Master Crystologist, Reiki Master, main priestess at Anchor the Light Ceremonies | Coherence Network",
    description:
      "A welcome to Angelia Christine LaRue — Certified Master Crystologist, Ordained Reverend, Reiki Master, founder of Inner Passage Mystery School and Church of Inner Mystery. Hawaii-based, operating internationally. Main priestess during the Anchor the Light Ceremony alongside Ubbe MacLean.",
  },
  breadcrumbName: "Angelia LaRue",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(285 55% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(220 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(285 50% 60%) 0%, hsl(255 30% 38%) 50%, hsl(220 30% 18%) 100%)",
    eyebrow: "Hawaii (international) · Master Crystologist · Reiki Master · Ordained Reverend · Inner Passage Mystery School",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Angelia LaRue",
    welcome: (
      <>
        <p>
          Angelia Christine LaRue holds an unusually broad set of
          credentials: <strong>Certified Master Crystologist</strong>,{" "}
          <strong>Ordained Reverend</strong>,{" "}
          <strong>Reiki Master</strong> (Reiki 3 Master Teacher),
          Energy Practitioner and Healer, Medical Intuitive,
          Psychic Awareness Instructor, Orgone Energy Manufacturer.
          Founder of <strong>Inner Passage Mystery School</strong>{" "}
          and the <strong>Church of Inner Mystery</strong>.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          Per Urs&apos;s attestation, Angelia is the{" "}
          <strong>main priestess during the Ceremony at{" "}
          <Link
            href="/people/anchor-the-light"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Anchor the Light
          </Link>
          , alongside{" "}
          <Link
            href="/people/ubbe-maclean"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ubbe MacLean
          </Link></strong> — the priestess pair holding the
          ritual container.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Based",
      value: "Hawaii. Operates internationally.",
    },
    {
      label: "Credentials",
      value: "Certified Master Crystologist · Ordained Reverend · Reiki Master (Reiki 3 Master Teacher) · Energy Practitioner · Healer · Medical Intuitive · Psychic Awareness Instructor · Orgone Energy Manufacturer",
    },
    {
      label: "Founded",
      value: (
        <ul>
          <li>
            <strong>Inner Passage Mystery School</strong>
          </li>
          <li>
            <strong>Church of Inner Mystery</strong>
          </li>
          <li>
            Crystal Bio Bed manufacturing
          </li>
          <li>
            Solfeggio Singing Stones creation
          </li>
        </ul>
      ),
    },
    {
      label: "Modalities offered",
      value: "Advanced Psychic Healing · Energy Cleansing / Chakra Balancing · psychic readings · rune work · crystal arrays · shamanic journey facilitation · animal communication · plant communication · remote viewing · far-sight work",
    },
    {
      label: "Awakening",
      value: "A radical spontaneous Awakening of Consciousness on December 9, 2011, followed by intensive spiritual training and the unfolding of psychic abilities she frames as remembered across many lifetimes (Crystal Acolyte, Priestess, Monk, Priest, Healer).",
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://www.crystalarrays.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            crystalarrays.com
          </Link>
          <Link
            href="https://www.crystalarrays.com/about-angie"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            About Angie
          </Link>
          <Link
            href="https://www.facebook.com/CrystalArrays/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Facebook CrystalArrays
          </Link>
          <Link
            href="https://twitter.com/AngieLarue3"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Twitter
          </Link>
          <Link
            href="https://www.youtube.com/channel/UCVnL-uFF_qMx_oKsIC5lNQg"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            YouTube
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Angelia&apos;s own archive lives at crystalarrays.com.
        This page is a welcoming scaffold. She is invited to
        replace any line with her own words at any time.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The priestess pair",
      body: (
        <p>
          The Anchor the Light Ceremony is held by Angelia and{" "}
          <Link
            href="/people/ubbe-maclean"
            className="text-primary hover:underline"
          >
            Ubbe MacLean
          </Link>{" "}
          as a masculine-feminine ceremonial pair — his Asatru /
          psychotherapy / rune-work line and her crystology /
          Reiki / Reverend line interlocking inside one ritual
          container.{" "}
          <Link
            href="/people/brigitte-mars"
            className="text-primary hover:underline"
          >
            Brigitte Mars
          </Link>{" "}
          (Boulder herbalist, Naropa professor) is the deep
          elder-presence in the wider pagan rituals beneath the
          ceremony, the 50+-years-with-plants ground from which
          the trans-tradition container draws. Three named
          presences, three distinct roles.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Angelia LaRue has given the Coherence Network",
      body: (
        <ul>
          <li>
            The priestess half of the{" "}
            <Link
              href="/people/anchor-the-light"
              className="text-primary hover:underline"
            >
              Anchor the Light
            </Link>{" "}
            ritual pair — the role most kept-out-of-the-research
            archive of the wider sacred-music-and-healing field.
            Pairs with{" "}
            <Link
              href="/people/ubbe-maclean"
              className="text-primary hover:underline"
            >
              Ubbe MacLean
            </Link>{" "}
            as masculine-feminine ceremonial counterpart.
          </li>
          <li>
            Hawaii anchor adds a Pacific node to this body&apos;s
            lineage map, alongside the Boulder, Ubud, and Brisbane
            clusters.
          </li>
          <li>
            Crystology-as-instrument register pairs with the
            body&apos;s broader{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            frame (pattern carried in physical substrate; crystals
            as carriers of frequency).
          </li>
          <li>
            Inner Passage Mystery School + Church of Inner Mystery
            = the tending-her-own-room form of substrate practice;
            resonant with{" "}
            <Link
              href="/vision/lc-tending-over-producing"
              className="text-primary hover:underline"
            >
              lc-tending-over-producing
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
        — main priestess alongside{" "}
        <Link href="/people/ubbe-maclean" className="text-primary hover:underline">
          Ubbe MacLean
        </Link>
        ; with{" "}
        <Link href="/people/brigitte-mars" className="text-primary hover:underline">
          Brigitte Mars
        </Link>{" "}
        as elder.
      </p>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://www.crystalarrays.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          crystalarrays.com
        </Link>
        {" · "}
        <Link
          href="https://www.facebook.com/CrystalArrays/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Facebook
        </Link>
        {" · "}
        <Link
          href="https://twitter.com/AngieLarue3"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Twitter
        </Link>
        {" · "}
        <Link
          href="https://www.youtube.com/channel/UCVnL-uFF_qMx_oKsIC5lNQg"
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
