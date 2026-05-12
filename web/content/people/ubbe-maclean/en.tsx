import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ubbe MacLean — Asatru, psychotherapist, reiki master, rune-healer at Anchor the Light | Coherence Network",
    description:
      "A welcome to Ubbe MacLean — practitioner of Asatru, clinically trained psychotherapist, life-enhancement coach, reiki master, author of Healing From the Tree: Using Runes for Emotional, Physical & Soul Healing. Holds the Anchor the Light Ceremony as priestess pair with Angelia LaRue; Brigitte Mars is the elder presence in the wider pagan rituals.",
  },
  breadcrumbName: "Ubbe MacLean",
  hero: {
    background:
      "radial-gradient(ellipse at 30% 25%, hsl(45 60% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 80% 80%, hsl(220 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(40 50% 60%) 0%, hsl(155 30% 35%) 50%, hsl(220 30% 18%) 100%)",
    eyebrow: "Asatru · psychotherapist · life-enhancement coach · reiki master · rune-healing author · priestess pair (with Angelia LaRue) at Anchor the Light",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Ubbe MacLean",
    welcome: (
      <>
        <p>
          Ubbe holds an unusually wide-banded vocabulary:
          practitioner of <strong>Asatru</strong> (the Norse
          heathen path), clinically trained{" "}
          <strong>psychotherapist</strong>, educator,
          life-enhancement coach, <strong>reiki master</strong>,
          and author of the rune-healing guidebook{" "}
          <em>
            Healing From the Tree: Using Runes for Emotional,
            Physical & Soul Healing
          </em>
          . Each surface is its own lineage; together they make
          the field he holds at{" "}
          <Link
            href="/people/anchor-the-light"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Anchor the Light
          </Link>
          , where he and{" "}
          <Link
            href="/people/angelia-larue"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Angelia LaRue
          </Link>{" "}
          hold the Ceremony as the priestess pair, with{" "}
          <Link
            href="/people/brigitte-mars"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Brigitte Mars
          </Link>{" "}
          as the elder presence in the wider pagan rituals.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The cross-walk between clinical psychotherapy and
          Asatru rune-work is rare — most carriers of either
          tradition stay inside it. Ubbe holds both lineages with
          their own integrity.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Practices held",
      value: "Asatru (Norse heathen path) · clinical psychotherapy · reiki (master) · runes (healing modality, author of Healing From the Tree) · life-enhancement coaching",
    },
    {
      label: "Where the work lives",
      value: (
        <>
          <Link
            href="/people/anchor-the-light"
            className="hover:text-primary transition-colors"
          >
            Anchor the Light
          </Link>{" "}
          — the living spiritual path; the Ceremony is held by
          Ubbe and{" "}
          <Link
            href="/people/angelia-larue"
            className="hover:text-primary transition-colors"
          >
            Angelia LaRue
          </Link>{" "}
          as priestess pair, with{" "}
          <Link
            href="/people/brigitte-mars"
            className="hover:text-primary transition-colors"
          >
            Brigitte Mars
          </Link>{" "}
          as elder presence in the pagan rituals; wider community
          draws on runologist Freya Aswynn
        </>
      ),
    },
    {
      label: "Personal offerings",
      value: "Life Enhancement Coaching · Mindfulness-Based Stress Reduction · Couples & Relationship Coaching · Reiki · Equine Healing Sessions · Personal Clearings · Rune Reading · Fitness Training",
    },
    {
      label: "Book",
      value: (
        <>
          <em>
            Healing From the Tree: Using Runes for Emotional,
            Physical & Soul Healing
          </em>{" "}
          — working manual threading runes with herbal and
          emotional healing register.{" "}
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
            href="https://www.instagram.com/ubbemaclean/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Instagram @ubbemaclean
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
        This page was first deleted as auto-harvest noise during a
        graph-dedup pass — Ubbe MacLean looked like a placeholder
        without lineage research. Urs named the real ground and
        the page returns substantively, now grounded in the
        anchorthelight.org public record. Ubbe is invited to
        replace any line with his own words.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The plural-lineage frame",
      body: (
        <p>
          The Anchor the Light frame describes itself as{" "}
          <em>
            a living spiritual path rooted in direct encounter
            with the Divine through music, movement, and embodied
            awareness
          </em>
          . The invitation: <em>Enter the Ritual. Become the
          Experience.</em> Monthly wellness retreats weave Qi
          Gong, mindfulness meditation, acupuncture, sound
          bathing, biofeedback, Reiki, energy healing, forest
          bathing, plant medicines, life-enhancement skill
          building, fully organic meals, visionary art, and dance
          into one container. The community-side of the work
          shows up in pagan ritual gatherings, monthly retreats,
          and free guided meditations on the Anchor the Light
          YouTube channel.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Ubbe MacLean has given the Coherence Network",
      body: (
        <ul>
          <li>
            A working example of the{" "}
            <em>plural-lineage tender</em> — clinically-credentialled
            psychotherapy held inside an Asatru and Reiki frame,
            all rendered as one consistent practice rather than
            as parallel costumes. Pairs with{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (each lineage keeps its voice; no forced
            reconciliation).
          </li>
          <li>
            The shape resonates with{" "}
            <Link href="/people/vasudev-baba" className="text-primary hover:underline">
              Vasudev Baba
            </Link>{" "}
            (bhakti kirtan crossing into Buddhist silence at
            Brahma Vihara) and{" "}
            <Link href="/people/ilena-young" className="text-primary hover:underline">
              Ilena Young
            </Link>{" "}
            (Australian regional development bridged into
            Indonesian wellness) — three cells whose contemporary
            work synthesises across traditions that the broader
            culture keeps separate.
          </li>
          <li>
            <em>
              Direct encounter with the Divine through music,
              movement, and embodied awareness
            </em>{" "}
            is a felt-ground sibling of{" "}
            <Link href="/people/gabrielle-roth" className="text-primary hover:underline">
              Gabrielle Roth
            </Link>
            &apos;s wave-map teaching at the body level.
          </li>
          <li>
            Rune-work as a healing modality joins the body&apos;s
            broader{" "}
            <Link
              href="/vision/lc-bioelectric-pattern"
              className="text-primary hover:underline"
            >
              lc-bioelectric-pattern
            </Link>{" "}
            frame (pattern as load-bearing) from the
            symbolic-language side.
          </li>
        </ul>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Where the work lives:</strong>{" "}
        <Link href="/people/anchor-the-light" className="text-primary hover:underline">
          Anchor the Light
        </Link>{" "}
        — Ceremony held with{" "}
        <Link href="/people/angelia-larue" className="text-primary hover:underline">
          Angelia LaRue
        </Link>{" "}
        as priestess pair;{" "}
        <Link href="/people/brigitte-mars" className="text-primary hover:underline">
          Brigitte Mars
        </Link>{" "}
        as elder presence; wider community draws on runologist
        Freya Aswynn.
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
          href="https://www.instagram.com/ubbemaclean/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Instagram
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
        {" · "}
        <Link
          href="https://anchorthelight.org/healing-from-the-tree-using-runes-for-emotional-physical-soul-healing/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Healing from the Tree (book)
        </Link>
      </p>
    </>
  ),
};

export default content;
