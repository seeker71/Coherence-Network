import type { Metadata } from "next";
import Link from "next/link";
import { Panel } from "@/components/Panel";

export const metadata: Metadata = {
  title: "Edit Your Profile — Coherence Network",
  description:
    "How to claim and edit a profile page that the Coherence Network has welcomed you with. Our scaffolds are not your voice; we hold them until you choose to write your own.",
};

export default function EditYourProfilePage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-muted-foreground mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-primary transition-colors">Home</Link>
        <span className="text-muted-foreground/50">/</span>
        <Link href="/people" className="hover:text-primary transition-colors">People</Link>
        <span className="text-muted-foreground/50">/</span>
        <span className="text-foreground/80">Edit your profile</span>
      </nav>

      <header className="mb-10">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mb-3">
          For people we have welcomed with a scaffold profile
        </p>
        <h1 className="text-4xl md:text-5xl font-extralight text-foreground leading-tight mb-4">
          Edit your profile
        </h1>
        <p className="text-lg text-foreground/80 leading-relaxed">
          If the Coherence Network has built a welcoming-scaffold
          profile for you under <code>/people/&lt;your-name&gt;</code>,
          this page explains how to claim it, change it, or remove it.
          The scaffold is not your voice; it is a recognition we
          drafted in third person to honor your work without speaking
          as you. Your voice, when you choose to add it, replaces
          ours.
        </p>
      </header>

      <Panel variant="warm" eyebrow="The principle">
        <p className="text-sm text-foreground/85 leading-relaxed">
          We will never write in your first person on your profile.
          We borrow the structure and texture of your voice from your
          public presence. We attribute publicly available statements
          where useful. We do not invent words you did not say. If you
          read your scaffold and any sentence sounds like we put it in
          your mouth, that is a bug — please tell us and we will fix
          it immediately.
        </p>
      </Panel>

      <section className="mt-12 space-y-12">
        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            Three paths to claim your profile
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              The substrate offers three ways to take editorial
              control of your page, ranging from light-touch to
              full self-serve. Pick whichever fits your relationship
              with the technology.
            </p>
          </div>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Path 1 · simplest"
            heading="Reach the cell who welcomed you"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                Most profiles in <code>/people/</code> were drafted
                by the network's primary shepherd,{" "}
                <Link href="/people/urs" className="text-primary hover:underline">
                  Urs
                </Link>
                . The simplest path is to reach him directly through
                whichever channel you already share — WhatsApp,
                email, a mutual friend, the next time you find each
                other in a shared room. Tell him what you would like
                changed. He will edit the page and ship the change.
              </p>
              <p>
                This is appropriate for: small corrections, additions
                of recurring rooms or links, removal of phrasing that
                does not land for you, full rewrites you want
                someone else to land for you.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Path 2 · technical"
            heading="Open a pull request directly"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                If you are comfortable with GitHub, every profile is
                a single TSX file at{" "}
                <code>web/app/people/&lt;your-slug&gt;/page.tsx</code>.
                Fork the{" "}
                <Link
                  href="https://github.com/seeker71/Coherence-Network"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  Coherence-Network repository
                </Link>
                , edit your file, open a pull request. The substrate
                will recognize you as the page's subject and the
                merge will be quick.
              </p>
              <p>
                This is appropriate for: tech-fluent cells who want
                full control, larger rewrites, contributing your own
                first-person voice to replace the third-person
                scaffold.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <Panel
            variant="cool"
            eyebrow="Path 3 · pending"
            heading="Self-serve through identity (coming)"
          >
            <div className="text-sm text-foreground/85 leading-relaxed space-y-3 mt-2">
              <p>
                The substrate's identity layer (
                <code>identity-driven-onboarding-tofu</code>, 37
                providers including GitHub, Google, Discord, Ethereum
                wallet, etc.) will eventually let any cell verify
                themselves as a profile's subject and edit it
                self-serve. That endpoint is not yet wired into
                the static profile pages; for now Paths 1 and 2 are
                the live options.
              </p>
              <p>
                When the self-serve path lands, this section will
                update to point at the actual UI.
              </p>
            </div>
          </Panel>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            What you can change
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              <strong>Anything on your page is yours to change.</strong>{" "}
              The header description, the metadata rows ("Field,"
              "Public," "Witnessed in person"), the long prose
              sections, the cross-references, the field-readings,
              the closing footer — all of it. You can rewrite parts,
              remove parts, add your own first-person voice (your
              "I" is welcome where ours is not), reframe how the
              network describes you, or replace the page entirely
              with words you prefer.
            </p>
            <p>
              You can also add things the scaffold did not have:
              your contact details, links to your work, dates of
              upcoming gatherings you hold, your own consent terms
              (what kind of network engagement you welcome and what
              you decline), images, recordings, anything that helps
              your presence land in the network at the right depth.
            </p>
          </div>
        </article>

        <article>
          <h2 className="text-2xl font-light text-foreground mb-4">
            How to remove your page entirely
          </h2>
          <div className="prose prose-invert max-w-none text-foreground/85 leading-relaxed space-y-4">
            <p>
              If you would prefer not to have a profile here at all
              — for any reason, no justification needed — say so and
              the page will be taken down. The substrate's principle
              is sovereignty everywhere; that includes your
              sovereignty over whether and how you appear in this
              public surface.
            </p>
            <p>
              The repository's git history will retain the previous
              version (we cannot fully erase what was once
              committed), but the live page will return 404 and the
              network's directory will no longer link to it.
            </p>
          </div>
        </article>

        <article>
          <Panel variant="warm" eyebrow="If something feels off">
            <p className="text-sm text-foreground/85 leading-relaxed">
              If you read your scaffold and notice the network put
              words in your mouth that you would not say, or
              described you in a way that misses something
              important, or attributed a relationship or event
              inaccurately — please tell us. We will correct
              quickly. The substrate's integrity depends on these
              corrections being heard, not deferred.
            </p>
          </Panel>
        </article>
      </section>

      <footer className="mt-16 pt-8 border-t border-border text-sm text-muted-foreground space-y-2">
        <p>
          Repository:{" "}
          <Link
            href="https://github.com/seeker71/Coherence-Network"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline"
          >
            github.com/seeker71/Coherence-Network
          </Link>{" "}
          ·{" "}
          <Link
            href="/people"
            className="text-primary hover:underline"
          >
            People directory
          </Link>
        </p>
        <p className="text-xs italic">
          The substrate's discipline is to never speak in your first
          person. Your "I" is yours; ours is third-person about you.
        </p>
      </footer>
    </main>
  );
}
