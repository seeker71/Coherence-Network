"use client";

import { useRemoteOps } from "@/app/remote-ops/use-remote-ops";
import { ControlsSection } from "@/app/remote-ops/controls-section";
import { QueuePipelineSection } from "@/app/remote-ops/queue-pipeline-section";
import { DeploymentUptimeSection } from "@/app/remote-ops/deployment-uptime-section";

export function RemoteControlSection() {
  const ops = useRemoteOps();
  const pendingRows = ops.pending?.tasks ?? [];
  const pendingTotal = ops.pending?.total ?? 0;
  const activeCount = ops.pipeline?.running?.length ?? 0;
  const pendingCount = ops.pipeline?.pending?.length ?? 0;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-border/30 bg-gradient-to-b from-card/60 to-card/30 p-6 space-y-3">
        <h2 className="text-xl font-semibold">API Status</h2>
        <p className="text-xs text-muted-foreground font-mono">
          Target: {ops.API_URL}
        </p>
        {ops.tokenProvided ? (
          <p className="text-xs text-green-600 dark:text-green-400">Execute token provided.</p>
        ) : (
          <p className="text-xs text-amber-600 dark:text-amber-400">
            No execute token set — protected endpoints will be denied.
          </p>
        )}
      </section>

      <DeploymentUptimeSection health={ops.health} proxy={ops.proxy} deploy={ops.deploy} />

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
    </div>
  );
}
