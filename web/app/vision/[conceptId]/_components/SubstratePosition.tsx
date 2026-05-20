// SubstratePosition — surface this concept's structural coordinate in
// the body's content-addressed lattice. The vision page carries the
// story; this panel carries the position. Both are the same cell,
// read through different surfaces.
//
// The visitor lands at /vision/lc-pulse for the felt meaning. From
// here they can step sideways into /substrate/concept/lc-pulse for
// the cell's full structural identity, or into /substrate/form pre-
// loaded with this cell, to ask the lattice questions directly.
//
// Edge wiring: this component is the door the page-comment in
// site_header.tsx names — "deeper surfaces reach themselves through
// the pages that already use them." The vision page was already
// using the cell; this is the surface that lets the visitor see it.

import Link from "next/link";
import { getApiBase } from "@/lib/api";

type NodeID = {
  package: number;
  level: number;
  type: number;
  instance: number;
};

type CellResponse = {
  cell_id: number;
  name: string;
  domain: string;
  blueprint: NodeID;
};

type EquivalentResponse = {
  blueprint: NodeID;
  cells: Array<{ name: string; domain: string }>;
};

function formatNodeId(nid: NodeID): string {
  return `@${nid.package}.${nid.level}.${nid.type}.${nid.instance}`;
}

async function fetchCell(conceptId: string): Promise<CellResponse | null> {
  try {
    const res = await fetch(
      `${getApiBase()}/api/substrate/cell/concept/${encodeURIComponent(conceptId)}`,
      { next: { revalidate: 60 } },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function fetchEquivalents(
  conceptId: string,
): Promise<EquivalentResponse | null> {
  try {
    const res = await fetch(
      `${getApiBase()}/api/substrate/equivalent/concept/${encodeURIComponent(conceptId)}`,
      { next: { revalidate: 60 } },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function SubstratePosition({
  conceptId,
}: {
  conceptId: string;
}) {
  const [cell, equivalents] = await Promise.all([
    fetchCell(conceptId),
    fetchEquivalents(conceptId),
  ]);

  // If the cell isn't in the substrate yet, surface nothing. The vision
  // story carries the meaning; the structural position is additive, not
  // load-bearing.
  if (!cell) return null;

  const cellRef = `@concept(${conceptId})`;
  const nodeIdStr = formatNodeId(cell.blueprint);
  const equivalentCount = equivalents?.cells.length ?? 0;

  return (
    <section
      aria-labelledby="substrate-position-heading"
      className="rounded-2xl border border-amber-500/20 bg-stone-900/60 p-5 space-y-3"
    >
      <h2
        id="substrate-position-heading"
        className="text-sm font-semibold text-amber-300/90"
      >
        Structural position
      </h2>
      <p className="text-xs text-stone-400 leading-relaxed">
        This concept lives in the body's content-addressed lattice. Two cells
        with the same Blueprint NodeID share structural identity regardless of
        name — recognition by coordinate, not vocabulary.
      </p>
      <dl className="grid gap-2 text-sm sm:grid-cols-[auto_1fr]">
        <dt className="text-stone-400">Blueprint</dt>
        <dd className="font-mono text-amber-200/90">{nodeIdStr}</dd>
        <dt className="text-stone-400">Structural equivalents</dt>
        <dd className="text-stone-200">
          {equivalentCount === 0
            ? "none currently"
            : `${equivalentCount} cell${equivalentCount === 1 ? "" : "s"} share this Blueprint`}
        </dd>
      </dl>
      <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs pt-2">
        <Link
          href={`/substrate/concept/${conceptId}`}
          className="text-amber-400/90 hover:text-amber-300 transition-colors"
        >
          → Full cell page
        </Link>
        <Link
          href={`/substrate/form?cell=${encodeURIComponent(cellRef)}`}
          className="text-amber-400/90 hover:text-amber-300 transition-colors"
        >
          → Ask the lattice (Form playground)
        </Link>
        <Link
          href="/substrate"
          className="text-stone-400 hover:text-amber-300 transition-colors"
        >
          → All cells
        </Link>
      </div>
    </section>
  );
}
