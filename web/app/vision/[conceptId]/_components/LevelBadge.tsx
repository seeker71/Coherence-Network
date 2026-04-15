import { LEVEL_LABELS, LEVEL_COLORS } from "@/lib/vision-utils";

export function LevelBadge({ level }: { level?: number }) {
  const l = level ?? 0;
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full border ${LEVEL_COLORS[l] || "border-stone-600 text-stone-400"}`}>
      {LEVEL_LABELS[l] || `Level ${l}`}
    </span>
  );
}
