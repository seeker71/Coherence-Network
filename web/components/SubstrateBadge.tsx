// SubstrateBadge — every page reveals what cells compose it.
//
// A small ⋄ in the bottom-right of every page. Click to expand a panel
// showing the page's ARTIFACT cell (NodeID + Blueprint) and structural
// twins (other pages whose Blueprint matches). Backed by
// GET /api/substrate/page?route=<pathname>.
//
// The panel is honest about absence: if the page file isn't yet an
// ARTIFACT cell in the substrate, it says so quietly instead of pretending
// the body knows itself when it doesn't.

"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { getApiBase } from "@/lib/api";
import { useT } from "@/components/MessagesProvider";

type NodeID = {
  package: number;
  level: number;
  type: number;
  instance: number;
};

type Cell = {
  cell_id: number;
  name: string;
  domain: string;
  blueprint: NodeID;
  source_path: string | null;
};

type PageSubstrate = {
  route: string;
  source_path: string | null;
  in_substrate: boolean;
  source: Cell | null;
  twins: Cell[];
  twins_count: number;
  twins_kind: string | null;
  kind: string | null;
  note: string | null;
};

function nodeId(n: NodeID | null | undefined): string {
  if (!n) return "—";
  return `@${n.package}.${n.level}.${n.type}.${n.instance}`;
}

export function SubstrateBadge() {
  const pathname = usePathname();
  const t = useT();
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<PageSubstrate | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Reset on route change. Lazy fetch — only when the badge is opened.
    setData(null);
    setError(null);
    setOpen(false);
  }, [pathname]);

  async function load() {
    if (data || loading) return;
    setLoading(true);
    try {
      const API = getApiBase();
      const res = await fetch(
        `${API}/api/substrate/page?route=${encodeURIComponent(pathname || "/")}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        setError(`HTTP ${res.status}`);
      } else {
        setData((await res.json()) as PageSubstrate);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "fetch failed");
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) void load();
  }

  return (
    <div className="fixed bottom-4 right-4 z-40 print:hidden">
      {open && (
        <div className="mb-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-border/50 bg-card/95 p-3 text-xs shadow-lg backdrop-blur-sm">
          <div className="mb-2 flex items-baseline justify-between gap-2">
            <span className="font-mono text-muted-foreground">substrate</span>
            <span className="text-muted-foreground/70">{pathname || "/"}</span>
          </div>

          {loading && (
            <div className="text-muted-foreground">sensing…</div>
          )}

          {error && (
            <div className="text-amber-300/90">cannot reach substrate: {error}</div>
          )}

          {data && !data.source_path && (
            <div className="text-muted-foreground">
              {data.note || "no page resolves for this route"}
            </div>
          )}

          {data && data.source_path && !data.in_substrate && (
            <div className="space-y-1">
              <div>
                <span className="text-muted-foreground">source: </span>
                <span className="font-mono break-all">{data.source_path}</span>
              </div>
              <div className="text-muted-foreground/90">
                {data.note || "not yet ingested"}
              </div>
            </div>
          )}

          {data && data.source && (
            <div className="space-y-2">
              <div>
                <span className="text-muted-foreground">source: </span>
                <span className="font-mono break-all">{data.source.source_path || data.source.name}</span>
              </div>
              <div>
                <span className="text-muted-foreground">blueprint: </span>
                <span className="font-mono text-emerald-300/90">{nodeId(data.source.blueprint)}</span>
                <span className="text-muted-foreground/70"> · domain {data.source.domain}</span>
              </div>
              {data.twins_count > 0 ? (
                <div>
                  <div className="mb-1 text-muted-foreground">
                    .{data.twins_kind || "?"} kin in the substrate ({data.twins_count}
                    {data.twins_count >= 24 ? "+" : ""}):
                  </div>
                  <ul className="space-y-0.5 max-h-40 overflow-y-auto">
                    {data.twins.slice(0, 12).map((t) => (
                      <li
                        key={t.cell_id}
                        className="font-mono text-foreground/80 truncate"
                        title={t.source_path || t.name}
                      >
                        · {t.source_path || t.name}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="text-muted-foreground">
                  no kin of this kind yet — this cell stands alone in the body.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={toggle}
        aria-label={t("substrate.footprintAria")}
        title={t("substrate.footprintTooltip")}
        className={`flex h-8 w-8 items-center justify-center rounded-full border border-border/40 bg-card/60 text-base text-muted-foreground shadow-sm transition-colors hover:text-foreground hover:border-border/80 ${
          open ? "text-foreground border-border/80" : ""
        }`}
      >
        <span aria-hidden>⋄</span>
      </button>
    </div>
  );
}

export default SubstrateBadge;
