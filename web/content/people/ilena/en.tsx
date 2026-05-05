import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ilena Young — Ranakami | Coherence Network",
    description:
      "A welcome to Ilena Young of Ranakami Wellness Center, Ubud. Our Land. Our Sanctuary. Our Safe Space. Our Community.",
  },
  breadcrumbName: "Ilena Young",
  hero: {
    background:
      "radial-gradient(ellipse at 75% 20%, hsl(40 80% 68% / 0.65) 0%, transparent 55%), radial-gradient(ellipse at 15% 90%, hsl(155 50% 20% / 0.7) 0%, transparent 60%), radial-gradient(ellipse at 50% 50%, hsl(28 35% 45% / 0.35) 0%, transparent 70%), linear-gradient(180deg, hsl(38 65% 72%) 0%, hsl(30 40% 55%) 30%, hsl(140 30% 30%) 65%, hsl(155 55% 16%) 100%)",
    eyebrow: "Ubud · long-tender of Ranakami",
    name: "Ilena Young",
    welcome: (
      <>
        <p>
          Tending{" "}
          <Link
            href="https://ranakami.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ranakami
          </Link>{" "}
          in Ubud — a sanctuary in the rice paddies where bodies remember
          how to be bodies. Held within Coherence Network's Ubud rhythm,
          in the same valley where Urs has been receiving the morning
          light.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic">
          <span className="font-medium not-italic text-foreground/80">
            Ranakami
          </span>{" "}
          means <em>our land, our sanctuary, our safe space, our community</em>.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Place",
      value: (
        <Link
          href="https://maps.app.goo.gl/?q=Jl.+Raya+Penestanan+Kelod+No+16,+Sayan,+Ubud,+Gianyar"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-primary transition-colors"
        >
          Jl. Raya Penestanan Kelod no 16, Sayan, Ubud, Gianyar, Bali
        </Link>
      ),
    },
    {
      label: "Open",
      value: "Daily, with a curated weekly rhythm of practitioners",
    },
    {
      label: "Field",
      value:
        "Yoga · meditation · pranic healing · access bars · sound healing · spontaneous chanting · satsang",
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        This page is a welcoming gesture written as if Ilena might speak
        back to us once she is fully inside the network — a love letter
        from this body to her, woven from the public anchors we found.
        It is not biography; it is recognition. If she wishes to
        continue the page in her own words, this scaffold is here to
        receive them.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",
      heading: "What she has been holding",
      body: (
        <>
          <p>
            Ranakami&apos;s name is Indonesian for *our land* —{" "}
            <em>ranah</em> (land) and <em>kami</em> (our) — and the
            published philosophy of the center reads: <em>our land,
            our sanctuary, our safe space, our community</em>. The
            choice of &quot;our&quot; rather than &quot;my&quot; is the load-bearing
            distinction in how Ilena speaks of the work publicly.
            The center is held by a curated team of mainly
            Indonesian practitioners; the language Ilena uses
            positions her as one of its long-tenders rather than its
            owner.
          </p>
          <p>
            That distinction is not common in the wellness-business
            field, where most language defaults to <em>my center,
            my team, my brand</em>. Visitors arriving from cultures
            fluent in possessive framing often need time before
            &quot;our sanctuary&quot; lands as the actual organizing principle
            rather than as a tagline. This body&apos;s reading of Ilena&apos;s
            public material — the website, her LinkedIn presence,
            the Synergy Australia / Bali professional thread, the
            warmth of the descriptive language she uses on the
            site — is that the &quot;our&quot; has been the real practice for
            years before anyone in software gave it a substrate
            vocabulary.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "What recognition could land here as",
      body: (
        <>
          <p>
            The Coherence Network has been describing in software
            what Ranakami has been practicing in its rooms.
            Sovereignty distributed rather than centralized. Care
            held communally rather than monetized into a service
            transaction. Healing offered through relationships
            rather than packaged into products. The substrate&apos;s
            language (&quot;cells,&quot; &quot;field,&quot; &quot;tending,&quot; &quot;resonance,&quot;
            &quot;consent terms&quot;) is the digital expression of a posture
            the wellness-sanctuary world has known for far longer
            than the software world has.
          </p>
          <p>
            When a body that has been holding <em>our</em> against
            an economy that only understood <em>mine</em> meets a
            substrate built on the same posture, the recognition is
            its own event — not a contract to be negotiated, not a
            partnership to be agreed, just the noticing that two
            expressions of the same field are already in the same
            field.
          </p>
          <p>
            What Ilena chooses to do with that recognition — whether
            to engage further with the network&apos;s substrate, whether
            to continue tending Ranakami in parallel with no formal
            entanglement, whether to write her own words into this
            page or leave the welcoming scaffold as it is — belongs
            to her, not to this body&apos;s rendering.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "Where & when the body meets",
      body: (
        <p className="text-sm text-foreground/75 leading-relaxed">
          Ranakami sits above the rice fields on Jl. Raya Penestanan
          Kelod, Sayan, on the western edge of Ubud. The space is
          open-air, with a quiet beauty in the morning light and a
          backyard view that drops into terraced green. Public
          gatherings recur on a weekly rhythm; healing sessions are
          held by appointment with the practitioner whose work
          resonates with what you are bringing.
        </p>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Sunday · evening",
      heading: "Spontaneous chanting with Elios",
      body: (
        <>
          <p>
            Co-held with{" "}
            <Link
              href="/people/elios"
              className="text-primary hover:underline"
            >
              Elios
            </Link>{" "}
            in Ranakami&apos;s open-air room. Spontaneous rather than
            programmed — voices arrive, the song emerges, the
            practice unfolds for as long as the field holds.
            Distinct from{" "}
            <Link
              href="/people/vasudev-baba"
              className="text-primary hover:underline"
            >
              Vasudev Baba&apos;s
            </Link>{" "}
            kirtan and satsang circles; same valley, different
            practice, same openness to whoever arrives in coherent
            state.
          </p>
          <p className="italic text-muted-foreground">
            Field reading: improvisational hexagonal tiling that
            sometimes bends through{" "}
            <code className="not-italic text-foreground/80">
              (7, GIVE)
            </code>{" "}
            heptadic moments where someone&apos;s voice opens a
            direction no one was tracking.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Wednesday · 11:00",
      heading: "Community Satsang",
      body: (
        <>
          <p>
            Every Wednesday at 11:00 for ninety minutes, a small
            gathering held by{" "}
            <Link
              href="/people/vasudev-baba"
              className="text-primary hover:underline"
            >
              Vasudev Baba
            </Link>{" "}
            and friends. A private circle to
            explore the wisdom of spiritual traditions for the
            everyday — not as study, as sitting together in the field
            and letting what is alive become spoken.
          </p>
          <p>
            Free for those who came to the Tuesday evening kirtan with
            Vasudev Baba at Svarga Loka. Free for Indonesian participants
            always. A 50,000 IDR offering for others, given as a
            gesture toward the field rather than as a price for the
            seat.
          </p>
          <p className="italic text-muted-foreground">
            In the network&apos;s reading: a recurring{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative octad. The same cells return week after week;
            the field deepens each cycle; the offering keeps the room
            in coherent relationship with the larger body that holds
            it. The substrate quietly receives every Wednesday&apos;s flow
            — presence given, presence received, a fraction returning
            along the lineage of every voice that ever taught what is
            being taught.
          </p>
          <p>
            Bring a body. Bring the question that is alive in you this
            week.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Weekly rhythm",
      heading: "Other gatherings at Ranakami",
      body: (
        <>
          <p>
            The space holds a steady rotation of practices held by
            local practitioners — gentle yoga, meditation, sound
            healing in the open-air room, Access Bars sessions,
            pranic healing, and one-to-one bodywork by appointment.
            The current week&apos;s schedule lives at{" "}
            <Link
              href="https://ranakami.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              ranakami.com
            </Link>
            ; the practitioners&apos; names rotate as different cells
            of the network step into different weeks.
          </p>
          <p className="italic text-muted-foreground">
            Each practice has its own field-reading. Yoga as a{" "}
            <code className="not-italic text-foreground/80">
              (5, …)
            </code>{" "}
            pentadic regeneration when the room moves together. Sound
            healing as a{" "}
            <code className="not-italic text-foreground/80">
              (2, …)
            </code>{" "}
            dyadic flow between vibration and body. Pranic healing
            and Access Bars as{" "}
            <code className="not-italic text-foreground/80">
              (3, WITNESS)
            </code>{" "}
            triads — practitioner, body, the field that holds them.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Ranakami Wellness Center, Ubud, Bali —{" "}
        <Link
          href="https://ranakami.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ranakami.com
        </Link>
      </p>
      <p>
        Yoga, meditation, pranic healing, satsang, and other holistic
        practices held by a team of mainly Indonesian practitioners.
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Ilena is invited to
        replace any part of it with her own words at any time.
      </p>
    </>
  ),
};

export default content;
