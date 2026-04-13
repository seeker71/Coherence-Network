import type { Metadata } from "next";
import Link from "next/link";
import QRCode from "qrcode";
import { PrintButton } from "@/components/vision/PrintButton";

export const metadata: Metadata = {
  title: "Flyer — The Living Collective",
  description: "Printable flyer with QR code for The Living Collective.",
};

async function generateQRDataUrl(url: string): Promise<string> {
  return QRCode.toDataURL(url, {
    width: 400,
    margin: 2,
    color: { dark: "#292524", light: "#fafaf9" },
    errorCorrectionLevel: "H",
  });
}

export default async function FlyerPage() {
  const siteUrl = "https://coherencycoin.com/vision/join";
  const qrDataUrl = await generateQRDataUrl(siteUrl);

  return (
    <>
      {/* Print styles */}
      <style>{`
        @media print {
          body { background: white !important; color: #1c1917 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          .no-print { display: none !important; }
          .print-page { page-break-after: always; break-after: page; }
          @page { margin: 0.5in; size: letter; }
        }
      `}</style>

      {/* Screen: navigation + print */}
      <div className="no-print fixed top-4 right-4 z-50 flex gap-3">
        <Link
          href="/vision/flyer/posters"
          className="px-4 py-2 rounded-lg bg-stone-800 text-stone-300 hover:bg-stone-700 transition-colors text-sm"
        >
          View workspace posters
        </Link>
        <PrintButton label="Print flyer" />
      </div>

      {/* ═══ FLYER 1: Main invitation flyer (letter/A4) ═══ */}
      <div className="print-page min-h-screen flex flex-col items-center justify-center p-8 bg-stone-50 text-stone-900 print:bg-white">
        <div className="max-w-lg w-full space-y-10 text-center">
          {/* Title */}
          <div className="space-y-3">
            <p className="text-sm tracking-[0.4em] uppercase text-stone-500 font-medium">
              A new way of living together
            </p>
            <h1 className="text-5xl md:text-6xl font-extralight tracking-tight text-stone-800 leading-tight">
              The Living
              <br />
              <span className="font-light text-amber-700">Collective</span>
            </h1>
          </div>

          {/* Essence */}
          <div className="space-y-4 text-lg text-stone-600 leading-relaxed max-w-md mx-auto">
            <p>
              A community of 50-200 people living as a single organism.
              No rules — resonance. No obligation — offering. No isolation — field.
            </p>
            <p className="text-base text-stone-500">
              Shared kitchens. Living gardens. Sound circles. Open workshops.
              Children weaving between all of it. Elders holding the frequency.
              Everyone contributing what flows through them naturally.
            </p>
          </div>

          {/* QR Code */}
          <div className="flex flex-col items-center gap-4 py-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={qrDataUrl}
              alt="QR code to join The Living Collective"
              width={180}
              height={180}
              className="rounded-lg"
            />
            <p className="text-sm text-stone-500 font-medium">
              Scan to explore the vision and express your resonance
            </p>
            <p className="text-xs text-stone-400 font-mono">
              coherencycoin.com/vision/join
            </p>
          </div>

          {/* What we're looking for */}
          <div className="text-left space-y-3 p-6 rounded-xl border border-stone-200 bg-stone-100/50">
            <p className="text-sm font-medium text-stone-700 text-center">
              The field is calling for:
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm text-stone-600">
              <div>
                <span className="text-amber-700">&#9670;</span> Builders &amp; architects
              </div>
              <div>
                <span className="text-amber-700">&#9670;</span> Permaculturists &amp; cooks
              </div>
              <div>
                <span className="text-amber-700">&#9670;</span> Musicians &amp; sound healers
              </div>
              <div>
                <span className="text-amber-700">&#9670;</span> Bodyworkers &amp; facilitators
              </div>
              <div>
                <span className="text-amber-700">&#9670;</span> Community elders
              </div>
              <div>
                <span className="text-amber-700">&#9670;</span> Earth workers &amp; makers
              </div>
            </div>
          </div>

          {/* Footer */}
          <p className="text-xs text-stone-400 italic">
            The field doesn't ask for credentials. It senses resonance.
          </p>
        </div>
      </div>

      {/* ═══ FLYER 2: Compact tear-off strip version ═══ */}
      <div className="print-page min-h-screen flex flex-col items-center justify-center p-8 bg-stone-50 text-stone-900 print:bg-white">
        <div className="max-w-2xl w-full space-y-6">
          <p className="text-center text-sm text-stone-500 no-print">
            Tear-off strips — print and cut along the dashed lines
          </p>

          {/* 5 identical strips */}
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="flex items-center gap-6 p-4 border border-dashed border-stone-300 rounded-lg"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={qrDataUrl}
                alt="QR code"
                width={80}
                height={80}
                className="rounded flex-shrink-0"
              />
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-light text-stone-800">
                  The Living Collective
                </h3>
                <p className="text-sm text-stone-600">
                  50-200 people. No rules — resonance. Scan to explore and join.
                </p>
              </div>
              <div className="text-right flex-shrink-0 text-xs text-stone-400 font-mono">
                coherencycoin.com
                <br />
                /vision/join
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
