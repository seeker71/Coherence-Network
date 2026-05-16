"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function WellnessRefresh() {
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch("/api/wellness?refresh=true", { cache: "no-store" });
      router.refresh();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <button
      onClick={handleRefresh}
      disabled={refreshing}
      className="rounded border border-stone-800/40 px-3 py-1 text-stone-400 hover:text-amber-300 hover:border-amber-500/30 transition-colors disabled:opacity-40"
    >
      {refreshing ? "Sensing..." : "Sense again"}
    </button>
  );
}
