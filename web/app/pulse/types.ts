// Response shapes for the Pulse Monitor API. Must stay in sync with
// pulse/pulse_app/models.py. These are read-only — no Zod validation
// needed because the monitor is a controlled internal service.

export type BreathStatus = "breathing" | "strained" | "silent" | "unknown";
export type Severity = "strained" | "silent";

export type OrganNow = {
  name: string;
  label: string;
  description: string;
  status: BreathStatus;
  latency_ms: number | null;
  last_sample_at: string | null;
  detail: string | null;
};

export type OngoingSilence = {
  id: number;
  organ: string;
  started_at: string;
  severity: Severity;
  duration_seconds: number;
};

export type PulseNow = {
  overall: BreathStatus;
  checked_at: string;
  witness_started_at: string;
  organs: OrganNow[];
  ongoing_silences: OngoingSilence[];
};

export type DailyBar = {
  date: string;
  status: BreathStatus;
  samples: number;
  failures: number;
};

export type OrganHistory = {
  name: string;
  label: string;
  description: string;
  uptime_pct: number;
  daily: DailyBar[];
};

export type PulseHistory = {
  days: number;
  generated_at: string;
  organs: OrganHistory[];
};

export type Silence = {
  id: number;
  organ: string;
  organ_label: string;
  started_at: string;
  ended_at: string | null;
  duration_seconds: number;
  severity: Severity;
  note: string | null;
};

export type PulseSilences = {
  days: number;
  generated_at: string;
  silences: Silence[];
};
