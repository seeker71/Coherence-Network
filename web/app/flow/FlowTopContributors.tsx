import Link from "next/link";

type Row = { contributorId: string; count: number; name: string };

type Props = { rows: Row[] };

function countLabel(value: number): string {
  return `${value} ${value === 1 ? "linked moment" : "linked moments"}`;
}

export function FlowTopContributors({ rows }: Props) {
  return (
    <section className="rounded border p-4 space-y-2">
      <h2 className="font-semibold">People Showing Up Most Often</h2>
      <p className="text-sm text-muted-foreground">
        Useful when you want to see who already has context around the ideas in this view.
      </p>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">No linked people are visible yet.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {rows.map((row) => (
            <li key={row.contributorId} className="flex items-center justify-between gap-3">
              <Link
                href={`/contributors?contributor_id=${encodeURIComponent(row.contributorId)}`}
                className="underline hover:text-foreground"
              >
                {row.name}
              </Link>
              <span className="text-muted-foreground">{countLabel(row.count)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
