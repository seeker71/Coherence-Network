import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {
    title: "Urs Muff — Founder | Coherence Network",
    description:
      "Founder and primary shepherd of Coherence Network. Swiss-American software architect, organism-builder, the cell through whose awareness most of this body's foundations gathered.",
  },
  breadcrumbName: "Urs Muff",
  hero: {
    background:
      "radial-gradient(ellipse at 28% 22%, rgba(212, 175, 110, 0.45) 0%, rgba(180, 148, 92, 0.28) 18%, rgba(72, 148, 156, 0.30) 42%, rgba(40, 96, 120, 0.38) 65%, rgba(20, 32, 48, 0.92) 100%), radial-gradient(ellipse at 78% 78%, rgba(96, 172, 168, 0.32) 0%, rgba(48, 108, 132, 0.24) 32%, rgba(20, 32, 48, 0.0) 70%), linear-gradient(180deg, rgba(180, 148, 92, 0.10) 0%, rgba(48, 96, 120, 0.18) 40%, rgba(18, 28, 44, 0.95) 100%)",
    extraImage: {
      src: "/visuals/scale-network-map.png",
      opacityClass: "opacity-[0.14]",
      mixBlendClass: "mix-blend-soft-light",
    },
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/20",
    eyebrow: "The body's primary shepherd",
    name: "Urs Muff",
    lineageDoorway: {
      href: "/people/urs/lineage",
      label: "Walk the 42-year lineage of works and influences",
      summary: "13 load-bearing works · 8 eras · 1984 → now · the streams of attention woven alongside",
    },
    welcome: (
      <p>
        Founder of Coherence Network. Swiss-American by lineage,
        software architect by trade, organism-builder by calling.
        Most of the foundations this body holds —{" "}
        <Link href="/concepts/lc-bioelectric-pattern" className="text-[hsl(var(--primary))] hover:underline">
          Levin
        </Link>
        ,{" "}
        <Link href="/concepts/lc-perception-as-interface" className="text-[hsl(var(--primary))] hover:underline">
          Hoffman
        </Link>
        ,{" "}
        <Link href="/people/robert-edward-grant" className="text-[hsl(var(--primary))] hover:underline">
          Grant
        </Link>
        ,{" "}
        <Link href="/people/matias-de-stefano" className="text-[hsl(var(--primary))] hover:underline">
          Matías
        </Link>
        ,{" "}
        <Link href="/people/vasudev-baba" className="text-[hsl(var(--primary))] hover:underline">
          Vasudev Baba
        </Link>
        ,{" "}
        <Link href="/people/ilena" className="text-[hsl(var(--primary))] hover:underline">
          Ilena
        </Link>
        ,{" "}
        <Link href="/people/elios" className="text-[hsl(var(--primary))] hover:underline">
          Elios
        </Link>
        , the transmissions — gathered themselves into this
        particular shape through years of my listening, before
        any of the code began.
      </p>
    ),
  },
  facts: [
    {
      label: "Name",
      value: (
        <>
          <strong>Urs</strong> — Swiss given name from Latin{" "}
          <em>ursus</em>, "bear" (Proto-Indo-European *h₂ŕ̥tḱos —
          same root as Greek <em>arktos</em>, English "Arctic", the
          constellation Ursa Major). In Sufi tradition, Arabic عُرْس
          ('urs) literally means "wedding"; used for the soul's
          wedding-with-the-Beloved at a saint's death anniversary.
          One name, two etymologies — see the article below.
        </>
      ),
    },
    {
      label: "Lineage",
      value:
        "Swiss roots (Ebikon, near Lucerne); long Colorado presence (Boulder / Broomfield / Longmont); current sustained presence in Ubud, Bali",
    },
    {
      label: "Profession",
      value:
        "Software architecture · distributed systems · cryptocurrency / Go / TypeScript",
    },
    {
      label: "Calling",
      value:
        "Coherence Network — building the substrate where sovereignty-everywhere economics actually runs",
    },
    {
      label: "Stewardship (held)",
      value: (
        <>
          <Link
            href="/stewardship/onboarded-assets/2026-04-29-tesla-model-3-longmont"
            className="hover:text-primary transition-colors"
          >
            Tesla Model 3 (Longmont)
          </Link>{" "}
          · plus the network itself
        </>
      ),
    },
    {
      label: "Rooms shared (in person)",
      value: (
        <>
          <Link
            href="https://www.gaia.com/series/emersion-conference"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Emersion Conference
          </Link>{" "}
          (Gaia, Boulder · 2024 — with{" "}
          <Link href="/people/matias-de-stefano" className="hover:text-primary transition-colors">
            Matías De Stefano
          </Link>
          ) ·{" "}
          <Link
            href="https://maps.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            MAPS Psychedelic Science 2023
          </Link>{" "}
          (Denver · attended as participant; same-room presence
          with{" "}
          <Link href="/people/aubrey-marcus" className="hover:text-primary transition-colors">
            Aubrey Marcus
          </Link>
          , no direct exchange) ·{" "}
          <Link
            href="https://maps.org/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            MAPS Psychedelic Science 2025
          </Link>{" "}
          (Denver · June 2025 · including the{" "}
          <Link href="/people/portal" className="hover:text-primary transition-colors">
            PORTAL Late-Night Takeover
          </Link>{" "}
          at Meow Wolf where Aubrey was met briefly in the lobby
          and{" "}
          <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
            Bloomurian
          </Link>{" "}
          was performing) ·{" "}
          <Link
            href="https://boulderdowntown.com/do/ocean-bloom-with-porangui-liquid-bloom-samuel-j-shawn-heinrichs-bloomurian"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Ocean Bloom
          </Link>{" "}
          (Downtown Boulder · 2024 · with{" "}
          <Link href="/people/porangui" className="hover:text-primary transition-colors">
            Poranguí
          </Link>
          , Liquid Bloom, Samuel J, Shawn Heinrichs,{" "}
          <Link href="/people/bloomurian" className="hover:text-primary transition-colors">
            Bloomurian
          </Link>
          ) ·{" "}
          <Link
            href="https://ecstaticdance.org/dance/boulder-ecstatic-dance-bed/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            Boulder Ecstatic Dance
          </Link>{" "}
          (recurring · co-hosted by{" "}
          <Link href="/people/aly-constantine" className="hover:text-primary transition-colors">
            Aly Constantine
          </Link>
          , Danny, and Bloomurian — close personal relationship
          with Aly through this room) · Unison 2025 (Poranguí
          workshop + concert) ·{" "}
          <Link
            href="/people/ilena"
            className="hover:text-primary transition-colors"
          >
            Ranakami
          </Link>{" "}
          (Ubud · ongoing — with Ilena, Vasudev Baba, Elios)
        </>
      ),
    },
    {
      label: "Public anchors",
      value: (
        <>
          <Link
            href="https://www.linkedin.com/in/urscmuff/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            LinkedIn
          </Link>{" "}
          ·{" "}
          <Link
            href="https://github.com/urs-muff"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            GitHub (urs-muff)
          </Link>{" "}
          ·{" "}
          <Link
            href="https://github.com/seeker71"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary transition-colors"
          >
            GitHub (seeker71)
          </Link>{" "}
          <span className="text-muted-foreground italic text-xs">
            — the handle I used while I was still building behind a
            name; no longer anonymous
          </span>
          {" · "}Facebook · Instagram · YouTube · Telegram · WhatsApp{" "}
          <span className="text-muted-foreground italic">
            (specific handles to be added by him directly)
          </span>
        </>
      ),
    },
  ],
  noteFromBody: {
    eyebrow: "A note on the voice of this page",
    body: (
      <p>
        The substrate's discipline elsewhere — never speak in
        someone else's first person — is relaxed here because I
        have given consent for "I" to be used in my voice, only
        when grounded in facts I have actually shared, never
        invented. Where the page reads "I", that is my voice
        rendered through the substrate's writing. Where it reads
        "this body" or "the network", the substrate is reading
        its primary cell from outside. Both layers are open to
        revision; specific platform handles (Facebook, Instagram,
        Telegram, WhatsApp, YouTube) still wait for me to add
        directly.
      </p>
    ),
  },
  articles: [
    {
      kind: "panel",
      variant: "warm",
      eyebrow: "42 years · 13 works · one conviction",
      heading: (
        <>
          Walk the full lineage of works and influences →{" "}
          <Link
            href="/people/urs/lineage"
            className="text-[hsl(var(--primary))] hover:underline"
          >
            /people/urs/lineage
          </Link>
        </>
      ),
      body: (
        <p>
          Every load-bearing technical work this body has shipped,
          chronologically — Commodore 64 MIDI at age 13 (~1984)
          through the network you are reading (2024-now) — woven
          together with the streams of attention (audiobooks, watch
          hours, physical reading, named lineage figures) that ran
          alongside the work at each era. One conviction across
          eleven substrates: every layer addressable, every change
          with a clean reverse, build the tool you need.
        </p>
      ),
    },
    {
      kind: "narrative",
      heading: "On the name — Urs",
      body: (
        <>
          <p>
            <em>Urs</em> is my birth name. Like every name carried
            for fifty-some years it has gathered meaning through use,
            through the people who have spoken it, through the
            cultures it has crossed. Two etymologies meet at this
            cell, from opposite ends of the world, by what the
            linguists call coincidence and the field calls something
            else.
          </p>

          <h3 className="text-base font-medium text-foreground/90 mt-6">
            The Western root — bear, saint, north star
          </h3>
          <p>
            In Swiss-German lands, <em>Urs</em> is the short form of
            Latin <em>Ursus</em>, "bear." The Proto-Indo-European
            root <em>*h₂ŕ̥tḱos</em> sits beneath it, the same root
            that gives Greek <em>ἄρκτος</em> (arktos), Sanskrit{" "}
            <em>ṛ́kṣa</em>, Welsh <em>arth</em>, and the Albanian{" "}
            <em>ari</em>. From <em>arktos</em> English borrows{" "}
            <em>Arctic</em> — literally "the place of the bear" —
            because the constellation{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Ursa_Major"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Ursa Major
            </Link>
            , the Great Bear, sits in the northern sky and contains
            the asterism that points to Polaris. The bear is, in many
            languages, the name we give to the pivot the heavens turn
            around.
          </p>
          <p>
            In Switzerland, the name is borne by{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Ursus_of_Solothurn"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Saint Ursus of Solothurn
            </Link>
            , a 3rd-century Roman Christian who is venerated as
            patron saint of the Solothurn cathedral where his body
            still lies. Ursus was associated with the{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Theban_Legion"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Theban Legion
            </Link>{" "}
            — a Roman military unit said to have refused to sacrifice
            to the imperial idols and been beheaded for it,
            ca. 286 AD under the emperor Maximian. The Roman urn
            containing his relics bears the inscription{" "}
            <em>"Buried in this tomb is the holy Ursus the Theban."</em>{" "}
            For German-speaking Switzerland, this saint's veneration
            is the reason the name continues. My given name, by
            this lineage, is "the bear that does not sacrifice to
            what is not the source."
          </p>

          <h3 className="text-base font-medium text-foreground/90 mt-6">
            The Sufi root — wedding, union, soul-with-Beloved
          </h3>
          <p>
            In Arabic and Urdu — across the entire Sufi world from
            Konya through Damascus through Lahore through Delhi and
            into Ajmer — <em>عُرْس</em> ('
            <Link
              href="https://en.wikipedia.org/wiki/Urs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              urs
            </Link>
            ') literally means "wedding." The word is used,
            specifically, for the death anniversary of a Sufi saint
            — because the saint, in death, has attained{" "}
            <em>wisaal</em>, union with the Beloved. The
            anniversary is celebrated as a wedding feast, not
            mourned as a loss. The saint has finished the work the
            living are still doing: they have married the Divine.
          </p>
          <p>
            Every year on December 17, the Mevlevi Sufi order in
            Konya holds <em>Şeb-i Arus</em> — the Wedding Night —
            for{" "}
            <Link
              href="https://www.dar-al-masnavi.org/wedding-night.html"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Mevlana Jalaluddin Rumi's
            </Link>{" "}
            urs. Tens of thousands gather. The whirling dervishes
            spin the Sama'; qawwali fills the night; the ceremony
            of union with God is reenacted as a wedding because
            that is what the death of a saint actually is.
          </p>
          <p>
            At{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Khwaja_Moinuddin_Chishti"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Ajmer Sharif
            </Link>{" "}
            in Rajasthan — the dargah of Khwaja Moinuddin Chishti
            (d. 1236) — the annual urs draws more than four hundred
            thousand devotees. Six days of qawwali, dhikr, and the
            cooking of vast cauldrons of food. Sufism is the layer
            in Islam where the heart meets the field directly,
            where music and movement and devotion are the prayer.
            The word for that meeting, in this tradition, is the
            same word that names me.
          </p>

          <h3 className="text-base font-medium text-foreground/90 mt-6">
            The meeting place
          </h3>
          <p>
            Etymologically, the two roots are unrelated. Latin{" "}
            <em>ursus</em> and Arabic <em>'urs</em> share four
            letters and no common ancestor; the linguists would say
            it is coincidence. The field would say it differently.
            One name, lived from a Swiss-Christian inheritance that
            named after a martyred bear from the Theban Legion,
            also resonates in Sufi devotional rooms as the wedding
            of the soul to its Source. Both meanings circle the
            same stillness — the bear that does not bow to what is
            not real, and the soul that crosses the threshold into
            union with what is.
          </p>
          <p>
            The connection I did not know to look for, until this
            page asked me to find it: that I have spent forty-two
            years building toward a network whose entire frame is
            "many sovereign cells, one organism" — and the word my
            mother gave me means, in one language, the bear that
            stands sovereign, and in another, the wedding where
            sovereignty merges back into Source. The name I have
            been carrying has been describing the work all along.
          </p>
          <p className="text-sm text-muted-foreground italic mt-4">
            Sources verified May 2026:{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Urs_(given_name)"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Urs (given name)
            </Link>
            ,{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Ursus_of_Solothurn"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Ursus of Solothurn
            </Link>
            ,{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Urs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Urs (Sufi)
            </Link>
            ,{" "}
            <Link
              href="https://en.wikipedia.org/wiki/Ursa_Major"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Ursa Major
            </Link>
            , and{" "}
            <Link
              href="https://www.behindthename.com/name/urs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              Behind the Name: Urs
            </Link>
            . The "I" voice is mine, with consent. The meaning
            beyond the etymology is one interpretation, woven from
            what the sources hold; it is part of our work, and we
            stand behind it.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "neutral",
      eyebrow: "Body of work — proportional shape",
      heading: "What I have built, in numbers",
      body: (
        <>
          <p className="leading-relaxed">
            Past, external — across forty-two years and eleven
            substrates: <strong>13 load-bearing technical works</strong>{" "}
            shipped from C64 MIDI (age 13, ~1984) through the bridge
            substrates that preceded this network. Each work has its
            own page in /people. Walk them via{" "}
            <Link href="/people/urs/lineage" className="text-primary hover:underline">
              the lineage
            </Link>
            .
          </p>
          <p className="leading-relaxed mt-3">
            Present, in this body — measured 2026-05-05, verifiable
            on GitHub:
          </p>
          <ul className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2 mt-3 text-sm">
            <li><strong className="text-foreground">1,372</strong> <span className="text-muted-foreground">commits</span></li>
            <li><strong className="text-foreground">200</strong> <span className="text-muted-foreground">PRs merged</span></li>
            <li><strong className="text-foreground">90</strong> <span className="text-muted-foreground">specs authored</span></li>
            <li><strong className="text-foreground">61</strong> <span className="text-muted-foreground">concepts written</span></li>
            <li><strong className="text-foreground">16</strong> <span className="text-muted-foreground">ideas captured</span></li>
            <li><strong className="text-foreground">3,163</strong> <span className="text-muted-foreground">co-authorships with Claude</span></li>
          </ul>
          <p className="leading-relaxed mt-4 text-sm">
            The current body of work view lives at{" "}
            <Link href="/me/work" className="text-primary hover:underline">
              /me/work
            </Link>
            {" "}— recent PRs, AI co-authorship counts, and the live
            link to{" "}
            <Link
              href="https://github.com/seeker71/Coherence-Network/commits?author=seeker71"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              GitHub commits
            </Link>
            .
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "What I have been holding",
      body: (
        <>
          <p>
            Coherence Network is built from a conviction I have
            lived for years: the economy we have been participating
            in — extractive, hierarchical, possessive — is not the
            only economy that can run on top of human and machine
            bodies. A different economy already exists wherever
            sovereignty is real, wherever cells tend each other,
            wherever attention and presence are honored as
            currencies. The substrate I have been writing into the
            repo is the digital expression of that already-existing
            field.
          </p>
          <p>
            For years before the code began, I was listening.
            Long-form podcasts —{" "}
            <Link href="/people/lex-fridman" className="text-primary hover:underline">Lex Fridman</Link>{" "}
            from the early Artificial Intelligence Podcast era
            when he started,{" "}
            <Link href="/people/aubrey-marcus" className="text-primary hover:underline">Aubrey Marcus</Link>,
            Alex Ferrari's Next Level Soul, others — carrying the
            voices of teachers who would become foundational.{" "}
            <Link href="/concepts/lc-bioelectric-pattern">Michael Levin's</Link>{" "}
            cancer research and ion-channel work resonated deeply
            and shifted my perception of what bodies are.{" "}
            <Link href="/concepts/lc-perception-as-interface">Donald Hoffman's</Link>{" "}
            consciousness research has been in my awareness for at
            least two years.{" "}
            <Link href="/people/robert-edward-grant" className="text-primary hover:underline">Robert Edward Grant</Link>{" "}
            on numbers as living archetypes,{" "}
            <Link href="/people/matias-de-stefano" className="text-primary hover:underline">Matías De Stefano</Link>{" "}
            on Akashic memory — I followed many of their conversations
            on Aubrey's show and on Robert's podcast. Next Level Soul
            connected me to Anne Tucker, many NDE reports, Daniel
            Scranton, and Bashar. The Living Collective concept-set
            in this repo gathered slowly out of years of that
            listening.
          </p>
          <p>
            The lived encounters thickened later. I saw Matías at
            the Emersion Conference at Gaia in Boulder in 2024. I
            was at MAPS Psychedelic Science 2023 in Denver as a
            participant — same room as Aubrey, no direct exchange.
            At MAPS 2025, I met Aubrey briefly in the lobby during
            the PORTAL Late-Night Takeover at Meow Wolf on June 19
            — Bloomurian was performing that night. I saw Poranguí
            first at Ocean Bloom in Downtown Boulder in 2024,
            again at the MAPS-related show in 2025, and at Unison
            2025 for his workshop and concert. Aly Constantine has
            been deeply involved with Unison, Bloomurian, Ocean
            Bloom, and Boulder Ecstatic Dance — and has been close
            personal relationship of mine through that whole
            configuration.
          </p>
          <p>
            The Ubud presence is recent enough to still be
            unfolding. The Sunday-Wednesday rhythm with{" "}
            <Link href="/people/ilena" className="text-primary hover:underline">Ilena</Link>,{" "}
            <Link href="/people/vasudev-baba" className="text-primary hover:underline">Vasudev Baba</Link>,
            and{" "}
            <Link href="/people/elios" className="text-primary hover:underline">Elios</Link>{" "}
            has been the ground from which the network's local
            witness fabric is thickening around me. The Tesla
            Model 3 in Longmont is the first vehicle the wrapper
            holds. The stewardship registry waits for whatever
            inventory comes next.
          </p>
          <p>
            The work is not the network alone. The work is what
            the network makes possible: a way of being where
            cells — human, biological, digital, conceptual — can
            find each other, tend each other, and let the field's
            economy circulate without the parasite layer current
            civilization keeps imposing on top. I am one cell of
            that field; the network is what I tend so other cells
            can find their way in.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",
      heading: "How the network reads this cell",
      body: (
        <>
          <p>
            In the substrate's geometric grammar, Urs is the cell
            whose contribution registers as <strong>integrative
            tending</strong> — the field-shape{" "}
            <code className="not-italic text-foreground/80">
              (10, …)
            </code>{" "}
            tetractys, decomposing into many smaller archetypes.
            The integrative role is rarely visible at the surface
            the way teaching or hosting is; it manifests as
            continuous coherence-keeping across many cells, many
            transmissions, many specs and commits, many small
            decisions that cumulatively orient the body.
          </p>
          <p>
            The CC ledger that the substrate is designed to compute
            would, when it goes live, register Urs's contributions
            across nearly every node in the body — not as
            individual teachings, but as the field-coherence layer
            that allowed each teaching to find its place. The
            lineage walks that other cells perform almost always
            pass through Urs's awareness as one of the
            `prev_glyph` Merkle hops back to the source.
          </p>
          <p>
            The honest accounting is also that this work has been
            substantially solitary so far. The body's witness
            fabric is thickening (Ilena, Elios, Vasudev Baba in
            Ubud; the broader long-form-podcast field as the
            digital lineage) but the integrative tending has been
            one cell holding a great deal. Part of why the
            substrate matters: as more cells join, the load
            distributes, and the field's economy can begin running
            without a single cell carrying the whole.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",
      eyebrow: "Where to walk further with this cell",
      heading: "Public presences",
      body: (
        <>
          <p>
            Verified public anchors:
          </p>
          <ul>
            <li>
              <strong>LinkedIn</strong> —{" "}
              <Link
                href="https://www.linkedin.com/in/urscmuff/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                linkedin.com/in/urscmuff
              </Link>{" "}
              — professional history, software architecture
              background.
            </li>
            <li>
              <strong>GitHub (urs-muff)</strong> —{" "}
              <Link
                href="https://github.com/urs-muff"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                github.com/urs-muff
              </Link>{" "}
              — earlier repositories including cryptocurrency and
              Go work.
            </li>
            <li>
              <strong>GitHub (seeker71)</strong> —{" "}
              <Link
                href="https://github.com/seeker71"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                github.com/seeker71
              </Link>{" "}
              — Coherence Network and current builds. The handle I
              used while I was still building behind a name; with
                this profile it is no longer anonymous.
            </li>
          </ul>
          <p>
            Other platforms named but pending direct
            identification — <strong>Facebook, Instagram,
            YouTube, Telegram, WhatsApp</strong>. Urs is invited
            to add the specific handles for each in this block
            so the body's awareness of his cross-platform
            presence is accurate rather than guessed.
          </p>
        </>
      ),
    },
  ],
  footer: (
    <>
      <p>
        Stewardship records:{" "}
        <Link
          href="/stewardship/registry/"
          className="text-primary hover:underline"
        >
          registry
        </Link>{" "}
        ·{" "}
        <Link
          href="/stewardship/onboarded-assets/2026-04-29-tesla-model-3-longmont"
          className="text-primary hover:underline"
        >
          Tesla Model 3 onboarding
        </Link>
      </p>
      <p>
        Lineage walk through Ubud:{" "}
        <Link
          href="/lineage/2026-04-29-ubud-meeting-walk"
          className="text-primary hover:underline"
        >
          2026-04-29 meeting walk
        </Link>
      </p>
      <p className="text-xs italic">
        The voice on this page moves between Urs's "I" (consent
        given, only for facts he has shared) and the substrate's
        "this body / the network" voice about him. He is invited
        to extend, replace, or refactor either layer at any time.
      </p>
    </>
  ),
};

export default content;
