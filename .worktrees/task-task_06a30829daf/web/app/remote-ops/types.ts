export type HealthResponse = {
  status: string;
  uptime_human: string;
  uptime_seconds: number;
  version: string;
  timestamp: string;
  started_at: string;
};

export type DeployContract = {
  result?: string;
  repository?: string;
  branch?: string;
  api_base?: string;
  web_base?: string;
  failing_checks?: string[];
  warnings?: string[];
  checks?: Array<{ name?: string; ok?: boolean; status_code?: number; error?: string }>;
};

export type PipelineTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  created_at?: string;
  updated_at?: string;
};

export type PipelineStatus = {
  running: PipelineTask[];
  pending: PipelineTask[];
};

export type PendingTaskList = {
  tasks: PipelineTask[];
  total: number;
};

export type RemoteActionResponse = {
  ok: boolean;
  task_id?: string;
  picked?: boolean;
  task?: PipelineTask;
  reason?: string;
  detail?: string;
};

export type HealthProxyResponse = {
  api?: HealthResponse;
  web?: {
    status: string;
    uptime_human: string;
    uptime_seconds: number;
    started_at: string;
    updated_at?: string;
  };
  checked_at?: string;
  error?: string;
};
