"use client";

import dynamic from "next/dynamic";

const GLTFRenderer = dynamic(
  () => import("./GLTFRenderer").then((m) => m.GLTFRenderer),
  { ssr: false, loading: () => <div className="aspect-[16/10] rounded-xl bg-stone-900/50 animate-pulse" /> }
);

export function ModelViewer({ modelUrl, caption }: { modelUrl: string; caption?: string }) {
  return <GLTFRenderer modelUrl={modelUrl} caption={caption} />;
}
