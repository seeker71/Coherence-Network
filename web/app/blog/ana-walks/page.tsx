import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { loadPublicWebConfig } from "@/lib/app-config";

const _WEB_UI = loadPublicWebConfig().webUiBaseUrl;

export const metadata: Metadata = {
  title: "Ana walks the field — an honest first-impression audit",
  description:
    "A new contributor arrives on the Coherence Network. Nine pages, nine first impressions, nine chances to welcome. This is what she actually sees on her phone — and what that asks of us next.",
  openGraph: {
    title: "Ana walks the field",
    description:
      "Nine first impressions on a phone, held up against one question: is this really the welcome we want to give?",
    url: `${_WEB_UI}/blog/ana-walks`,
    images: [{ url: "/stories/ana-walk/10-meet-nourishing-desktop.png" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Ana walks the field",
    description: "Nine first impressions on a phone.",
    images: ["/stories/ana-walk/10-meet-nourishing-desktop.png"],
  },
};

interface StepProps {
  n: number;
  image: string;
  alt: string;
  title: string;
  children: React.ReactNode;
}

function Step({ n, image, alt, title, children }: StepProps) {
  return (
    <section className="my-12 scroll-mt-16">
      <h2 className="text-xl font-medium tracking-tight mb-4">
        <span className="text-muted-foreground/60 font-mono mr-3">
          {String(n).padStart(2, "0")}
        </span>
        {title}
      </h2>
      <div className="not-prose my-6 mx-auto max-w-sm rounded-2xl border border-border/30 overflow-hidden bg-stone-950 shadow-xl">
        <Image
          src={image}
          alt={alt}
          width={780}
          height={1688}
          className="w-full h-auto"
        />
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Tender({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border-l-2 border-rose-500/40 bg-rose-500/5 px-4 py-3 text-sm text-stone-300">
      <span className="text-rose-300 font-medium mr-2">Tender —</span>
      {children}
    </p>
  );
}

function Alive({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-md border-l-2 border-emerald-500/40 bg-emerald-500/5 px-4 py-3 text-sm text-stone-300">
      <span className="text-emerald-300 font-medium mr-2">Alive —</span>
      {children}
    </p>
  );
}

export default function AnaWalksPage() {
  return (
    <main id="main-content" className="mx-auto max-w-2xl px-4 sm:px-6 py-12 space-y-6">
      <article className="prose prose-stone dark:prose-invert prose-headings:tracking-tight prose-a:text-amber-600 dark:prose-a:text-amber-400 max-w-none">
        <p className="text-xs uppercase tracking-widest text-muted-foreground">
          Field notes · April 2026
        </p>
        <h1 className="text-3xl md:text-4xl font-light tracking-tight">
          Ana walks the field
        </h1>
        <p className="text-lg text-muted-foreground leading-relaxed">
          A new contributor arrives on her phone. Nine pages, nine first
          impressions, nine chances to welcome her — or lose her. This is what
          she actually sees. Every screenshot is from the live site at 390px
          wide, the width of an iPhone. Below each one: what's alive and
          what's tender, named honestly.
        </p>

        <p className="text-sm text-muted-foreground italic">
          Ana is a permaculturist in Ubud. A friend in Lisbon sent her a
          WhatsApp link. She taps it. She is not logged in. She speaks Bahasa
          but the browser is using English (that's a separate story). Here is
          what happens.
        </p>

        <hr className="border-border/30 my-8" />

        <Step
          n={1}
          image="/stories/ana-walk/01-meet-nourishing-mobile.png"
          alt="Mobile screenshot of /meet/concept/lc-nourishing at 390px — the concept description is clipped on the right side mid-word."
          title="/meet/concept/lc-nourishing — the first touch"
        >
          <p>
            A friend's link lands Ana here. She sees the mycorrhizal image
            (beautiful), the title <em>Nourishing</em>, and the beginning of a
            description about flows circulating like water through soil. At
            the top: her pulse (15), a label (&quot;FIRST MEETING · 1 other
            here now&quot;), and somewhere — she can&apos;t tell where — a pulse
            for the concept itself.
          </p>
          <Alive>
            The image renders gorgeously. The &quot;FIRST MEETING · 1 other here
            now&quot; line does real work — she is not alone in her first
            breath.
          </Alive>
          <Tender>
            The description is cut off mid-word on the right. She can&apos;t
            read past &quot;circulates like blo…&quot;. The three gestures I
            built — care, move on, amplify — should be at the bottom of the
            fold. Instead, the bottom navigation (Vision · Ideas · Contribute
            · Resonance) covers them entirely. She has no way to react.
          </Tender>
          <Tender>
            The content pulse (the concept&apos;s own number) is hidden off the
            right edge. One half of the &quot;you meet this&quot; symmetry is
            missing.
          </Tender>
        </Step>

        <Step
          n={2}
          image="/stories/ana-walk/09-home-mobile.png"
          alt="Mobile screenshot of the home page showing the LiveBreathPanel and the 'what idea are you holding' section."
          title="/ — the home page"
        >
          <p>
            If she navigated to the home page instead, she meets a teal banner
            first: <em>&quot;3 people are meeting something across 2 pieces of
            vision.&quot;</em> Three buttons: Here now · Walk the vision ·
            Propose. Below: &quot;What idea are you holding?&quot; and
            statistics (356 ideas alive, 8,759 value created, 0.60 coherence).
          </p>
          <Alive>
            The breath panel lives. It tells her, in one glance, that the
            place is inhabited. The three buttons are thumb-sized and warm.
          </Alive>
          <Tender>
            The hero question &quot;What idea are you holding?&quot; — the
            site&apos;s most emotional sentence — is clipped on the right
            (&quot;holdi…&quot;). So is the next paragraph (&quot;looking for
            ex…&quot;). The bottom nav again covers content.
          </Tender>
          <Tender>
            Statistics are in English only. &quot;8,759 value created&quot; —
            no unit, no currency symbol, no narrative. For a first-time visitor
            this number is noise, not meaning.
          </Tender>
        </Step>

        <Step
          n={3}
          image="/stories/ana-walk/02-vision-join-mobile.png"
          alt="Mobile screenshot of /vision/join — hero and the first of three paths"
          title="/vision/join — the invitation"
        >
          <p>
            She taps &quot;Step into the network.&quot; The hero reads{" "}
            <em>&quot;The field is formi…&quot;</em> — cut off. Below, three
            paths in cards: Explore, Join, See who&apos;s gathering. The first
            is visible; the others are below the fold.
          </p>
          <Alive>
            The three-path framing is generous. No account demanded. Her
            language, if the UI had switched to Bahasa, would meet her here —
            cycle 21 shipped full localization for this page.
          </Alive>
          <Tender>
            The hero title is clipped at &quot;formi…&quot;. The lede cuts at
            &quot;designed.&quot; and &quot;that want to&quot;. She cannot
            read the welcome even though it's one of the best pieces of
            writing on the site.
          </Tender>
          <Tender>
            The registration form is four full swipes below the fold. Ana may
            never find it.
          </Tender>
        </Step>

        <Step
          n={4}
          image="/stories/ana-walk/03-feed-mobile.png"
          alt="Mobile screenshot of /feed — tabs, empty state, action buttons"
          title="/feed — the felt pulse"
        >
          <p>
            She taps the Contribute nav item. Or Resonance. Or anything that
            sounds warm. Some of those land her on /feed. She sees tabs:
            &quot;Here now · Everyone · You&quot;. Currently Everyone, and
            it&apos;s quiet. A button: &quot;Explore the vision.&quot;
          </p>
          <Alive>
            The three tabs exist. The empty state reads as invitation
            (&quot;The feed is quiet. Be the first breath.&quot;) not as
            apology.
          </Alive>
          <Tender>
            The lede clips: &quot;reactions, voic, seeds&quot;. Two of the
            three footer action chips (Explore more · Propose) bleed off the
            right edge. She can see them starting but not their full labels.
          </Tender>
          <Tender>
            Below the empty state: a big stretch of brown fade to the bottom
            nav. It reads as dead space. A smaller, warmer empty state would
            fit better.
          </Tender>
        </Step>

        <Step
          n={5}
          image="/stories/ana-walk/04-here-mobile.png"
          alt="Mobile screenshot of /here — 'meeting now' with lc-nourishing showing 2 people"
          title="/here — where attention is"
        >
          <p>
            She taps the &quot;Here now&quot; tab. The map of current attention.
            It shows one entity: <em>lc-nourishing</em>, with 2 people meeting
            it right now. She remembers — that was the first concept she met.
            Someone else is there.
          </p>
          <Alive>
            This is the page that most honors the organism right now. The
            &quot;2 people here&quot; signal lands. The concept she just met
            has presence — she can walk back into it.
          </Alive>
          <Tender>
            Right edge clipped again (&quot;+ Pro…&quot;). &quot;Walk a
            serendipitous queue →&quot; runs to the edge. The concepts she
            hasn&apos;t met yet (the cycle-19 &quot;waiting&quot; list) don&apos;t
            appear because there <em>is</em> attention — the surface gates
            them behind a fully quiet state. A warmer version would show both.
          </Tender>
        </Step>

        <Step
          n={6}
          image="/stories/ana-walk/05-feed-you-mobile.png"
          alt="Mobile screenshot of /feed/you — the no-identity state"
          title="/feed/you — the no-identity door"
        >
          <p>
            She taps &quot;You&quot;. Her corner. She hasn&apos;t registered,
            so the page reads: <em>&quot;No name is here yet. Choose one and
            your corner begins.&quot;</em> One button: &quot;Step into the
            network.&quot;
          </p>
          <Alive>
            The no-identity state is honest and inviting, not a wall. A single
            button. The copy is specific — &quot;your corner begins&quot; is a
            beautiful promise.
          </Alive>
          <Tender>
            The lede is clipped mid-word on every line. &quot;replies that
            can&quot; should be &quot;replies that came back to you.&quot;
            She can&apos;t read the promise of what her corner would hold.
          </Tender>
          <Tender>
            The button takes her to /vision/join (not to a sign-in flow), and
            that page also clips. The welcome chain holds the same paper cut
            at every turn.
          </Tender>
        </Step>

        <Step
          n={7}
          image="/stories/ana-walk/06-vision-mobile.png"
          alt="Mobile screenshot of /vision — hero 'The Living Collective' with clipped text"
          title="/vision — the Living Collective"
        >
          <p>
            Or she taps &quot;Vision&quot; in the bottom nav.{" "}
            <em>&quot;The Living Colle…&quot;</em> — clipped. The hero
            promises: &quot;What emerges when community is d…&quot; — clipped.
            Below: &quot;Alive. Changing. Nothing fixed.&quot; A down arrow.
          </p>
          <Alive>
            &quot;Alive. Changing. Nothing fixed.&quot; is the frequency. Those
            four words do more than the entire hero above them.
          </Alive>
          <Tender>
            The Living Collective&apos;s title — the brand of the whole
            section — is clipped at &quot;Colle…&quot;. The body that explains
            what emerges is unreadable. This is the flagship page for the
            51-concept ontology and she can&apos;t read its first screen.
          </Tender>
          <Tender>
            The 51 concepts themselves are not visible on this page. They live
            deeper. Cycle 22 shipped an API fallback that attunes concept
            names into German on the fly — but the /vision page doesn&apos;t
            render concept names, it renders the intro. So even the
            German-speaker who forced ?lang=de into the URL would read an
            English intro here and wonder whether the site is actually
            multilingual.
          </Tender>
        </Step>

        <Step
          n={8}
          image="/stories/ana-walk/07-explore-concept-mobile.png"
          alt="Mobile screenshot of /explore/concept — a meeting with 'Play and Expansion'"
          title="/explore/concept — the walk"
        >
          <p>
            She taps &quot;Walk the vision&quot; from the home panel. One
            concept fills the screen: <em>&quot;Play and Expansion.&quot;</em>{" "}
            &quot;Adults playing freely as children. Experiment-…
            superpositi… possibilities.&quot; Her pulse (15) is on the left.
            There is no content pulse on the right.
          </p>
          <Alive>
            The image of children under strung lights does more in one glance
            than ten headings. The serendipitous walk lands her somewhere she
            didn&apos;t choose — and that&apos;s the point.
          </Alive>
          <Tender>
            The right-side pulse (for the concept itself) has disappeared on
            mobile. The two-organism frame becomes one-sided. Care · move on ·
            amplify are again covered by the bottom nav, so she can&apos;t
            actually advance the walk.
          </Tender>
          <Tender>
            The walk page shows its own &quot;next →&quot; button (fixed
            right, mid-screen) on desktop but on mobile at 390px it&apos;s cut
            off. She doesn&apos;t know how to move to the next concept.
          </Tender>
        </Step>

        <Step
          n={9}
          image="/stories/ana-walk/08-propose-mobile.png"
          alt="Mobile screenshot of /propose — form with three fields"
          title="/propose — offer something"
        >
          <p>
            She finds /propose. A form: title, body, her name, submit. Clean.
            Welcoming.
          </p>
          <Alive>
            This is the simplest page on the site. Three fields, one button.
            The copy tells her what happens next: &quot;Your proposal enters
            the walk right away; reactions become the vote.&quot;
          </Alive>
          <Tender>
            Right-clipped: &quot;Offer something for the collective to meet.
            Your propos…&quot;. She can read that she&apos;s offering
            something; she can&apos;t read the full promise of what happens to
            it.
          </Tender>
        </Step>

        <Step
          n={10}
          image="/stories/ana-walk/10-meet-nourishing-desktop.png"
          alt="Desktop screenshot of /meet/concept/lc-nourishing at 1280px — full layout renders beautifully"
          title="Same page. Desktop. What I thought I was building."
        >
          <p>
            Here&apos;s the same concept page on a 1280px laptop screen. Both
            pulses. &quot;FIRST MEETING · 2 others here now&quot; (plural
            correct). The hero image. The full title, the full description.
            The three gesture buttons — move on, care, amplify — visible and
            thumb-sized. The four-letter locale switcher in the top-right
            (from cycle 20). An &quot;Auto refresh · Available&quot; chip.
          </p>
          <Alive>
            Everything I&apos;ve described across 22 cycles works here. The
            frequency is right. The shape is right. The welcome is right.
          </Alive>
          <Tender>
            I was designing on desktop and the mobile experience — the
            experience a visitor from Bali actually has — was never truly
            inspected. This is the gap between the cycles and the first
            impression.
          </Tender>
        </Step>

        <hr className="border-border/30 my-12" />

        <section className="space-y-4">
          <h2 className="text-xl font-medium">What this walk asks of us</h2>
          <p className="leading-relaxed">
            Before adding a single new feature, three things need to be true.
          </p>

          <div className="rounded-xl border border-border/30 bg-card/30 p-5 space-y-4">
            <div>
              <h3 className="font-medium text-amber-300/90 mb-1">
                1. No page clips on a phone.
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Every mobile screenshot above is clipped on the right. Either
                containers have the wrong max-width, or the root body is
                missing <code>overflow-x: hidden</code>, or (most likely) a
                specific descendant has a fixed width that exceeds 390px. One
                cycle of careful CSS work on every page. Before anything else.
              </p>
            </div>
            <div>
              <h3 className="font-medium text-amber-300/90 mb-1">
                2. The bottom navigation stops covering content on every page
                that has a lower-fold action.
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                The <em>MobileBottomNav</em> is a fixed bar of five legacy
                links. It covers the care/move-on/amplify gestures on every
                meeting surface and the explore walk&apos;s own controls. Two
                paths: either the nav hides when a page has its own bottom
                controls, or the nav gets redesigned to hold the primary
                verbs of the new substrate (Feed · Here · Explore · Propose ·
                Me).
              </p>
            </div>
            <div>
              <h3 className="font-medium text-amber-300/90 mb-1">
                3. The locale switcher is reachable on mobile.
              </h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Cycle 20 added it to the desktop header and to the hamburger
                menu. On 390px the hamburger is currently off-screen (the
                right edge of the header is clipped, so &quot;Simple&quot;
                sits flush against the frame and the menu trigger beside it is
                not visible). Ana cannot switch her UI to Bahasa. The
                beautiful multilingual chrome we shipped is invisible to her.
              </p>
            </div>
          </div>

          <p className="leading-relaxed text-muted-foreground">
            These three fixes are the keystone for every previous cycle
            landing well. After them, the warmer work — an interest mirror
            (&quot;the organism senses you care about&hellip;&quot;), the
            re-discover-yesterday strip, external signals weaving in — becomes
            felt rather than theoretical.
          </p>
        </section>

        <hr className="border-border/30 my-12" />

        <section className="space-y-4">
          <p className="text-xs uppercase tracking-widest text-muted-foreground">
            Field notes · Part two — a week later
          </p>
          <h2 className="text-2xl font-light tracking-tight">
            Mama arrives
          </h2>
          <p className="leading-relaxed text-muted-foreground">
            Ana&apos;s walk was a first audit. The clipping, the covered
            gestures, the hidden locale switcher — all named. What followed
            over the next week was a run of small cycles, each filtered
            through one question: <em>would this make sense to my mother,
            arriving from a WhatsApp link, in German, on her phone?</em>
          </p>
          <p className="leading-relaxed text-muted-foreground">
            She is not a hypothetical. She is 72, lives in Switzerland,
            speaks no English, has never heard the word &quot;blockchain&quot;
            and would not care if she had. The question she would ask is
            the only question that matters: <em>is something alive here
            for me?</em>
          </p>
          <p className="leading-relaxed text-muted-foreground">
            What follows is the same honest walk, held against that
            question. The cycles named below all shipped. The screenshots
            are from the live site.
          </p>
        </section>

        <Step
          n={10}
          image="/stories/ana-walk/11-invite-mobile.png"
          alt="Mobile screenshot of /feed/you showing the InviteFriend card with a recipient-name field and a language selector defaulting to 'Let her device decide'."
          title="/feed/you — the door she comes through"
        >
          <p>
            Before Mama sees anything, someone who already belongs here
            writes her into existence. On my corner of the organism, a
            quiet teal card asks three things: <em>her name, her
            language, what should greet her first?</em>
          </p>
          <p>
            I type <em>Mama</em>. I pick <em>Deutsch</em>. The concept I
            choose is <em>Nourishing</em> — not because it is closest to
            her heart (I do not know yet), but because it is the warmest
            first touch, and a generic home page would feel colder than
            a link to something specific.
          </p>
          <Alive>
            The name field carries more than a greeting — it is a soft
            pre-registration. When she taps the link, her phone writes
            <em> Mama</em> into its own memory. She does not see a sign-up
            screen. She can react, voice, comment on her first minute.
          </Alive>
          <Alive>
            The language selector defaults to <em>&quot;Let her device
            decide.&quot;</em> My browser is in English; hers is in
            German. The default respects the recipient, not the sender.
            But I override it anyway — I know her phone is not always
            set to German, and I want to be sure.
          </Alive>
        </Step>

        <Step
          n={11}
          image="/stories/ana-walk/12-meet-nourishing-welcome-mobile.png"
          alt="Mobile screenshot of /meet/concept/lc-nourishing showing a 'Willkommen, Mama — Patrick lädt dich ein' banner above the concept image, with two pulse circles and the title 'Nourishing' below."
          title="/meet/concept/lc-nourishing?from=Patrick&name=Mama&lang=de — her first breath"
        >
          <p>
            She taps the WhatsApp link. The first thing she sees is a
            small teal line: <em>&quot;Willkommen, Mama — Patrick lädt
            dich ein, diesem zu begegnen.&quot;</em> Her own name. His
            name. Nothing asks her to sign in.
          </p>
          <p>
            Below it: the mycorrhizal image in the center, two pulse
            circles flanking it ( <em>15 du</em> · <em>31 dies</em> with
            &quot;STILL · 2 weitere sind hier&quot; between them), and
            the title <em>Nourishing</em>.
          </p>
          <Alive>
            The banner does the work of a hundred onboarding screens. No
            form, no question, no barrier. Her name is in the greeting
            and the inviter&apos;s name is named. She feels addressed.
          </Alive>
          <Alive>
            The chrome is in her language — the language switcher at the
            top (EN · DE · ES · ID), the pulse labels (du, dies), the
            &quot;bereit&quot; status chip at the bottom. Cycle 21
            shipped full translation for every UI string.
          </Alive>
          <Tender>
            The concept title is still <em>Nourishing</em>, not
            <em> Nährend</em>. The description below it stays in
            English. LibreTranslate is installed on the VPS, but
            single-word concept titles and the living-collective
            descriptions haven&apos;t been re-projected through the
            translator for the snippet-fallback path on this specific
            concept. The frame welcomes her in German; the content
            inside the frame doesn&apos;t yet. This is the next piece
            of work that has to land before the welcome feels complete.
          </Tender>
        </Step>

        <Step
          n={12}
          image="/stories/ana-walk/13-meeting-gesture-mobile.png"
          alt="Mobile screenshot of the meeting surface after tapping the amber heart — an inline 'Möchtest du etwas sagen?' panel has appeared with Mama pre-filled in the name field and a German placeholder asking her to share two sentences."
          title="Her first gesture"
        >
          <p>
            She scrolls to the amber heart below the concept and taps
            it. A small panel unfolds right where her finger was:{" "}
            <em>&quot;MÖCHTEST DU ETWAS SAGEN?&quot;</em> Her name is
            already in the name field — <em>Mama</em>, pre-filled from
            the invite link. The placeholder reads <em>&quot;Zwei Sätze
            reichen. Was hast du gespürt?&quot;</em>
          </p>
          <p>
            She could type something like <em>&quot;Bei uns im Garten
            fließt es auch so — die Kompostwärme macht den Boden
            lebendig.&quot;</em> When she taps <em>Anbieten</em>, her
            voice lands on the concept. Anyone can later lift it into
            a proposal.
          </p>
          <Alive>
            The gesture and the voice are the same motion. Cycle 20
            folded the say-something panel into the reaction — the
            first emoji opens the second door. The amber heart at the
            bottom of the screenshot is now lit, indicating she tapped
            it; the panel appeared above, not below, so her finger
            doesn&apos;t have to travel to find the form.
          </Alive>
          <Alive>
            Every piece of the panel — heading, placeholder, submit
            button, dismiss link — is in German. Her name was carried
            over by the invite so she does not have to type it. Two
            sentences from a Swiss grandmother can become a piece of
            the vision.
          </Alive>
        </Step>

        <Step
          n={13}
          image="/stories/ana-walk/14-home-morning-mobile.png"
          alt="Mobile screenshot of the home page the next morning showing a warm amber 'Guten Morgen' panel with Mama's name, a summary line, and a live news link."
          title="The next morning — a small door, left open"
        >
          <p>
            Twelve hours later, in the kitchen, she opens the app on
            her phone. It is 7:42 on Tuesday morning. The first thing
            on the page is a warm amber panel: <em>&quot;Mama, seit du
            zuletzt hier warst:&quot;</em> Below that, <em>&quot;Aus der
            weiten Welt:&quot;</em> and a live link to a real TechCrunch
            article that the news-resonance engine pulled and matched
            against the ideas in the graph overnight.
          </p>
          <Alive>
            The panel fires only when three things line up: she has a
            soft identity, she has been here before, and her local
            clock is between 06:00 and 11:00. Otherwise it stays quiet.
            No false urgency, no badge nagging her at midnight.
          </Alive>
          <Alive>
            The news link is the first time the news-resonance work —
            quietly matching RSS to ideas for months — meets someone
            whose day it could actually shape. The signal existed. It
            was waiting for a person to receive it.
          </Alive>
          <Tender>
            The amber text is saturated and clips the &quot;Guten
            Morgen&quot; eyebrow on 390px. The &quot;Aus der weiten
            Welt:&quot; label plus the English headline of the matched
            article sit next to each other — she sees a German
            greeting introducing an English news title. The news title
            translation is the next gap to close. And the real push
            notification — the one that arrives when the app is closed
            — still wants a service worker, VAPID keys, and a
            server-side schedule. That is the next cycle.
          </Tender>
        </Step>

        <section className="space-y-4 mt-12">
          <h2 className="text-xl font-medium">What changed between part one and part two</h2>
          <p className="leading-relaxed text-muted-foreground">
            The walk in part one named three keystones: no more clipping,
            the bottom nav gets out of the way, the locale switcher
            becomes reachable. All three shipped. What also shipped —
            unplanned, because Mama&apos;s arrival asked for them — was
            an invitation that carries her name, a banner that
            pre-registers her, a language override that respects her
            phone, an inline voice on first reaction, a &quot;since you
            last were here&quot; delta, and the beginning of a morning
            nudge that folds a real news signal into a felt greeting.
          </p>
          <p className="leading-relaxed text-muted-foreground">
            None of these were on a roadmap. Each came from the same
            question asked twelve times: <em>would this make sense to
            her?</em> When the answer was no, something was built until
            it was yes. That is the shape of the work now.
          </p>
        </section>

        <hr className="border-border/30 my-12" />

        <section className="space-y-3">
          <h2 className="text-xl font-medium">A note on method</h2>
          <p className="leading-relaxed text-muted-foreground">
            Every image above was captured today from{" "}
            <Link href="https://coherencycoin.com">coherencycoin.com</Link>{" "}
            at 390 × 844 pixels, the viewport of an iPhone 13. The desktop
            image was captured at 1280 × 800. No mocks, no synthetic
            composites. This is the site as a first visitor meets it right
            now.
          </p>
          <p className="leading-relaxed text-muted-foreground">
            There is only one first impression. We built a beautiful
            organism; it&apos;s time to make sure a visitor arriving on her
            phone from Ubud can feel it.
          </p>
        </section>

        <div className="mt-12 pt-6 border-t border-border/30 text-sm text-muted-foreground">
          <Link href="/blog" className="hover:text-amber-300/90">
            ← All field notes
          </Link>
        </div>
      </article>
    </main>
  );
}
