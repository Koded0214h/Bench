import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import type { Goal, Paginated } from "../types";

const STATUS_PILL: Record<string, string> = {
  done: "ok", running: "run", planning: "run", pending: "run",
  blocked: "warn", failed: "bad",
};

export function Dashboard() {
  const nav = useNavigate();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const d = await api<Paginated<Goal>>("/goals/?limit=50");
      setGoals(d.results);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
    const anyRunning = goals.some((g) => ["running", "planning", "pending"].includes(g.status));
    const t = setInterval(load, anyRunning ? 2000 : 6000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [goals.map((g) => g.status).join()]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const g = await api<Goal>("/goals/", { method: "POST", body: { text, run: true } });
      setText("");
      await load();
      nav(`/goals/${g.id}`);
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : String(x));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="panel">
        <h2>New goal</h2>
        <form className="stack" onSubmit={create}>
          <textarea
            placeholder="e.g. Launch a landing page for our fintech tool and log the campaign in Salesforce"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="between">
            <span className="muted small">
              The CEO agent decomposes it, hires workers, and runs each task through policy → quarantine → review.
            </span>
            <button disabled={busy || text.trim().length < 8}>{busy ? "starting…" : "Run it"}</button>
          </div>
          {err && <div className="err">{err}</div>}
        </form>
      </div>

      <div className="panel">
        <h2>Your goals</h2>
        {goals.length === 0 && <p className="muted">nothing yet.</p>}
        {goals.map((g) => (
          <div className="goal-item" key={g.id}>
            <div className="between">
              <div className="t">
                <Link to={`/goals/${g.id}`}>{g.text}</Link>
              </div>
              <span className={`pill ${STATUS_PILL[g.status] || ""}`}>{g.status}</span>
            </div>
            <div className="muted small mono">
              {g.id} · {g.tasks.length} task(s) · {new Date(g.created_at).toLocaleString()}
              {g.error && <span style={{ color: "var(--bad)" }}> · {g.error.slice(0, 90)}</span>}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
