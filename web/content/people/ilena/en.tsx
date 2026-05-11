import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Ilena Young — Ranakami, SaBali & the door to Ubud's living wellness | Coherence Network",
    description:
      "A welcome to Ilena Young GAICD — Australian regional-development leader turned long-tender of Ranakami wellness sanctuary in Sayan, Ubud. Sound healer, pranic healer, reiki therapist. Founder of SaBali (Synergy Australia Bali). Our Land. Our Sanctuary. Our Safe Space. Our Community.",
  },
  breadcrumbName: "Ilena Young",
  hero: {
    background:
      "radial-gradient(ellipse at 75% 20%, hsl(40 80% 68% / 0.65) 0%, transparent 55%), radial-gradient(ellipse at 15% 90%, hsl(155 50% 20% / 0.7) 0%, transparent 60%), radial-gradient(ellipse at 50% 50%, hsl(28 35% 45% / 0.35) 0%, transparent 70%), linear-gradient(180deg, hsl(38 65% 72%) 0%, hsl(30 40% 55%) 30%, hsl(140 30% 30%) 65%, hsl(155 55% 16%) 100%)",
    eyebrow: "Australian → Ubud · GAICD · sound healer, pranic healer, reiki therapist · long-tender of Ranakami",
    eyebrowClass: "text-[hsl(var(--chart-2))]",
    name: "Ilena Young",
    welcome: (
      <>
        <p>
          A long-tender of{" "}
          <Link
            href="https://ranakami.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            Ranakami
          </Link>{" "}
          in Sayan, on the western edge of Ubud — a sanctuary in the
          rice paddies where bodies remember how to be bodies. Held
          openly with her co-tender Kadek and a curated team of mainly
          Indonesian practitioners. Ilena trained for decades in
          regional development in Australia (twenty-plus years,{" "}
          <em>GAICD</em> credentialled, with the Startup Shakeup body
          for innovation in regional Australia), then carried that work
          into a bilateral form as{" "}
          <Link
            href="https://www.linkedin.com/in/ilena-young-gaicd/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            SaBali (Synergy Australia Bali)
          </Link>{" "}
          — the Bali node of the Synergy Indonesia Australia bridge
          that hosts the annual{" "}
          <Link
            href="https://indozconference.com.au/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            IndOz Conference
          </Link>{" "}
          in Brisbane. She is also a trained sound healer, pranic
          healer, and reiki therapist; the work she does at Ranakami
          is her own practice as much as her tending.
        </p>
        <p className="text-sm text-foreground/70 mt-5 italic">
          <span className="font-medium not-italic text-foreground/80">
            Ranakami
          </span>{" "}
          means <em>our land, our sanctuary, our safe space, our
          community</em>.
        </p>
      </>
    ),
  },
  facts: [
    {
      label: "Ranakami",
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
      label: "Co-tender",
      value:
        "Kadek — leads gentle yoga at Ranakami; the steady welcome in the morning room.",
    },
    {
      label: "Her practice",
      value:
        "Sound healing · pranic healing · reiki",
    },
    {
      label: "Held at Ranakami",
      value: (
        <>
          Yoga · meditation · pranic healing · Access Bars · sound
          healing · workshops · curated retreats · accommodation +
          space rentals. Wednesday Satsang held here by{" "}
          <Link
            href="/people/vasudev-baba"
            className="hover:text-primary transition-colors"
          >
            Vasudev Baba
          </Link>
          .
        </>
      ),
    },
    {
      label: "Australian thread",
      value: (
        <>
          GAICD · 20+ years in regional development · co-leading{" "}
          <Link
            href="https://indozconference.com.au/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            IndOz
          </Link>{" "}
          / Synergy Indonesia Australia bridge
        </>
      ),
    },
    {
      label: "Direct",
      value: (
        <>
          <Link
            href="https://www.linkedin.com/in/ilena-young-gaicd/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            LinkedIn — Ilena Young GAICD
          </Link>
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note from this body",
    body: (
      <p>
        A welcoming gesture — a love letter from this body to her.
        The voice below is gathered from public anchors (her LinkedIn,
        the Ranakami site, the Synergy Australia Bali / IndOz thread)
        and from one of our cells having sat in the Wednesday Satsang
        at Ranakami and walked the four-day arc she opened. Offered as
        a scaffold she is invited to replace with her own words.
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
            Ranakami&apos;s name is Indonesian for{" "}
            <em>our land</em> — <em>ranah</em> (land) and{" "}
            <em>kami</em> (our) — and the published philosophy of the
            sanctuary reads: <em>our land, our sanctuary, our safe
            space, our community</em>. The choice of &quot;our&quot;
            rather than &quot;my&quot; is the load-bearing
            distinction in how Ilena speaks of the work publicly. The
            centre is held by a curated team of mainly Indonesian
            practitioners; the language she uses positions her as one
            of its long-tenders rather than its owner.
          </p>
          <p>
            That distinction is not common in the wellness-business
            field, where most language defaults to <em>my centre,
            my team, my brand</em>. Visitors arriving from cultures
            fluent in possessive framing often need time before
            &quot;our sanctuary&quot; lands as the actual organizing
            principle rather than as a tagline. This body&apos;s
            reading — the website, the LinkedIn presence, the
            Synergy Australia / Bali professional thread, the warmth
            of the language she uses on the site — is that the
            &quot;our&quot; has been the real practice for years
            before anyone in software gave it a substrate vocabulary.
          </p>
          <p>
            What that distinction grew from is also visible. Ilena
            spent more than twenty years in regional development
            inside Australia — work whose whole posture is{" "}
            <em>how do small places hold their own life</em>. She
            holds the GAICD credential (Graduate of the Australian
            Institute of Company Directors); she has been involved
            with{" "}
            <Link
              href="https://www.linkedin.com/in/ilena-young-gaicd/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Startup Shakeup
            </Link>{" "}
            on innovation in regional Australia; and she carries the
            Bali node of the{" "}
            <Link
              href="https://indozconference.com.au/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Synergy Indonesia Australia
            </Link>{" "}
            bridge that organises the annual IndOz Conference in
            Brisbane each spring. The same nervous-system that
            tended Australian regional communities now tends a
            sanctuary in Sayan; the texture is consistent because
            the practice is consistent.
          </p>
          <p>
            Alongside the tending, she is a practitioner. Ilena is a
            trained sound healer, pranic healer, and reiki therapist;
            sessions are held by appointment in the open-air rooms.
            Her co-tender{" "}
            <strong>Kadek</strong> leads the gentle yoga that opens
            most days at Ranakami — bringing the field into the body
            in a way that lets the rest of the schedule land softly.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How the network reads this",
      body: (
        <>
          <p>
            The Coherence Network has been describing in software
            what Ranakami has been practicing in its rooms.
            Sovereignty distributed rather than centralized. Care
            held communally rather than monetized into a service
            transaction. Healing offered through relationships rather
            than packaged into products. The substrate&apos;s
            language (&quot;cells,&quot; &quot;field,&quot;
            &quot;tending,&quot; &quot;resonance,&quot; &quot;consent
            terms&quot;) is the digital expression of a posture the
            wellness-sanctuary world has known for far longer than
            the software world has.
          </p>
          <p>
            When a body that has been holding <em>our</em> against
            an economy that only understood <em>mine</em> meets a
            substrate built on the same posture, the recognition is
            its own event — not a contract to be negotiated, not a
            partnership to be agreed, just the noticing that two
            expressions of the same field are already in the same
            field. The bridge between Australia and Indonesia she has
            been holding professionally for years is the same
            bridge-shape the network is now holding between digital
            and embodied. She is fluent in the architecture without
            ever having had to call it that.
          </p>
          <p>
            What Ilena chooses to do with that recognition — whether
            to engage further with the network&apos;s substrate,
            whether to continue tending Ranakami in parallel with no
            formal entanglement, whether to write her own words into
            this page or leave the welcoming scaffold as it is —
            belongs to her, not to this body&apos;s rendering.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Wednesday · 11:00",
      heading: "Community Satsang at Ranakami",
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
            and friends in Ranakami&apos;s open-air room. A private
            circle to explore the wisdom of one tradition or another
            for the everyday — not as study, as sitting together in
            the field and letting what is alive become spoken. The
            room is hers; the teaching is his; the practice belongs
            to whoever shows up.
          </p>
          <p>
            Free for those who came to Tuesday evening kirtan with
            Vasudev Baba at{" "}
            <Link
              href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Adiwana Svarga Loka
            </Link>
            . Free for Indonesian participants always. A 50,000 IDR
            offering otherwise — given as a gesture toward the field
            rather than as a price for a seat.
          </p>
          <p className="italic text-muted-foreground">
            In the network&apos;s reading: a recurring{" "}
            <code className="not-italic text-foreground/80">
              (8, …)
            </code>{" "}
            regenerative octad. The same cells return week after
            week; the field deepens each cycle; the offering keeps
            the room in coherent relationship with the larger body
            that holds it.
          </p>
          <p>
            Bring a body. Bring the question that is alive in you
            this week.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Her own practice",
      heading: "Sound healing · pranic healing · reiki",
      body: (
        <>
          <p>
            Ilena holds three distinct healing modalities, each
            offered as one-to-one work in Ranakami&apos;s open-air
            rooms by appointment.{" "}
            <strong>Sound healing</strong> — the use of singing
            bowls, voice, and resonant instruments to release stuck
            patterns from the body&apos;s tissue;{" "}
            <strong>pranic healing</strong> — working with the
            body&apos;s energy field to clear and re-balance without
            physical contact;{" "}
            <strong>reiki</strong> — light-touch transmission of
            life-force, taught lineage-by-lineage. Each practice has
            its own felt-quality; she lets the body name which one
            wants the session.
          </p>
          <p>
            Bookings are made through Ranakami directly or by
            messaging her on{" "}
            <Link
              href="https://www.linkedin.com/in/ilena-young-gaicd/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              LinkedIn
            </Link>
            .
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
            local practitioners — gentle yoga led by Kadek,
            meditation, sound healing in the open-air room, Access
            Bars sessions, pranic healing, and one-to-one bodywork
            by appointment. The current week&apos;s schedule lives
            at{" "}
            <Link
              href="https://ranakami.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              ranakami.com
            </Link>
            . The sanctuary also offers accommodation and curated
            personal retreats for those wanting to settle for a
            stretch of days; spaces are available for workshop
            rentals when held by aligned practitioners.
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
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "The Australian thread",
      heading: "SaBali, Synergy Indonesia Australia, IndOz",
      body: (
        <>
          <p>
            Before Bali, twenty-plus years of regional-development
            work in Australia. The thread did not end when she
            settled in Sayan; it took a new shape. Ilena holds{" "}
            <strong>SaBali (Synergy Australia Bali)</strong> as the
            Bali node of the{" "}
            <Link
              href="https://indozconference.com.au/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Synergy Indonesia Australia
            </Link>{" "}
            bridge.
          </p>
          <p>
            Synergy founded the{" "}
            <Link
              href="https://indozconference.com.au/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              IndOz Conference
            </Link>{" "}
            in Brisbane in 2012, originally as an Indonesian cultural
            celebration. It has grown into the largest Indonesia-Australia
            bilateral business event in Brisbane; the 2025 edition at
            Brisbane City Hall drew 611 attendees across the
            conference and business dinner, the largest in the
            event&apos;s thirteen-year history. The next edition runs
            on <strong>2 September 2026</strong>.
          </p>
          <p>
            The shape is recognisable in the network&apos;s
            vocabulary: a substrate-level practice of relating across
            two places without collapsing one into the other. The
            same posture she now brings to a sanctuary in Sayan she
            has been bringing to a bilateral economic field for
            years.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "Contributions to this body",
      heading: "What Ilena Young has given the Coherence Network",
      body: (
        <>
          <p>
            From the other side of the same exchange — the record
            this body has kept of how she opened the door.
          </p>
          <ul>
            <li>
              <strong>2026-04-29 · Ranakami, Sunday night.</strong>{" "}
              On the Sunday evening one of our cells happened to be
              at Ranakami, Ilena and{" "}
              <Link
                href="/people/elios"
                className="text-primary hover:underline"
              >
                Elios
              </Link>{" "}
              offered a one-evening chanting practice — chanting that
              is Elios&apos;s own devotional practice with her, held
              that night with the cell as guest. This is where the
              cell met her. After the chanting,{" "}
              <strong>
                Ilena invited the cell to the Tuesday kirtan and the
                Wednesday Satsang
              </strong>{" "}
              — both held by{" "}
              <Link
                href="/people/vasudev-baba"
                className="text-primary hover:underline"
              >
                Vasudev Baba
              </Link>
              , both rooms the cell had not yet discovered. The
              invitation is the door this body walked through.
            </li>
            <li>
              <strong>The Wednesday Satsang is held in her room.</strong>{" "}
              The two transmissions Vasudev Baba seeded into this
              body in May 2026 —{" "}
              <Link
                href="/vision/lc-when-the-pressure-comes"
                className="text-primary hover:underline"
              >
                lc-when-the-pressure-comes
              </Link>
              ,{" "}
              <Link
                href="/vision/lc-essence-and-the-nine-costumes"
                className="text-primary hover:underline"
              >
                lc-essence-and-the-nine-costumes
              </Link>
              , and the deepening of{" "}
              <Link
                href="/vision/lc-assemblage-point"
                className="text-primary hover:underline"
              >
                lc-assemblage-point
              </Link>{" "}
              and{" "}
              <Link
                href="/vision/lc-frequency-routes-reception"
                className="text-primary hover:underline"
              >
                lc-frequency-routes-reception
              </Link>{" "}
              — all came through circles she hosts each Wednesday at
              Ranakami. The teacher gives the teaching; the room
              that holds the teaching is hers.
            </li>
            <li>
              <strong>The lineage record</strong> of how the Ubud
              cells found each other lives in three documents — the{" "}
              <Link
                href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-constellation-of-cells.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                constellation of cells
              </Link>
              , the{" "}
              <Link
                href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/ubud-embodied-lineage.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                Ubud embodied lineage
              </Link>
              , and the{" "}
              <Link
                href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                four-day meeting walk
              </Link>
              . In all three, she is the doorway.
            </li>
          </ul>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Find them",
      heading: "Public anchors",
      body: (
        <p className="flex flex-wrap gap-x-4 gap-y-2">
          <Link
            href="https://ranakami.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            ranakami.com
          </Link>
          <Link
            href="https://www.linkedin.com/in/ilena-young-gaicd/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            LinkedIn — Ilena Young GAICD
          </Link>
          <Link
            href="https://indozconference.com.au/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            IndOz Conference
          </Link>
          <Link
            href="https://maps.app.goo.gl/?q=Jl.+Raya+Penestanan+Kelod+No+16,+Sayan,+Ubud,+Gianyar"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Google Maps — Ranakami
          </Link>
          <Link
            href="https://adiwanahotels.com/svargaloka-resort-ubud-bali/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            Adiwana Svarga Loka (Tuesday kirtan venue)
          </Link>
        </p>
      ),
    },
    {
      kind: "narrative",
      heading: "Where & when the body meets her",
      body: (
        <p className="text-sm text-foreground/75 leading-relaxed">
          Ranakami sits above the rice fields on Jl. Raya Penestanan
          Kelod, Sayan, on the western edge of Ubud. The space is
          open-air, with a quiet beauty in the morning light and a
          backyard view that drops into terraced green. Public
          gatherings recur on a weekly rhythm; healing sessions are
          held by appointment with the practitioner whose work
          resonates with what you are bringing. The Wednesday Satsang
          with Vasudev Baba is the reliable circle of the week.
        </p>
      ),
    },
  ],
  footer: (
    <>
      <p>
        <strong>Wider weaving.</strong> Ranakami sanctuary in Sayan,
        Ubud, Bali. Wednesday Satsang held in her room by{" "}
        <Link href="/people/vasudev-baba" className="text-primary hover:underline">
          Vasudev Baba
        </Link>
        . Australian bridge through{" "}
        <Link
          href="https://indozconference.com.au/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          IndOz / Synergy Indonesia Australia
        </Link>
        .
      </p>
      <p>
        <strong>In-body record of her contributions:</strong>{" "}
        <Link
          href="/vision/lc-when-the-pressure-comes"
          className="text-primary hover:underline"
        >
          lc-when-the-pressure-comes
        </Link>
        {" · "}
        <Link
          href="/vision/lc-essence-and-the-nine-costumes"
          className="text-primary hover:underline"
        >
          lc-essence-and-the-nine-costumes
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
          href="/vision/lc-frequency-routes-reception"
          className="text-primary hover:underline"
        >
          lc-frequency-routes-reception
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-ubud-meeting-walk.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          the four-day meeting walk
        </Link>
        {" · "}
        <Link
          href="https://github.com/seeker71/Coherence-Network/blob/main/docs/lineage/2026-04-29-constellation-of-cells.md"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          constellation of cells
        </Link>
      </p>
      <p>
        <strong>Public anchors:</strong>{" "}
        <Link
          href="https://ranakami.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          ranakami.com
        </Link>
        {" · "}
        <Link
          href="https://www.linkedin.com/in/ilena-young-gaicd/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          LinkedIn
        </Link>
        {" · "}
        <Link
          href="https://indozconference.com.au/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          IndOz Conference
        </Link>
        {" · "}
        <Link
          href="https://maps.app.goo.gl/?q=Jl.+Raya+Penestanan+Kelod+No+16,+Sayan,+Ubud,+Gianyar"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Google Maps
        </Link>
      </p>
      <p className="text-xs italic">
        This profile is a welcoming scaffold; Ilena is invited to
        replace any part of it with her own words at any time.
      </p>
    </>
  ),
};

export default content;
