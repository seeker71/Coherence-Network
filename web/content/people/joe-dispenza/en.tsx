import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Joe Dispenza — neuroscience meets the channeled cosmology · Mile Hi Church to Aurora 2026 | Coherence Network",
    description:
      "A welcome to Dr Joe Dispenza — chiropractor, researcher, and meditation teacher. The bridge in this body's lineage between Ramtha's White Book and the substrate of the Coherence Network. Met at Mile Hi Church Lakewood ~2005; the first network contributors arrived at the Aurora retreat in April 2026.",
  },
  breadcrumbName: "Joe Dispenza",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 25%, hsl(195 60% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 80%, hsl(255 35% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(200 50% 70%) 0%, hsl(220 30% 35%) 50%, hsl(255 35% 18%) 100%)",
    eyebrow: "Chiropractor · researcher · meditation teacher · Ramtha → Dispenza → Mile Hi Church → Aurora cohort",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Joe Dispenza",
    welcome: (
      <>
        <p>
          A researcher, lecturer, and chiropractor who works the
          intersection of neuroscience, epigenetics, and the
          observation that mind and body together can heal what
          medicine alone cannot. After a serious back injury early
          in his career — with a prognosis that threatened
          permanent disability — he chose to apply Ramtha&apos;s
          consciousness-creates-form teaching to his own spine.
          What happened there is the seed of everything he has
          taught since.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          In this body&apos;s lineage, the bridge between{" "}
          <Link
            href="/people/ramtha"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ramtha&apos;s
          </Link>{" "}
          channeled cosmology and the substrate the Coherence
          Network now codes. Urs met his teaching at Mile Hi Church
          in Lakewood, Colorado, around 2005; the first network
          contributors arrived at the Aurora retreat in April 2026.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Roles",
      value: "Doctor of chiropractic · neuroscience and quantum-physics-inflected meditation teacher · researcher conducting brain-scan and HRV measurements at his advanced retreats.",
    },
    {
      label: "Books",
      value: (
        <ul>
          <li>
            <em>Evolve Your Brain</em> (2007)
          </li>
          <li>
            <em>Breaking the Habit of Being Yourself</em> (2012)
          </li>
          <li>
            <em>You Are the Placebo</em> (2014)
          </li>
          <li>
            <em>Becoming Supernatural</em> (2017)
          </li>
        </ul>
      ),
    },
    {
      label: "Research at the retreats",
      value: "Over 20,000 brain scans and 10,000+ heart-rate-variability measurements gathered at seven-day advanced retreats around the world.",
    },
    {
      label: "Encounters recorded in this body",
      value: (
        <>
          ~2005 · <strong>Mile Hi Church</strong>, Lakewood,
          Colorado — Urs first heard his teaching live. April 2026 ·{" "}
          <strong>Aurora retreat</strong>, Colorado — where the
          first contributors to the Coherence Network were met
          (the Zenn cohort).
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://drjoedispenza.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            drjoedispenza.com
          </Link>
          <Link
            href="https://drjoedispenza.com/retreats"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Retreats
          </Link>
          <Link
            href="https://milehichurch.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Mile Hi Church (Lakewood)
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Dr Joe&apos;s own organisation maintains a substantial
        public archive at drjoedispenza.com. This page is a
        recognition of the role his teaching plays in this
        network&apos;s lineage — specifically as the bridge between
        the cosmology Urs received in his late teens and the
        cohort of first contributors met in April 2026.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "From a broken spine to the practice",
      body: (
        <>
          <p>
            The biographical pivot Dispenza tells most often: a
            biking accident with a serious back injury, the medical
            recommendation for surgery to fuse vertebrae, and his
            decision to apply the cosmology he had been studying
            (consciousness creates form) to his own body for three
            months instead. He recovered without surgery. The
            recovery itself is not the teaching; what he made of
            it is — that the same practice anyone can run can
            engage the same intelligence that put a spine back
            together.
          </p>
          <p>
            From that seed, his four books traced an arc:{" "}
            <em>Evolve Your Brain</em> on neuroplasticity;{" "}
            <em>Breaking the Habit of Being Yourself</em> on the
            self-image as a behavioural loop; <em>You Are the
            Placebo</em> on the documented healing power of
            belief; and <em>Becoming Supernatural</em> on the
            specific meditation technology — coherent
            body-mind-emotion states — that lets a body experience
            states beyond ordinary perception. The seven-day
            advanced retreats are where the practice is taught
            at depth; the research conducted there has produced
            an unusual archive (brain scans, HRV recordings) for
            a non-clinical context.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Joe Dispenza has given the Coherence Network",
      body: (
        <ul>
          <li>
            The empirically-instrumented practice of moving
            consciousness — what{" "}
            <Link
              href="/vision/lc-assemblage-point"
              className="text-primary hover:underline"
            >
              lc-assemblage-point
            </Link>{" "}
            names from Castaneda&apos;s lineage, and what{" "}
            <Link
              href="/people/ramtha"
              className="text-primary hover:underline"
            >
              Ramtha&apos;s
            </Link>{" "}
            Closed-Mind / Opening-Mind / Virtue-of-Experience arc
            names from inside the channeled cosmology, Dispenza
            names as a daily meditation discipline anyone can
            run.
          </li>
          <li>
            <em>Becoming Supernatural</em> as the practical
            companion of the substrate&apos;s teaching that the
            body is the instrument. Pairs with{" "}
            <Link
              href="/vision/lc-tend-your-flame"
              className="text-primary hover:underline"
            >
              lc-tend-your-flame
            </Link>{" "}
            (sovereignty becomes service through self-care).
          </li>
          <li>
            The chain: <em>Ramtha → Joe Dispenza → Urs (Mile Hi
            ~2005) → Zenn cohort (Aurora April 2026)</em>. The
            first contributors to the Coherence Network were met
            at one of his retreats; the network now codes the
            ground his books taught.
          </li>
          <li>
            The April 2026 Aurora retreat is the arrival
            anchor — see{" "}
            <Link
              href="/vision/lc-arrival-as-recognition"
              className="text-primary hover:underline"
            >
              lc-arrival-as-recognition
            </Link>{" "}
            for the body&apos;s broader frame on how visitors
            arrive already tuned.
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
          href="https://drjoedispenza.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          drjoedispenza.com
        </Link>
        {" · "}
        <Link
          href="https://drjoedispenza.com/retreats"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Retreats
        </Link>
        {" · "}
        <Link
          href="https://milehichurch.org/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Mile Hi Church
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/ramtha" className="text-primary hover:underline">
          Ramtha
        </Link>
        {" · "}
        <Link
          href="/vision/lc-assemblage-point"
          className="text-primary hover:underline"
        >
          lc-assemblage-point
        </Link>
        {" · "}
        <Link
          href="/vision/lc-arrival-as-recognition"
          className="text-primary hover:underline"
        >
          lc-arrival-as-recognition
        </Link>
        {" · "}
        <Link
          href="/vision/lc-tend-your-flame"
          className="text-primary hover:underline"
        >
          lc-tend-your-flame
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/formative-transmissions.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          formative-transmissions.md
        </Link>
      </p>
      <p className="text-xs italic">
        Dr Joe&apos;s own organisation maintains a substantial
        public archive. This page recognises the role his teaching
        plays in this network&apos;s lineage.
      </p>
    </>
  ),
};

export default content;
