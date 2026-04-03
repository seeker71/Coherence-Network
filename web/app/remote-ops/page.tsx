"use client";

import Link from "next/link";
import { ControlsSection } from "./controls-section";
import { DeploymentUptimeSection } from "./deployment-uptime-section";
import { QueuePipelineSection } from "./queue-pipeline-section";
import { useRemoteOps } from "./use-remote-ops";

export default function RemoteOpsPage() {
  const ops = useRemoteOps();
  const pendingRows = ops.pending?.tasks ?? [];
  const pendingTotal = ops.pending?.total ?? 0;
  const activeCount = ops.pipeline?.running?.length ?? 0;
  const pendingCount = ops.pipeline?.pending?.length ?? 0;

  return (
    <main className="min-h-screen p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex flex-wrap gap-3 text-sm">
        <Link href="/" className="text-muted-foreground hover:text-foreground">
          ← Coherence Network
        </Link>
        <Link href="/agent" className="text-muted-foreground hover:text-foreground">
          Agent
        </Link>
        <Link href="/tasks" className="text-muted-foreground hover:text-foreground">
          Tasks
        </Link>
        <Link href="/remote-ops" className="text-muted-foreground hover:text-foreground">
          Remote Ops
        </Link>
        <Link href="/gates" className="text-muted-foreground hover:text-foreground">
          Gates
        </Link>
        <a
          href={`${ops.API_URL}/docs`}
          className="text-muted-foreground hover:text-foreground"
          target="_blank"
          rel="noopener noreferrer"
        >
          API Docs
        </a>
      </div>

      <section className="space-y-3 border rounded-md p-4">
        <h1 className="text-2xl font-bold">Remote Ops</h1>
        <p className="text-muted-foreground">
          Work from anywhere: verify public deploy status, monitor queue, and dispatch Codex on the
          deployed API.
        </p>
        <p className="text-xs text-muted-foreground">
          Current API target: <span className="font-mono">{ops.API_URL}</span>
        </p>
        {ops.tokenProvided ? (
          <p className="text-xs text-muted-foreground">
            Execute token is provided for execute endpoints.
          </p>
        ) : (
          <p className="text-xs text-destructive">
            Execute token is not set. If execution is protected, enter AGENT_EXECUTE_TOKEN before
            running.
          </p>
        )}
      </section>

      <DeploymentUptimeSection
        health={ops.health}
        proxy={ops.proxy}
        deploy={ops.deploy}
      />

      <ControlsSection
        executeToken={ops.executeToken}
        setExecuteToken={ops.setExecuteToken}
        executor={ops.executor}
        setExecutor={ops.setExecutor}
        taskType={ops.taskType}
        setTaskType={ops.setTaskType}
        modelOverride={ops.modelOverride}
        setModelOverride={ops.setModelOverride}
        forcePaid={ops.forcePaid}
        setForcePaid={ops.setForcePaid}
        runAsPrThread={ops.runAsPrThread}
        setRunAsPrThread={ops.setRunAsPrThread}
        autoMergePr={ops.autoMergePr}
        setAutoMergePr={ops.setAutoMergePr}
        waitPublic={ops.waitPublic}
        setWaitPublic={ops.setWaitPublic}
        direction={ops.direction}
        setDirection={ops.setDirection}
        status={ops.status}
        error={ops.error}
        runningMessage={ops.runningMessage}
        onCreate={ops.onCreate}
        runPickUp={ops.runPickUp}
      />

      <QueuePipelineSection
        pendingRows={pendingRows}
        pendingTotal={pendingTotal}
        pendingCount={pendingCount}
        activeCount={activeCount}
        runTask={ops.runTask}
        status={ops.status}
      />
    </main>
  );
}
