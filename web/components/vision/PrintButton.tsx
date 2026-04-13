"use client";

export function PrintButton({ label = "Print" }: { label?: string }) {
  return (
    <button
      onClick={() => window.print()}
      className="px-4 py-2 rounded-lg bg-amber-600 text-white hover:bg-amber-500 transition-colors text-sm font-medium"
    >
      {label}
    </button>
  );
}
