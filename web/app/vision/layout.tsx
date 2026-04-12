/**
 * Vision layout — dark theme wrapper that preserves the Living Collective
 * aesthetic across all /vision/* pages. Children render inside the dark
 * field; the site header inherits from the root layout above.
 */
export default function VisionLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-b from-stone-950 via-stone-950 to-stone-900 text-stone-100">
      {children}
    </div>
  );
}
