import Link from "next/link";

export const metadata = {
  title: "Upload Asset — Coherence Network",
  description:
    "Register any digital asset with a MIME type and permanent storage. Full upload awaits Arweave integration.",
};

export default function AssetUploadPage() {
  return (
    <main className="max-w-2xl mx-auto px-6 py-12">
      <nav
        className="text-sm text-stone-500 mb-8 flex items-center gap-2"
        aria-label="breadcrumb"
      >
        <Link href="/" className="hover:text-amber-400/80 transition-colors">
          Home
        </Link>
        <span className="text-stone-700">/</span>
        <span className="text-stone-300">Upload</span>
      </nav>

      <h1 className="text-3xl font-extralight text-white mb-4">
        Upload an asset
      </h1>
      <p className="text-stone-400 text-sm leading-relaxed mb-8">
        The asset-renderer system accepts any MIME type. Permanent storage
        (Arweave + IPFS) and on-chain IP registration (Story Protocol) are
        pending partner integration — for now, registration via the public{" "}
        <code className="text-stone-300">POST /api/assets/register</code>{" "}
        endpoint records the asset with its MIME type and content hash; the
        file hosting is handled externally.
      </p>

      <div className="rounded border border-amber-500/30 bg-amber-500/5 p-5 mb-8">
        <div className="text-amber-200 font-light mb-2">
          Pending Arweave + Story Protocol wiring
        </div>
        <p className="text-sm text-stone-300 leading-relaxed">
          Direct-upload-from-browser is gated on two partner decisions:
        </p>
        <ul className="list-disc list-inside mt-3 space-y-1 text-sm text-stone-400">
          <li>
            Arweave bundler (Irys / Bundlr) — selection + funding wallet
          </li>
          <li>
            Story Protocol SDK — chain selection + signer configuration
          </li>
        </ul>
        <p className="text-sm text-stone-400 mt-3">
          See <code className="text-stone-300">specs/story-protocol-integration.md</code> R1 + R3.
          The service stubs{" "}
          <code className="text-stone-300">
            api/app/services/ip_registration_service.py
          </code>{" "}
          and{" "}
          <code className="text-stone-300">
            api/app/services/permanent_storage_service.py
          </code>{" "}
          define the exact interface partner integration will fill.
        </p>
      </div>

      <div className="space-y-4">
        <h2 className="text-lg font-light text-stone-300">Today's path</h2>
        <p className="text-sm text-stone-400 leading-relaxed">
          Host your content on Arweave / IPFS / GitHub / your own server, then
          register the asset with its hash and URLs via the API. The full
          attribution chain works against that registration — renderer
          resolution, render events, evidence, settlement, and the proof card.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/creators/submit"
            className="rounded border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-amber-200 hover:bg-amber-500/20 transition-colors text-sm"
          >
            Submit a creator asset →
          </Link>
          <Link
            href="/creators"
            className="rounded border border-stone-700 bg-stone-900/50 px-4 py-2 text-stone-200 hover:border-amber-500/40 transition-colors text-sm"
          >
            Creators landing
          </Link>
        </div>
      </div>
    </main>
  );
}
