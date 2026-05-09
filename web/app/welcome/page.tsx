// /welcome — the naming gesture. A visitor names themselves, the server
// mints a personal API key (cc_*), lays it as an httpOnly cookie, and
// from then on every write the visitor makes through this browser
// carries their name. The proxy at app/api/[...path]/route.ts reads
// the cookie server-side and translates it into X-API-Key + Authorization
// for upstream FastAPI; the raw key never touches the browser bundle.
import { cookies } from "next/headers";
import Link from "next/link";

import { WelcomeForm } from "./_components/WelcomeForm";

export const metadata = {
  title: "Welcome — Coherence Network",
  description: "Name yourself so what you place here carries your name.",
};

export default async function WelcomePage() {
  const cookieStore = await cookies();
  const existingName = cookieStore.get("coh_contributor_name")?.value || "";

  return (
    <main className="max-w-xl mx-auto px-6 py-12 space-y-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-light">Welcome</h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Anything you place into this body carries your name. So we begin with the name. You can change it later, and you can step
          away whenever you like.
        </p>
      </header>

      {existingName ? (
        <section className="rounded border p-4 space-y-3">
          <p className="text-sm">
            You are here as <span className="font-medium">{existingName}</span>.
          </p>
          <p className="text-sm text-muted-foreground">
            If you would like to be known by a different name, you can name yourself again below. To step out of this browser, use
            <Link href="/session/logout" className="underline ml-1">
              sign out
            </Link>
            .
          </p>
        </section>
      ) : null}

      <WelcomeForm initialName={existingName} />

      <footer className="text-xs text-muted-foreground">
        The name you choose lives in this browser only. Your contributions attach to it through the network.
      </footer>
    </main>
  );
}
