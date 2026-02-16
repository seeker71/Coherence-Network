import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getApiBase } from "@/lib/api";

export default function Home() {
  const apiUrl = getApiBase();
  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-8">
      <h1 className="text-3xl font-bold mb-4">Coherence Network</h1>
      <p className="text-gray-600 mb-6">
        Open Source Contribution Intelligence
      </p>
      <div className="flex flex-wrap gap-4">
        <Button asChild>
          <Link href="/search">Search projects</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/import">Import stack</Link>
        </Button>
        <Button asChild variant="outline">
          <a
            href={`${apiUrl}/docs`}
            target="_blank"
            rel="noopener noreferrer"
          >
            API Docs
          </a>
        </Button>
        <Button asChild variant="outline">
          <Link href="/api-health">API Health</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/friction">Friction Ledger</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/gates">Gate Status</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/portfolio">Portfolio Cockpit</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/ideas">Ideas</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/specs">Specs</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/usage">Usage</Link>
        </Button>
      </div>
    </main>
  );
}
