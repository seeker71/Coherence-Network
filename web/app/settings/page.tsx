import Link from "next/link";
import { ConfigEditor } from "./_components/ConfigEditor";

export const metadata = {
  title: "Settings — Coherence Network",
};

export default function SettingsPage() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-12">
      <nav className="text-sm text-stone-500 mb-8 flex items-center gap-2" aria-label="breadcrumb">
        <Link href="/" className="hover:text-amber-400/80 transition-colors">Home</Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Settings</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-8">Settings</h1>

      <ConfigEditor />
    </main>
  );
}
