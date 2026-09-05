export type User = { id: number; username: string; email: string; date_joined: string };

export interface Company {
  id: string;
  name: string;
  purpose: string;
  focus: string;
  autonomy: "ask" | "auto";
  created_at: string;
  updated_at: string;
}

export interface Agent {
  id: string;
  kind: "management" | "worker";
  role: string;
  status: "active" | "dismissed";
  capability: string | null;
  task_id: string | null;
  created_at: string;
  dismissed_at: string | null;
}

export interface AuditEvent {
  seq?: number;
  event_id?: string;
  ts: string;
  kind: string;
  actor?: string | null;
  task_id?: string | null;
  worker_id?: string | null;
  machine_id?: string | null;
  payload?: Record<string, unknown>;
}

export interface PolicyRule {
  name: string;
  match: Record<string, unknown>;
  effect: string;
  reason: string | null;
  enabled: boolean;
  priority: number;
}

export type TaskStatus =
  | "created" | "dispatching" | "denied" | "escalated" | "running"
  | "quarantine" | "review" | "done" | "rejected" | "failed";

export interface Task {
  id: string;
  goal_id: string;
  title: string;
  capability: "sandbox" | "browser" | "desktop";
  instructions: string;
  success_criteria: string[];
  depends_on: string[];
  tool: string | null;
  status: TaskStatus;
  attempts: number;
  result: {
    status: string;
    summary: string;
    artifacts: { kind: string; value: string; label: string; meta?: Record<string, unknown> }[];
    steps: number;
    usage: { input_tokens: number; output_tokens: number };
  } | null;
  review: { verdict: string; reason: string } | null;
  quarantine: {
    passed: boolean;
    skipped: boolean;
    checks: { name: string; passed: boolean; detail: string }[];
    failure: string | null;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface Goal {
  id: string;
  owner: string | null;
  company_id: string | null;
  text: string;
  status: "pending" | "planning" | "running" | "done" | "failed" | "blocked";
  notes: string;
  error: string;
  created_at: string;
  updated_at: string;
  tasks: Task[];
}

export interface Escalation {
  id: string;
  task_id: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export interface Machine {
  id: string;
  kind: string;
  status: string;
  task_id: string | null;
  stream_url: string | null;
  preview_urls: Record<string, string>;
}

export interface Spend {
  total_usd: number;
  tasks: Record<string, { total_usd: number; by_category: Record<string, number>; charges: number }>;
}

export interface Paginated<T> { count: number; results: T[] }
