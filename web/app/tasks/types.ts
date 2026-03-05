export type AgentTask = {
  id: string;
  status: string;
  task_type: string;
  direction: string;
  model?: string;
  output?: string | null;
  current_step?: string | null;
  context?: Record<string, unknown> | null;
  claimed_by?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type RuntimeEvent = {
  id: string;
  recorded_at?: string;
  endpoint: string;
  method?: string;
  status_code: number;
  idea_id?: string | null;
  origin_idea_id?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type TaskListResponse = {
  tasks?: AgentTask[];
  items?: AgentTask[];
  total?: number;
};

export type TaskLogResponse = {
  task_id: string;
  log?: string;
};

export type EvidenceIdeaRow = {
  ideaId: string;
  source: string;
};

export type EvidenceEventRow = {
  id: string;
  recordedAt?: string;
  endpoint: string;
  statusCode: number;
  trackingKind: string;
  finalStatus: string;
};
