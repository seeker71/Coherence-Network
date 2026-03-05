import Link from "next/link";

type Row = { contributorId: string; count: number; name: string };

type Props = { rows: Row[] };

export function FlowTopContributors({ rows }: Props) {
  return (
    <section className="rounded border p-4 space-y-2">
      <h2 className="font-semibold">Top Contributors by Contribution Count</h2>
      <ul className="space-y-1 text-sm">
        {rows.map((row) => (
          <li key={row.contributorId} className="flex justify-between">
            <span>
              <Link
                href={`/contributors?contributor_id=${encodeURIComponent(row.contributorId)}`}
                className="underline hover:text-foreground"
              >
                {row.name}
              </Link>
            </span>
            <span className="text-muted-foreground">{row.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
