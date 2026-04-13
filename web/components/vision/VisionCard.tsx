/**
 * Emerging vision card — a concept that's ready for concrete realization.
 */
import Link from "next/link";

type VisionCardProps = {
  title: string;
  conceptId: string;
  description: string;
};

export function VisionCard({ title, conceptId, description }: VisionCardProps) {
  return (
    <Link
      href={`/vision/${conceptId}`}
      className="group p-6 rounded-2xl border border-stone-800/40 bg-stone-900/20 hover:bg-stone-900/40 hover:border-amber-800/30 transition-all duration-500 space-y-3"
    >
      <h3 className="text-lg font-light text-amber-300/80 group-hover:text-amber-300 transition-colors">
        {title}
        <span className="ml-2 text-stone-700 group-hover:text-amber-500/40 transition-colors">→</span>
      </h3>
      <p className="text-sm text-stone-500 leading-relaxed">{description}</p>
    </Link>
  );
}
