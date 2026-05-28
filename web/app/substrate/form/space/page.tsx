// Kernel Space — a walkable 3D rendering of the Form kernel's recipe tree.
// Recipes are rooms, children are doorways, blueprints are crystals, and the
// substrate lattice is the floor. See lc-form-kernel-runtime-visualizer.
import type { Metadata } from "next";
import Link from "next/link";
import dynamicImport from "next/dynamic";

const KernelSpace = dynamicImport(() => import("./_components/KernelSpace"), {
  loading: () => (
    <div className="flex h-[calc(100vh-4rem)] items-center justify-center bg-[#05060c] text-sm text-white/40">
      Booting the kernel space…
    </div>
  ),
});

export const metadata: Metadata = {
  title: "Kernel Space — Coherence Network",
  description:
    "Walk what the Form kernel is doing. Recipes are rooms, children are doorways, blueprints are crystals, the substrate lattice is the floor.",
};

export const dynamic = "force-dynamic";

export default function KernelSpacePage() {
  return (
    <main className="w-full">
      <nav
        className="border-b border-white/10 bg-[#0a0c14] px-4 py-2 text-sm text-stone-500"
        aria-label="breadcrumb"
      >
        <Link href="/substrate" className="transition-colors hover:text-amber-400/80">
          Substrate
        </Link>
        <span className="mx-2 text-stone-700">/</span>
        <Link
          href="/substrate/form"
          className="transition-colors hover:text-amber-400/80"
        >
          Form
        </Link>
        <span className="mx-2 text-stone-700">/</span>
        <span className="text-stone-300">Space</span>
      </nav>
      <KernelSpace />
    </main>
  );
}
