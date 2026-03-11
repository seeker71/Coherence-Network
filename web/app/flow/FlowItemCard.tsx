import Link from "next/link";
import { getApiBase } from "@/lib/api";
import { formatConfidence, formatDecimal, formatUsd, humanizeStatus } from "@/lib/humanize";
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
        Blocker {humanizeStatus(item.interdependencies.blocking_stage ?? "none")} | Unblock priority{" "}
        {formatDecimal(item.interdependencies.unblock_priority_score)} | Remaining upside {formatUsd(item.idea_signals.value_gap)} | Confidence{" "}
        {formatConfidence(item.idea_signals.confidence)}
      </p>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 text-sm">
        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Spec + Process</p>
          <p className="text-muted-foreground">
            Specs {item.spec.count} ({statLabel(item.spec.tracked)}) | Workflow evidence {item.process.evidence_count} ({statLabel(item.process.tracked)})
          </p>
          <p className="text-muted-foreground">
            Spec links{" "}
            {item.spec.spec_ids.length > 0
              ? item.spec.spec_ids.slice(0, 8).map((specId, idx) => (
                  <span key={specId}>
                    {idx > 0 ? ", " : ""}
                    <Link
                      href={`/specs/${encodeURIComponent(specId)}`}
                      className="underline hover:text-foreground"
                      title={`Spec ID: ${specId}`}
                    >
                      Spec {idx + 1}
                    </Link>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            Execution tasks{" "}
            {item.process.task_ids.length > 0
              ? item.process.task_ids.slice(0, 8).map((taskId, idx) => (
                  <span key={taskId}>
                    {idx > 0 ? ", " : ""}
                    <Link
                      href={`/tasks?task_id=${encodeURIComponent(taskId)}`}
                      className="underline hover:text-foreground"
                      title={`Task ID: ${taskId}`}
                    >
                      Task {idx + 1}
                    </Link>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            Branches{" "}
            {item.process.thread_branches.length > 0
              ? item.process.thread_branches.slice(0, 4).map((branch, idx) => (
                  <span key={branch}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={toBranchHref(branch)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                      title={branch}
                    >
                      Branch {idx + 1}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            Source files{" "}
            {item.process.source_files.length > 0
              ? item.process.source_files.slice(0, 6).map((filePath, idx) => (
                  <span key={filePath}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={toRepoHref(filePath)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                      title={filePath}
                    >
                      File {idx + 1}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
        </div>

        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Implementation + Contribution</p>
          <p className="text-muted-foreground">
            Lineage links {item.implementation.lineage_link_count} ({statLabel(item.implementation.tracked)}) | Runtime events{" "}
            {item.implementation.runtime_events_count}
          </p>
          <p className="text-muted-foreground">
            Runtime time {formatDecimal(item.implementation.runtime_total_ms, 0)} ms | Runtime cost{" "}
            {formatUsd(item.implementation.runtime_cost_estimate)}
          </p>
          <p className="text-muted-foreground">
            Usage events {item.contributions.usage_events_count} | Measured value {formatUsd(item.contributions.measured_value_total)}
          </p>
          <p className="text-muted-foreground">
            Team-record contributions {item.contributions.registry_contribution_count} | Team-record cost{" "}
            {formatUsd(item.contributions.registry_total_cost)}
          </p>
          <p className="text-muted-foreground">
            Assets {item.assets.count} ({statLabel(item.assets.tracked)})
          </p>
          <p className="text-muted-foreground">
            Lineage records{" "}
            {item.implementation.lineage_ids.length > 0
              ? item.implementation.lineage_ids.slice(0, 6).map((lineageId, idx) => (
                  <span key={lineageId}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={`${getApiBase()}/api/value-lineage/links/${encodeURIComponent(lineageId)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                      title={`Lineage ID: ${lineageId}`}
                    >
                      Record {idx + 1}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
          <p className="text-muted-foreground">
            Implementation files{" "}
            {item.implementation.implementation_refs.length > 0
              ? item.implementation.implementation_refs.slice(0, 6).map((ref, idx) => (
                  <span key={ref}>
                    {idx > 0 ? ", " : ""}
                    <a
                      href={toRepoHref(ref)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline hover:text-foreground"
                      title={ref}
                    >
                      File {idx + 1}
                    </a>
                  </span>
                ))
              : "-"}
          </p>
        </div>

        <div className="rounded border p-3 space-y-1">
          <p className="font-medium">Validation</p>
          <p className="text-muted-foreground">
            Local checks passed {item.validation.local.pass} | CI checks passed {item.validation.ci.pass} | Deploy checks passed{" "}
            {item.validation.deploy.pass} | End-to-end checks passed {item.validation.e2e.pass}
          </p>
          <p className="text-muted-foreground">
            Phase checks passed {item.validation.phase_gate.pass_count} | Blocked checks {item.validation.phase_gate.blocked_count}
          </p>
          <p className="text-muted-foreground">
            Public endpoints{" "}
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
            Unique contributors {item.contributors.total_unique} ({statLabel(item.contributors.tracked)})
          </p>
          <p className="text-muted-foreground">
            Team profiles {item.contributors.registry_ids.length > 0 ? `${Math.min(item.contributors.registry_ids.length, 5)} linked` : "-"}
          </p>
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
                            title={`Contributor ID: ${contributorId}`}
                          >
                            Contributor {idx + 1}
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
