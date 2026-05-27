// /deploy — real-time deploy log viewer. Phone-first surface for the
// maintainer (often on 4G with no laptop) to watch a deploy unfold without
// SSH or developer tools. Consumes /api/deploy/log/stream (SSE primary)
// with a /api/deploy/log/tail poll fallback, plus /api/deploy/status for
// the SHA + in-progress / complete indicator. Public, no auth — same posture
// as /verify.
import Link from "next/link";
import { DeployLogViewer } from "./_components/DeployLogViewer";

export const metadata = {
  title: "Deploy Status — Coherence Network",
  description: "Watch a deploy unfold in real time. SSE stream with polling fallback. No login required.",
};

export const dynamic = "force-dynamic";

export default function DeployPage() {
  return (
    <main className="min-h-screen max-w-3xl mx-auto px-3 sm:px-6 py-6 sm:py-10">
      <nav className="text-xs sm:text-sm text-stone-500 mb-4 sm:mb-6 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/" className="hover:text-amber-400/80 transition-colors">Home</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Deploy</span>
      </nav>
      <DeployLogViewer />
    </main>
  );
}
