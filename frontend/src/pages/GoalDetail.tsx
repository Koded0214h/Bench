import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { Escalation, Goal, Machine, Paginated, Spend, Task } from "../types";

const TASK_PILL: Record<string, string> = {
  done: "ok", running: "run", dispatching: "run", quarantine: "run", review: "run",
  escalated: "warn", denied: "bad", rejected: "bad", failed: "bad",
};
const GOAL_PILL: Record<string, string> = {
  done: "ok", running: "run", planning: "run", pending: "run", blocked: "warn", failed: "bad",
};

export function GoalDetail() {
  const { id } = useParams();
  const [goal, setGoal] = useState<Goal | null>(null);
  const [escs, setEscs] = useState<Escalation[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [spend, setSpend] = useState<Spend | null>(null);
  const [chain, setChain] = useState<{ ok: boolean; checked: number } | null>(null);

  const load = useCallback(async () => {
    const [g, e, m, s, v] = await Promise.all([
      api<Goal>(`/goals/${id}/`),
      api<Paginated<Escalation>>(`/escalations/?pending=1`),
      api<Paginated<Machine>>(`/machines/?live=1`),
      api<Spend>(`/spend`),
      api<{ ok: boolean; checked: number }>(`/audit/verify`),
    ]);
    setGoal(g);
    setEscs(e.results.filter((x) => g.tasks.some((t) => t.id === x.task_id)));
    setMachines(m.results.filter((x) => g.tasks.some((t) => t.id === x.task_id)));
    setSpend(s);
    setChain(v);
  }, [id]);

  useEffect(() => {
    load().catch(() => {});
    const running = goal && ["running", "planning", "pending"].includes(goal.status);
    const t = setInterval(() => load().catch(() => {}), running ? 2000 : 8000);
    return () => clearInterval(t);
  }, [load, goal?.status]);

  async function resolve(escId: string, approved: boolean) {
    await api(`/escalations/${escId}/resolve/`, { method: "POST", body: { approved } });
    load();
  }

  if (!goal) return <p className="muted">…</p>;

  const goalSpend = Object.entries(spend?.tasks ?? {})
    .filter(([tid]) => goal.tasks.some((t) => t.id === tid) || tid === goal.id || tid === "__plan__")
    .reduce((sum, [, v]) => sum + v.total_usd, 0);

  return (
    <>
      <div className="between" style={{ marginBottom: 16 }}>
        <div>
          <Link to="/" className="small">← all goals</Link>
          <h2 style={{ margin: "6px 0 0", textTransform: "none", letterSpacing: 0, fontSize: 18, color: "var(--fg)" }}>
            {goal.text}
          </h2>
          <div className="muted small mono">{goal.id}</div>
        </div>
        <span className={`pill ${GOAL_PILL[goal.status] || ""}`}>{goal.status}</span>
      </div>

      {escs.length > 0 && (
        <div className="panel">
          <h2>Needs a human</h2>
          {escs.map((e) => (
            <div className="esc" key={e.id}>
              <div className="small mono muted">task {e.task_id}</div>
              <div style={{ margin: "4px 0 10px" }}>{e.reason}</div>
              <div className="row">
                <button onClick={() => resolve(e.id, true)}>Approve</button>
                <button className="danger" onClick={() => resolve(e.id, false)}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="panel">
        <h2>Tasks</h2>
        {goal.tasks.length === 0 && <p className="muted">the CEO agent is decomposing the goal…</p>}
        {goal.tasks.map((t) => (
          <TaskView key={t.id} t={t} />
        ))}
      </div>

      {machines.length > 0 && (
        <div className="panel">
          <h2>Live machines</h2>
          {machines.map((m) => (
            <div key={m.id} className="between small" style={{ padding: "6px 0" }}>
              <span className="mono">{m.kind} · {m.id.slice(0, 40)}…</span>
              <span>
                {m.stream_url && <a href={m.stream_url} target="_blank" rel="noreferrer">stream</a>}
                {Object.entries(m.preview_urls || {}).map(([p, u]) => (
                  <a key={p} href={u} target="_blank" rel="noreferrer" style={{ marginLeft: 8 }}>:{p}</a>
                ))}
              </span>
            </div>
          ))}
        </div>
      )}

      <div className="panel">
        <h2>Run</h2>
        <div className="kv">
          <span className="k">spend</span><span className="mono">${goalSpend.toFixed(4)}</span>
          <span className="k">audit chain</span>
          <span className={chain?.ok ? "" : "err"}>
            {chain ? (chain.ok ? `intact (${chain.checked} events)` : "BROKEN") : "…"}
          </span>
          {goal.notes && (<><span className="k">CEO notes</span><span>{goal.notes}</span></>)}
        </div>
      </div>
    </>
  );
}

function TaskView({ t }: { t: Task }) {
  return (
    <div className="task">
      <div className="head">
        <span className="cap">[{t.capability}]</span>
        <strong>{t.title}</strong>
        <span className={`pill ${TASK_PILL[t.status] || ""}`}>{t.status}</span>
        {t.attempts > 1 && <span className="pill">{t.attempts} attempts</span>}
      </div>
      <div className="muted small">{t.instructions}</div>

      {t.result && (
        <div className="small" style={{ marginTop: 8 }}>
          <div className="muted">{t.result.summary}</div>
          <div className="stack" style={{ gap: 8, marginTop: 6 }}>
            {t.result.artifacts.map((a, i) => (
              <ArtifactView key={i} a={a} />
            ))}
          </div>
        </div>
      )}

      {t.quarantine && !t.quarantine.skipped && (
        <div className="small" style={{ marginTop: 8 }}>
          <span className={`pill ${t.quarantine.passed ? "ok" : "bad"}`}>
            quarantine {t.quarantine.passed ? "pass" : "fail"}
          </span>
          {t.quarantine.checks.map((c, i) => (
            <div key={i} className={`checkline ${c.passed ? "ok" : "bad"}`}>{c.name} — {c.detail}</div>
          ))}
          {t.quarantine.failure && <div className="err small">{t.quarantine.failure}</div>}
        </div>
      )}

      {t.review && (
        <div className="small" style={{ marginTop: 8 }}>
          <span className={`pill ${t.review.verdict === "ACCEPT" ? "ok" : t.review.verdict === "ESCALATE" ? "warn" : "bad"}`}>
            review {t.review.verdict}
          </span>{" "}
          <span className="muted">{t.review.reason}</span>
        </div>
      )}
    </div>
  );
}

const IMAGE_EXT = /\.(png|jpe?g|gif|webp|svg|bmp)(\?|#|$)/i;

function ArtifactView({ a }: { a: NonNullable<Task["result"]>["artifacts"][number] }) {
  const isUrl = a.value.startsWith("http");
  const looksLikeImage = a.kind === "image" || (isUrl && IMAGE_EXT.test(a.value)) || IMAGE_EXT.test(a.value);
  const content = typeof a.meta?.content === "string" ? a.meta.content : null;
  const b64 = typeof a.meta?.content_b64 === "string" ? a.meta.content_b64 : null;
  const mime = typeof a.meta?.mime === "string" ? a.meta.mime : "application/octet-stream";
  const dataUrl = b64 ? `data:${mime};base64,${b64}` : null;

  // Embedded bytes beat a live sandbox URL — that URL dies with the sandbox,
  // this survives in the database.
  if (dataUrl && looksLikeImage) {
    return (
      <div>
        <div className="muted mono" style={{ marginBottom: 4 }}>[image] {a.label || a.value}</div>
        <a href={dataUrl} download={a.value.split("/").pop()}>
          <img src={dataUrl} alt={a.label || "generated image"}
               style={{ maxWidth: 320, maxHeight: 240, borderRadius: 8, border: "1px solid var(--line)" }} />
        </a>
      </div>
    );
  }
  if (dataUrl) {
    return (
      <div className="mono">
        [{a.kind}] <a href={dataUrl} download={a.value.split("/").pop()}>{a.label || a.value} ↓</a>
      </div>
    );
  }

  if (looksLikeImage && isUrl) {
    return (
      <div>
        <div className="muted mono" style={{ marginBottom: 4 }}>
          [image] {a.label || a.value} <span className="warn">(live preview only — expires with the sandbox)</span>
        </div>
        <a href={a.value} target="_blank" rel="noreferrer">
          <img src={a.value} alt={a.label || "generated image"}
               style={{ maxWidth: 320, maxHeight: 240, borderRadius: 8, border: "1px solid var(--line)" }} />
        </a>
      </div>
    );
  }

  if (isUrl) {
    return (
      <div className="mono">
        [{a.kind}] {a.label}: <a href={a.value} target="_blank" rel="noreferrer">{a.value}</a>
      </div>
    );
  }

  if (content) {
    return (
      <details>
        <summary className="mono" style={{ cursor: "pointer" }}>
          [{a.kind}] {a.label || a.value}
        </summary>
        <pre style={{
          whiteSpace: "pre-wrap", background: "var(--bg)", border: "1px solid var(--line)",
          borderRadius: 8, padding: 10, marginTop: 6, maxHeight: 320, overflow: "auto",
        }}>
          {content.slice(0, 6000)}
        </pre>
      </details>
    );
  }

  return (
    <div className="mono">
      [{a.kind}] {a.label}: {a.value}
    </div>
  );
}
