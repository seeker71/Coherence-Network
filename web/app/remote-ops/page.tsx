"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// /remote-ops has been consolidated into /nodes
// Queue, controls, and deployment status are now available at /nodes
export default function RemoteOpsPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/nodes");
  }, [router]);
  return (
    <main className="min-h-screen flex items-center justify-center">
      <p className="text-muted-foreground text-sm">Redirecting to Nodes…</p>
    </main>
  );
}
