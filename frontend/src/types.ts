export type User = { id: number; username: string; email: string; date_joined: string };

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
