// ════════════════════════════════════════════════════════════════════
// MASCHINELL ÜBERSETZT · machine-translated string fields from en.tsx
// JSX bodies remain in English; refinement welcome.
// To regenerate: python3 scripts/generate_curated_translations.py \
//                  --slug quark-multi-undo-redo --target-lang de --overwrite
// ════════════════════════════════════════════════════════════════════
import Link from "next/link";
import type { PersonProfileContent } from "@/components/people/PersonProfileTemplate";

const content: PersonProfileContent = {
  metadata: {title: "Quark Multi-Document Undo/Redo Motor",description: "Eine undo/redo-Engine für QuarkXPress, die über Dokumente und über Anwendungsflächen arbeitete. Jede Benutzeraktion — per-document edits, anwendungsweite Vorliebenänderungen, die in jedes offene Dokument kaskadiert wurden — konnte abgewickelt und wiedergespielt werden, ohne Sediment zu verlassen. Der architektonisch harte Teil: Aktionen, deren Strahlradius mehrere Dokumente überspannte, mussten sich korrekt in jede pro-Dokumente Zeitlinie einfügen.",
  },breadcrumbName: "Quark Multi-Undo/Redo",
  hero: {
    background:
      "linear-gradient(135deg, hsl(220 30% 8%), hsl(20 35% 14%) 50%, hsl(40 30% 16%))",
    overlayClass:
      "absolute inset-0 bg-gradient-to-t from-background via-background/85 to-background/30",eyebrow: "Arbeit · Quark Inc. · Denver · Mai 2000 – März 2005",
    eyebrowClass: "text-[hsl(var(--chart-2))]",name: "Quark Multi-Document Undo/Redo Motor",
    welcome: (
      <p>
        An undo/redo engine that worked across <em>every</em> open
        document and <em>every</em> application surface in
        QuarkXPress. Any user action could be unwound and re-played —
        per-document edits in the obvious way, but also app-wide
        preference changes that cascaded into multiple open documents
        at once. The architecturally hard part: actions whose blast
        radius spanned multiple documents had to interleave correctly
        into each document's per-document timeline so undoing in any
        document carried the right slice of the global change.
      </p>
    ),
  },
  facts: [
    {label: "Er",value: "Quark Inc. · Denver Office · Mai 2000 – März 2005 · 4 Jahre 11 Monate · Software Engineer III · direkt nach MS Dissertation" },
    {label: "Substrat",value: "C++ · QuarkXPress Laufzeit · Mac OS Classic / Mac OS X / Windows · plattformübergreifendes Action-Record-Modell" },
    {label: "Anwendung", value: (<>QuarkXPress — desktop publishing across multiple simultaneous documents per session. <Link href="https://www.quark.com" target="_blank" rel="noopener noreferrer" className="hover:text-primary">quark.com</Link></>) },
    {label: "Zurück zur Übersicht",
      value: (
        <>
          Backtracking-as-unwinding-without-sediment from the{" "}
          <Link href="/people/bml-language" className="hover:text-primary">2000 BML thesis</Link>
          , now applied at the application level: a user's keystroke
          had a <code className="text-foreground/80">DO</code> and an{" "}
          <code className="text-foreground/80">UNDO</code>, the same
          way every BMA instruction did in the{" "}
          <Link href="/people/bmcpu-vm" className="hover:text-primary">BMCPU virtual machine</Link>
          .
        </>
      ),
    },
    {label: "Linie nach vorne",
      value: (
        <>
          The same <em>tend / attune / compost / release</em> commit
          posture that powers{" "}
          <Link href="/people/coherence-network" className="hover:text-primary">Coherence-Network</Link>
          {" "}today is the same conviction this engine encoded at the
          desktop-app scale: the system never accumulates dead
          sediment, because every change has a clean reverse.
        </>
      ),
    },
  ],
  noteFromBody: {eyebrow: "Was war eigentlich hart",
    body: (
      <p>
        Single-document undo is a textbook problem. Multi-document
        undo with shared application state is{" "}
        <em>not</em>. A "set hyphenation rules" change is not local
        to a document — it modifies an app-wide setting that every
        currently-open document immediately re-paginates against.
        Undoing that change has to either roll back the global state
        AND re-paginate every affected document, or it has to{" "}
        <em>partially</em> roll back if some documents have since
        moved on. The engine had to know, for every action, who its
        affected parties were, and how to compose its reverse with
        the actions that landed after it.
      </p>
    ),
  },
  articles: [
    {
      kind: "narrative",heading: "Zwei Reiche des Staates, eine Zeitlinie pro Spielraum",
      body: (
        <>
          <p>
            QuarkXPress lived in two state realms at once. The{" "}
            <strong>document realm</strong> held everything specific
            to a single open document — pages, text, boxes, style
            sheets local to that document. The{" "}
            <strong>application realm</strong> held everything shared
            — preferences, hyphenation rules, color profiles, font
            substitution policies, plug-in registry — settings that,
            when changed, took effect immediately in every currently-
            open document.
          </p>
          <p>
            The engine modeled each realm with its own action stack.
            Each open document carried a per-document undo stack;
            the application carried a global app-state stack. The
            challenge was that some actions belonged to{" "}
            <em>both</em> realms — an app-wide preference change is
            one global action that produces a consequence in every
            document. The engine had to record one global action
            with N document-side consequences and route undo
            requests so the right slice of the change came back at
            the right moment.
          </p>
          <figure className="my-6 rounded-xl border border-border/40 bg-card/30 p-5">
            <svg viewBox="0 0 720 340" className="w-full h-auto" role="img" aria-labelledby="undo-arch-title">
              <title id="undo-arch-title">Multi-document undo/redo timeline interleaving</title>
              <g fontFamily="ui-sans-serif,system-ui" fontSize="11">
                {/* Application realm timeline */}
                <text x="40" y="40" fill="hsl(40 80% 75%)" fontSize="12">App realm</text>
                <line x1="40" y1="60" x2="680" y2="60" stroke="hsl(40 60% 50%)" strokeWidth="1.5" />
                {/* Three global actions */}
                <g>
                  <rect x="120" y="48" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" />
                  <text x="150" y="64" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">prefs A</text>
                </g>
                <g>
                  <rect x="320" y="48" width="80" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" />
                  <text x="360" y="64" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">hyphenation</text>
                </g>
                <g>
                  <rect x="540" y="48" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" />
                  <text x="570" y="64" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">color</text>
                </g>

                {/* Doc 1 timeline */}
                <text x="40" y="120" fill="hsl(195 80% 75%)" fontSize="12">Doc 1</text>
                <line x1="40" y1="140" x2="680" y2="140" stroke="hsl(195 60% 50%)" strokeWidth="1.5" />
                <g>
                  <rect x="80" y="128" width="40" height="24" rx="4" fill="hsl(195 60% 28%)" stroke="hsl(195 70% 60%)" />
                  <text x="100" y="144" textAnchor="middle" fill="hsl(195 90% 85%)" fontSize="10">edit</text>
                </g>
                <g>
                  <rect x="120" y="128" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="150" y="144" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">prefs ↓</text>
                </g>
                <g>
                  <rect x="220" y="128" width="40" height="24" rx="4" fill="hsl(195 60% 28%)" stroke="hsl(195 70% 60%)" />
                  <text x="240" y="144" textAnchor="middle" fill="hsl(195 90% 85%)" fontSize="10">box</text>
                </g>
                <g>
                  <rect x="320" y="128" width="80" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="360" y="144" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">hyphen ↓</text>
                </g>
                <g>
                  <rect x="440" y="128" width="40" height="24" rx="4" fill="hsl(195 60% 28%)" stroke="hsl(195 70% 60%)" />
                  <text x="460" y="144" textAnchor="middle" fill="hsl(195 90% 85%)" fontSize="10">page</text>
                </g>

                {/* Doc 2 timeline */}
                <text x="40" y="200" fill="hsl(280 70% 80%)" fontSize="12">Doc 2</text>
                <line x1="40" y1="220" x2="680" y2="220" stroke="hsl(280 60% 60%)" strokeWidth="1.5" />
                <g>
                  <rect x="120" y="208" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="150" y="224" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">prefs ↓</text>
                </g>
                <g>
                  <rect x="200" y="208" width="50" height="24" rx="4" fill="hsl(280 60% 30%)" stroke="hsl(280 70% 65%)" />
                  <text x="225" y="224" textAnchor="middle" fill="hsl(280 90% 88%)" fontSize="10">color</text>
                </g>
                <g>
                  <rect x="320" y="208" width="80" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="360" y="224" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">hyphen ↓</text>
                </g>
                <g>
                  <rect x="540" y="208" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="570" y="224" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">color ↓</text>
                </g>

                {/* Doc 3 closed-then-reopened */}
                <text x="40" y="278" fill="hsl(140 70% 75%)" fontSize="12">Doc 3</text>
                <line x1="40" y1="298" x2="290" y2="298" stroke="hsl(140 60% 50%)" strokeWidth="1.5" />
                <line x1="450" y1="298" x2="680" y2="298" stroke="hsl(140 60% 50%)" strokeWidth="1.5" strokeDasharray="3,3" />
                <text x="370" y="302" textAnchor="middle" fill="hsl(140 50% 70%)" fontSize="10">closed</text>
                <g>
                  <rect x="120" y="286" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="150" y="302" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">prefs ↓</text>
                </g>
                <g>
                  <rect x="540" y="286" width="60" height="24" rx="4" fill="hsl(40 70% 28%)" stroke="hsl(40 80% 60%)" strokeDasharray="3,2" />
                  <text x="570" y="302" textAnchor="middle" fill="hsl(40 90% 85%)" fontSize="10">color ↓</text>
                </g>

                <text x="360" y="335" fill="hsl(220 30% 70%)" textAnchor="middle" fontSize="11" fontStyle="italic">
                  global actions cast shadows (dashed) onto every affected document timeline
                </text>
              </g>
            </svg>
            <figcaption className="text-xs text-muted-foreground mt-3 text-center">
              Solid blocks are document-local actions. Dashed blocks are
              the per-document <em>shadow</em> of a global action — the
              same shared event recorded onto each affected document's
              undo stack so unwinding the global state can also unwind
              its document-level consequences correctly.
            </figcaption>
          </figure>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "warm",eyebrow: "Der harte Fall aus Beton",heading: "Hyphenation, drei Dokumente, ein undo",
      body: (
        <>
          <p>
            User opens documents <em>A</em>, <em>B</em>, <em>C</em>.
            Edits boxes in each. Then changes the application-wide
            hyphenation rules. All three documents instantly
            re-paginate. User does more work in <em>A</em> and{" "}
            <em>B</em>, then closes <em>C</em> entirely. Now: user
            presses ⌘Z in <em>A</em>. What should happen?
          </p>
          <p>
            The naïve answer is "undo the most recent action in A's
            stack" — which would unwind one of A's box edits. The
            naïve answer is wrong if the user's mental model is "undo
            the last thing I changed," because the most recent shared
            change was the hyphenation. The engine had to surface the
            hyphenation as an undoable action visible from{" "}
            <em>any</em> currently-open document — not just where it
            originated. Undoing the hyphenation change has to roll
            back the global state, then re-paginate every still-open
            document at its current state. Document <em>C</em>, having
            closed, does not get re-paginated; the engine drops its
            shadow when the document unmounts. If the user later
            re-opens <em>C</em> from disk, its on-disk version reflects
            its state at close-time — independent of the timeline.
            <em> The engine must know what it can and cannot reach</em>.
          </p>
          <p>
            And then there's <em>redo</em>. The user now hits ⌘⇧Z. The
            hyphenation change has to come back, and every still-open
            document has to re-receive its shadow. The two action
            stacks (global, per-document) had to stay in sync without
            either being authoritative — every undoable was tagged
            with its scope, and the engine composed reverses across
            scopes when it had to.
          </p>
        </>
      ),
    },
    {
      kind: "narrative",heading: "Die architektonische Form, die entsteht",
      body: (
        <>
          <p>
            Three primitives carried the weight:
          </p>
          <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
            <li>
              <strong>Action records.</strong> Every user-visible
              change emitted a record carrying its forward
              effect, its reverse effect, and the set of document
              + application surfaces it touched. Records were
              immutable and value-typed; reversing produced a new
              record that the redo stack could re-apply.
            </li>
            <li>
              <strong>Scope-tagged stacks.</strong> Each open
              document held its own undo and redo stack. The
              application held a global undo and redo stack. A
              record could appear in more than one stack — once on
              the global timeline as the canonical event, plus a
              shadow on each document timeline that sees it. All
              shadows pointed at the same underlying record.
            </li>
            <li>
              <strong>Reachability awareness.</strong> When a
              document closed, its shadow links dropped from the
              global record's affected-set. When the user pressed
              undo, the engine asked: "is this record still
              consistent given the current set of open documents?"
              and either applied it normally or applied its
              partially-effective reverse. No silent corruption.
            </li>
          </ul>
          <p>
            Two readings the engine carried that the rest of the
            industry didn't yet have widely. First,{" "}
            <strong>undo as a tree, not a line</strong> — branches
            from divergent edits were addressable, not collapsed
            into a single linear stream. Second,{" "}
            <strong>scope as a first-class property of an action</strong>
            {" "}— the question "what does this change affect?" was
            answered at the moment the action was recorded, not
            inferred at undo time. Both convictions show up later in
            the network's design — the graph as the substrate where
            scope is reachable through edges, and the contribution
            attribution arc as a tree of related actions, not a
            ledger of disconnected events.
          </p>
        </>
      ),
    },
    {
      kind: "panel",
      variant: "cool",eyebrow: "Gleiche Überzeugung · unterschiedliches Substrat",heading: "Die Linie bleibt ungebrochen",
      body: (
        <p>
          The 2000 thesis (
          <Link href="/people/backtracking-model-languages" className="text-primary hover:underline">
            Backtracking Model Languages
          </Link>
          ) made backtracking the architecture of execution: every
          BMA instruction had a forward and a reverse semantics.
          The Quark engine made the same conviction the architecture
          of <em>user experience</em>: every user-action had a forward
          and a reverse, with the reverse aware of its full
          cross-document blast radius. The Coherence Network now
          carries the same posture into{" "}
          <em>commit verbs</em> —{" "}
          <code className="text-foreground/80">tend</code> /{" "}
          <code className="text-foreground/80">attune</code> /{" "}
          <code className="text-foreground/80">compost</code> /{" "}
          <code className="text-foreground/80">release</code> — where
          unwinding without sediment is named directly, and git's tree
          of commits is the timeline that the QuarkXPress engine
          carried per-document, scaled out across cells.
        </p>
      ),
    },
  ],
  footer: (
    <p>
      Application context:{" "}
      <Link
        href="https://www.quark.com"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        quark.com
      </Link>
      {" · "}
      <Link
        href="https://en.wikipedia.org/wiki/QuarkXPress"
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        QuarkXPress on Wikipedia
      </Link>
      . The implementation is internal to Quark and not public — what
      lives here is the architectural shape, the design rationale,
      and the lived memory of building and shipping it. Urs is
      invited to refine the canonical action-record vocabulary and
      any technical detail through the Refine doorway below.
    </p>
  ),
};

export default content;
