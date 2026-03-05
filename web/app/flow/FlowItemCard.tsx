import Link from "next/link";
import { getApiBase } from "@/lib/api";
import type { FlowItem } from "./types";
import { statLabel, toBranchHref, toRepoHref } from "./utils";

type Props = { item: FlowItem };

export function FlowItemCard({ item }: Props) {
  return (
    <article className="rounded border p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">
          <Link href={`/ideas/${encodeURIComponent(item.idea_id)}`} className="hover:underline">
            {item.idea_name}
          </Link>
        </h2>
        <span className="text-xs text-muted-foreground">{item.idea_id}</span>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded border px-2 py-1">spec: {item.chain.spec}</span>
        <span className="rounded border px-2 py-1">process: {item.chain.process}</span>
        <span className="rounded border px-2 py-1">implementation: {item.chain.implementation}</span>
        <span className="rounded border px-2 py-1">validation: {item.chain.validation}</span>
        <span className="rounded border px-2 py-1">contributors: {item.chain.contributors}</span>
        <span className="rounded border px-2 py-1">contributions: {item.chain.contributions}</span>
        <span className="rounded border px-2 py-1">assets: {item.chain.assets}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        blocker {item.interdependencies.blocking_stage ?? "none"} | unblock priority{" "}
        {item.interdependencies.unblock_priority_score.toFixed(2)} | idea value gap{" "}
        {item.idea_signals.value_gap.toFixed(2)} | confidence {item.idea_signals.confidence.toFixed(2)}
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 text-sm">
        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Spec + Process</p>
          <p className="text-muted-foreground">
            specs {item.spec.count} ({statLabel(item.spec.tracked)}) | evidence {item.process.evidence_count} ({statLabel(item.process.tracked)})
          </p>
          <p className="text-muted-foreground">
            spec_ids{" "}
            {item.spec.spec_ids.length > 0
              ? item.spec.spec_ids.slice(0, 8).map((specId, idx) => (
                  <span key={specId}>
                    {idx > 0 ? ", " : ""}
                    <Link href={`/specs/${encodeURIComponent(specId)}`} className="underline hover:text-foreground">
                      {specId}
                    </Link>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            task_ids{" "}
            {item.process.task_ids.length > 0
              ? item.process.task_ids.slice(0, 8).map((taskId, idx) => (
                  <span key={taskId}>
                    {idx > 0 ? ", " : ""}
                    <Link href={`/tasks?task_id=${encodeURIComponent(taskId)}`} className="underline hover:text-foreground">
                      {taskId}
                    </Link>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            threads{" "}
            {item.process.thread_branches.length > 0
              ? item.process.thread_branches.slice(0, 4).map((branch, idx) => (
                  <span key={branch}>
                    {idx > 0 ? ", " : ""}
                    <a href={toBranchHref(branch)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                      {branch}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            source_files{" "}
            {item.process.source_files.length > 0
              ? item.process.source_files.slice(0, 6).map((filePath, idx) => (
                  <span key={filePath}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={toRepoHref(filePath)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                    >
                      {filePath}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
        </div>

        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Implementation + Contribution</p>
          <p className="text-muted-foreground">
            lineage_links {item.implementation.lineage_link_count} ({statLabel(item.implementation.tracked)}) | runtime_events {item.implementation.runtime_events_count}
          </p>
          <p className="text-muted-foreground">
            runtime_ms {item.implementation.runtime_total_ms.toFixed(2)} | runtime_cost {item.implementation.runtime_cost_estimate.toFixed(6)}
          </p>
          <p className="text-muted-foreground">
            usage_events {item.contributions.usage_events_count} | measured_value {item.contributions.measured_value_total.toFixed(2)}
          </p>
          <p className="text-muted-foreground">
            registry_contributions {item.contributions.registry_contribution_count} | registry_cost {item.contributions.registry_total_cost.toFixed(2)}
          </p>
          <p className="text-muted-foreground">
            assets {item.assets.count} ({statLabel(item.assets.tracked)})
          </p>
          <p className="text-muted-foreground">
            lineage_ids{" "}
            {item.implementation.lineage_ids.length > 0
              ? item.implementation.lineage_ids.slice(0, 6).map((lineageId, idx) => (
                  <span key={lineageId}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={`${getApiBase()}/api/value-lineage/links/${encodeURIComponent(lineageId)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                    >
                      {lineageId}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            implementation_refs{" "}
            {item.implementation.implementation_refs.length > 0
              ? item.implementation.implementation_refs.slice(0, 6).map((ref, idx) => (
                  <span key={ref}>
                    {idx > 0 ? ", " : ""}
                    <a href={toRepoHref(ref)} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                      {ref}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
        </div>

        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Validation</p>
          <p className="text-muted-foreground">
            local pass {item.validation.local.pass} | ci pass {item.validation.ci.pass} | deploy pass {item.validation.deploy.pass} | e2e pass {item.validation.e2e.pass}
          </p>
          <p className="text-muted-foreground">
            phase_gate pass {item.validation.phase_gate.pass_count} | blocked {item.validation.phase_gate.blocked_count}
          </p>
          <p className="text-muted-foreground">
            public_endpoints{" "}
            {item.validation.public_endpoints.length > 0
              ? item.validation.public_endpoints.slice(0, 5).map((endpoint, idx) => (
                  <span key={endpoint}>
                    {idx > 0 ? ", " : ""}
                    <a href={endpoint} target="_blank" rel="noopener noreferrer" className="underline hover:text-foreground">
                      {endpoint}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
        </div>

        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Contributors</p>
          <p className="text-muted-foreground">
            unique {item.contributors.total_unique} ({statLabel(item.contributors.tracked)})
          </p>
          <p className="text-muted-foreground">registry_ids {item.contributors.registry_ids.slice(0, 5).join(", ") || "-"}</p>
          <ul className="space-y-1 text-muted-foreground">
            {Object.entries(item.contributors.by_role)
              .slice(0, 8)
              .map(([role, ids]) => (
                <li key={role}>
                  {role}:{" "}
                  {ids.length > 0
                    ? ids.slice(0, 5).map((contributorId, idx) => (
                        <span key={`${role}-${contributorId}`}>
                          {idx > 0 ? ", " : ""}
                          <Link
                            href={`/contributors?contributor_id=${encodeURIComponent(contributorId)}`}
                            className="underline hover:text-foreground"
                          >
                            {contributorId}
                          </Link>
                        </span>
                      ))
                    : "-"}
                </li>
              ))}
          </ul>
        </div>
      </div>
    </article>
  );
}
