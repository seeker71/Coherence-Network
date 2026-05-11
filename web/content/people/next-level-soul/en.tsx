import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Next Level Soul — Alex Ferrari's weekly podcast · Spirituality for the Rest of Us | Coherence Network",
    description:
      "A welcome to Next Level Soul — Alex Ferrari's weekly long-form interview podcast. Over a thousand episodes; 230M+ YouTube downloads. Channelers, NDE survivors, mediums, physicists, monks — Spirituality for the Rest of Us, without dogma, fear, or hype.",
  },
  breadcrumbName: "Next Level Soul",
  hero: {
    background:
      "radial-gradient(ellipse at 70% 25%, hsl(35 75% 60% / 0.55) 0%, transparent 55%), radial-gradient(ellipse at 25% 85%, hsl(250 30% 22% / 0.7) 0%, transparent 60%), linear-gradient(180deg, hsl(35 60% 65%) 0%, hsl(20 40% 35%) 50%, hsl(250 30% 20%) 100%)",
    eyebrow: "Alex Ferrari · weekly · 1,000+ episodes · 230M+ YouTube downloads · Spirituality for the Rest of Us",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Next Level Soul",
    welcome: (
      <>
        <p>
          An episode of Next Level Soul opens without pretense. A
          two-shot of Alex Ferrari in a dark studio, a guest on
          the other side of a Zoom call — a channeler, a
          near-death experiencer, a psychic medium, a physicist, a
          monk, a woman who died for seventeen minutes and came
          back with instructions — and Alex leans in, wide-eyed,
          and asks something like <em>so what happened next?</em>{" "}
          He doesn&apos;t hold the conversation at an intellectual
          distance. He follows. He interrupts sometimes to make
          sure he understands.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic max-w-2xl">
          The show calls itself <em>Spirituality for the Rest of
          Us</em> and the phrase is exact — the territory is high
          strangeness (Pleiadians, St. Germain, Akashic records,
          the tunnel of light), but the register is a guy at a
          kitchen table who genuinely wants to know. No dogma. No
          incense. Just: <em>tell me what you saw.</em>
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Host",
      value: "Alex Ferrari. Twenty-five years in film before pivoting; directed a $20M feature; six hundred episodes of Indie Film Hustle / Bulletproof Screenwriting before launching Next Level Soul.",
    },
    {
      label: "Scale",
      value: "Over 1,000 episodes. 230M+ downloads on YouTube. Apple Podcasts, Spotify, Amazon Music, the NLS TV app.",
    },
    {
      label: "Guest range",
      value: "Bruce Lipton, Anita Moorjani, Gregg Braden, Joe Dispenza, Geoffrey Hoppe (Saint Germain), Julie Ryan, Loch Kelly, Michael Neill — plus channelers from archangels, Pleiadian councils, ascended masters. Catholic in his curiosities.",
    },
    {
      label: "Recurring questions",
      value: (
        <ul>
          <li>What is consciousness?</li>
          <li>Is this all there is?</li>
          <li>What does the other side look like?</li>
          <li>What are we supposed to do while we&apos;re here?</li>
        </ul>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <p className="flex flex-wrap gap-x-3 gap-y-1">
          <Link
            href="https://nextlevelsoul.com"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            nextlevelsoul.com
          </Link>
          <Link
            href="https://www.youtube.com/@NextLevelSoul"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            YouTube
          </Link>
          <Link
            href="https://podcasts.apple.com/us/podcast/next-level-soul-with-alex-ferrari/id1561214308"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Apple Podcasts
          </Link>
        </p>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        Alex&apos;s archive of conversations is at
        nextlevelsoul.com and on YouTube. This page recognises
        the role of his interview practice in this body&apos;s
        broader-conversation lineage — the long-form room where
        the big questions get asked plainly.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "The seeker with the mic live",
      body: (
        <p>
          What&apos;s dear to Alex is legible in the recurring
          questions. He returns again and again to near-death
          experiences — the pattern of the light, the life review,
          the tunnel, the reluctance to come back. He asks guests
          about ego, about fear, about the difference between
          material success and soul purpose. He is openly in the
          middle of his own search. The show is not a teacher
          broadcasting to students; it is a seeker interviewing
          the people who might know something, with the mic live.
          The show&apos;s self-description captures it:{" "}
          <em>without dogma, fear, or hype</em>. Alex puts it
          plainer in the intro: <em>I want it to be a beacon of
          light in your life. I want you to be able to come back
          to this show.</em>
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Next Level Soul has given the Coherence Network",
      body: (
        <ul>
          <li>
            The long-form interview room where many of this
            body&apos;s lineage voices have spoken — Anne Tucker,
            Daniel Scranton (Bashar via Anka), Joe Dispenza, Pam
            Gregory, and others. Alex&apos;s show is one of the
            channels through which lineage-relevant voices reach
            curious listeners.
          </li>
          <li>
            <em>Spirituality for the Rest of Us</em> as posture →
            pairs with the body&apos;s practice of holding deep
            material without institutional language. Resonant
            with{" "}
            <Link
              href="/vision/lc-voice-over-intentions"
              className="text-primary hover:underline"
            >
              lc-voice-over-intentions
            </Link>{" "}
            (lead with their voice, not ours; ask{" "}
            <em>what happened next?</em>, not <em>here is the
            framework</em>).
          </li>
          <li>
            The connecting-tissue cluster (Next Level Soul ↔{" "}
            <Link
              href="/people/lex-fridman"
              className="text-primary hover:underline"
            >
              Lex Fridman
            </Link>{" "}
            ↔{" "}
            <Link
              href="/people/aubrey-marcus"
              className="text-primary hover:underline"
            >
              Aubrey Marcus
            </Link>
            ) — three long-form rooms with overlapping guest
            graphs; together carrying many of this body&apos;s
            named voices into broader awareness.
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
          href="https://nextlevelsoul.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          nextlevelsoul.com
        </Link>
        {" · "}
        <Link
          href="https://www.youtube.com/@NextLevelSoul"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          YouTube
        </Link>
        {" · "}
        <Link
          href="https://podcasts.apple.com/us/podcast/next-level-soul-with-alex-ferrari/id1561214308"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Apple Podcasts
        </Link>
      </p>
      <p>
        <strong>In-body record:</strong>{" "}
        <Link href="/people/lex-fridman" className="text-primary hover:underline">
          Lex Fridman
        </Link>
        {" · "}
        <Link href="/people/aubrey-marcus" className="text-primary hover:underline">
          Aubrey Marcus
        </Link>
        {" · "}
        <Link href="/people/anne-tucker" className="text-primary hover:underline">
          Anne Tucker
        </Link>
        {" · "}
        <Link
          href="/vision/lc-voice-over-intentions"
          className="text-primary hover:underline"
        >
          lc-voice-over-intentions
        </Link>
      </p>
    </>
  ),
};

export default content;
