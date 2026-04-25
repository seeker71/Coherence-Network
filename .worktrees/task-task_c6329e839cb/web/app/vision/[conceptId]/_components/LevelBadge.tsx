"use client";

import { LEVEL_COLORS } from "@/lib/vision-utils";
import { useT } from "@/components/MessagesProvider";

export function LevelBadge({ level }: { level?: number }) {
  const l = level ?? 0;
  const t = useT();
  const label = t(`vision.level.${l}`);
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full border ${LEVEL_COLORS[l] || "border-stone-600 text-stone-400"}`}>
      {label === `vision.level.${l}` ? `Level ${l}` : label}
    </span>
  );
}
