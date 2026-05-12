import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Anchor the Light — a living spiritual path · Ceremony held by Ubbe MacLean & Angelia LaRue, with Brigitte Mars as elder | Coherence Network",
    description:
      "A welcome to Anchor the Light — a living spiritual path rooted in direct encounter with the Divine through music, movement, and embodied awareness. The Ceremony is held by Ubbe MacLean and Angelia LaRue as priestess pair; Brigitte Mars is the elder presence deep within the pagan rituals; the wider community draws on Freya Aswynn's runological line. Monthly wellness retreats, pagan ritual gatherings, the Healing from the Tree rune-work book.",
  },
  breadcrumbName: "Anchor the Light",
  hero: {
    background:
      "radial-gradient(ellipse at 35% 25%, hsl(45 65% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(155 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(45 55% 60%) 0%, hsl(120 30% 35%) 50%, hsl(155 30% 18%) 100%)",
    eyebrow: "A living spiritual path · Enter the Ritual. Become the Experience.",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Anchor the Light",
    welcome: (
      <>
        <p>
          <em>
            A living spiritual path rooted in direct encounter
            with the Divine through music, movement, and embodied
            awareness.
          </em>{" "}
          The invitation: <em>Enter the Ritual. Become the
          Experience.</em> The <strong>Ceremony</strong> is held by{" "}
          <Link
            href="/people/ubbe-maclean"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ubbe MacLean
          </Link>{" "}
          and{" "}
          <Link
            href="/people/angelia-larue"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Angelia LaRue
          </Link>{" "}
          as the <strong>priestess pair</strong> — Ubbe carrying
          the Asatru / psychotherapy / rune-work line, Angelia
          carrying the crystology / Reiki / Reverend line.{" "}
          <Link
            href="/people/brigitte-mars"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Brigitte Mars
          </Link>{" "}
          is the <strong>elder presence</strong> deep within the
          pagan rituals — Boulder herbalist, Naropa professor, 60+
          years with plant medicine, 50+ years holding ceremonial
          space. The wider community also draws on the runologist{" "}
          <strong>Freya Aswynn</strong> (author of{" "}
          <em>Leaves of Yggdrasil</em>).
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          A trans-tradition spiritual community — Norse Asatru,
          Reiki lineage, clinical psychotherapy, herbal medicine,
          qi gong, sound healing, dance — all held inside one
          ritual frame, without flattening any of them.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Priestess pair (Ceremony)",
      value: (
        <>
          <Link href="/people/ubbe-maclean" className="hover:text-primary transition-colors">
            Ubbe MacLean
          </Link>
          {" · "}
          <Link href="/people/angelia-larue" className="hover:text-primary transition-colors">
            Angelia LaRue
          </Link>
        </>
      ),
    },
    {
      label: "Elder presence (pagan rituals)",
      value: (
        <>
          <Link href="/people/brigitte-mars" className="hover:text-primary transition-colors">
            Brigitte Mars
          </Link>
          {" — Boulder herbalist, Naropa professor; 60+ years with plant medicine, 50+ years holding ceremonial space"}
        </>
      ),
    },
    {
      label: "Wider community",
      value: "Runologist Freya Aswynn (author of Leaves of Yggdrasil) — the broader rune-line the ritual frame draws on.",
    },
    {
      label: "Monthly wellness retreats",
      value: "Qi Gong · mindfulness meditation · acupuncture · sound bathing · biofeedback · IV therapy · Reiki · energy healing & protection · forest bathing · plant medicines · life-enhancement skill building · fully organic meals · visionary art · dance — woven into one container",
    },
    {
      label: "Services held",
      value: "Life Enhancement Coaching · Mindfulness-Based Stress Reduction · Couples & Relationship Coaching · Reiki · Equine Healing Sessions · Personal Clearings · Rune Reading · Fitness Training",
    },
    {
      label: "Published",
      value: (
        <>
          Ubbe MacLean&apos;s rune-healing book{" "}
          <em>
            Healing From the Tree: Using Runes for Emotional,
            Physical & Soul Healing
          </em>
          .{" "}
          <Link
            href="https://anchorthelight.org/healing-from-the-tree-using-runes-for-emotional-physical-soul-healing/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            More
          </Link>
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://anchorthelight.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            anchorthelight.org
          </Link>
          <Link
            href="https://anchorthelight.org/anchor-the-light/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Anchor the Light Church
          </Link>
          <Link
            href="https://anchorthelight.org/anchor-the-light-wellness-retreats/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Wellness Retreats
          </Link>
          <Link
            href="https://www.facebook.com/anchorthelight9"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Facebook (@anchorthelight9)
          </Link>
          <Link
            href="https://anchorthelight.org/media-appearances-resources/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Media appearances
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A working church and retreat community with its own
        ongoing tending. This page recognises its role in this
        body&apos;s wider field as a trans-tradition working
        example, not affiliation.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Anchor the Light has given the Coherence Network",
      body: (
        <ul>
          <li>
            A working example of <em>trans-tradition spiritual
            community</em> — Norse heathen Asatru, Reiki lineage,
            clinical psychotherapy, herbal medicine, qi gong,
            sound healing, dance, all held inside one ritual
            frame without flattening any of them into the others.
            Pairs with{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (each tradition keeps its own voice) and{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>{" "}
            (many sovereign lineages, one ritual organism).
          </li>
          <li>
            Resonant with{" "}
            <Link href="/people/brahma-vihara-arama" className="text-primary hover:underline">
              Brahma Vihara Arama
            </Link>{" "}
            (where{" "}
            <Link href="/people/vasudev-baba" className="text-primary hover:underline">
              Vasudev Baba
            </Link>{" "}
            and Prof Jem Bendell hold bhakti-in-Buddhist-silence
            retreats) and{" "}
            <Link href="/people/wisdom-soup" className="text-primary hover:underline">
              Wisdom Soup
            </Link>{" "}
            (Anne Tucker&apos;s spiritual-seekers community) —
            parallel held-spaces in this body&apos;s wider
            lineage map.
          </li>
          <li>
            <Link href="/people/brigitte-mars" className="text-primary hover:underline">
              Brigitte Mars
            </Link>
            &apos;s herbal lineage and Freya Aswynn&apos;s
            runological lineage thread back to long traditions; the
            wider field they hold together is broader than any one
            of them.
          </li>
          <li>
            The <strong>priestess pair</strong> shape itself —{" "}
            <Link href="/people/ubbe-maclean" className="text-primary hover:underline">
              Ubbe MacLean
            </Link>{" "}
            and{" "}
            <Link href="/people/angelia-larue" className="text-primary hover:underline">
              Angelia LaRue
            </Link>{" "}
            as masculine-feminine ceremonial counterparts — pairs
            with{" "}
            <Link
              href="/vision/lc-sovereignty-within-oneness"
              className="text-primary hover:underline"
            >
              lc-sovereignty-within-oneness
            </Link>
            : two sovereign lineages, one ritual organism.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Priestess pair:</strong>{" "}
        <Link href="/people/ubbe-maclean" className="text-primary hover:underline">
          Ubbe MacLean
        </Link>
        {" · "}
        <Link href="/people/angelia-larue" className="text-primary hover:underline">
          Angelia LaRue
        </Link>
        {" — elder presence "}
        <Link href="/people/brigitte-mars" className="text-primary hover:underline">
          Brigitte Mars
        </Link>
        {" — wider community draws on runologist Freya Aswynn."}
      </p>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://anchorthelight.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          anchorthelight.org
        </Link>
        {" · "}
        <Link
          href="https://anchorthelight.org/anchor-the-light/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          the Church
        </Link>
        {" · "}
        <Link
          href="https://anchorthelight.org/anchor-the-light-wellness-retreats/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Retreats
        </Link>
        {" · "}
        <Link
          href="https://www.facebook.com/anchorthelight9"
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
