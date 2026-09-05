import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api, ApiError } from "../../api";
import type { Escalation, Goal, Paginated, Spend } from "../../types";
import type { WsContext } from "./Workspace";

const RUNNING = ["running", "planning", "pending"];
const PILL: Record<string, string> = {
  done: "ok", running: "run", planning: "run", pending: "run", blocked: "warn", failed: "bad",
};

export function CompanyHome() {
  const { companyId, company } = useOutletContext<WsContext>();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [escs, setEscs] = useState<Escalation[]>([]);
  const [spend, setSpend] = useState<Spend | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function load() {
    try {
      const [g, e, s] = await Promise.all([
        api<Paginated<Goal>>(`/goals/?company=${companyId}&limit=100`),
        api<Paginated<Escalation>>(`/escalations/?pending=1`),
        api<Spend>("/spend"),
      ]);
      setGoals(g.results);
      const ids = new Set(g.results.flatMap((x) => x.tasks.map((t) => t.id)));
      setEscs(e.results.filter((x) => ids.has(x.task_id)));
      setSpend(s);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
    const anyRunning = goals.some((g) => RUNNING.includes(g.status));
    const t = setInterval(load, anyRunning ? 2500 : 7000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, goals.map((g) => g.status).join()]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api<Goal>("/goals/", { method: "POST", body: { text, company: companyId, run: true } });
      setText("");
      await load();
    } catch (x) {
      setErr(x instanceof ApiError ? x.message : String(x));
    } finally {
      setBusy(false);
    }
  }

  const active = goals.filter((g) => RUNNING.includes(g.status));
  const recent = goals.filter((g) => g.status === "done").slice(0, 4);
  const totalSpend = goals
    .flatMap((g) => [g.id, ...g.tasks.map((t) => t.id)])
    .reduce((sum, id) => sum + (spend?.tasks[id]?.total_usd ?? 0), 0);

  return (
    <>
      <div className="pg-head">
        <h1>{company?.name ?? "Company"}</h1>
        <p>{company?.purpose}</p>
      </div>

      <div className="goalbox">
        <h2>What should we get done?</h2>
        <form onSubmit={create}>
          <textarea
            placeholder="e.g. Ship a landing page for the new product and log the launch in Salesforce"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="row">
            <span className="hint">
              The CEO breaks it into tasks, hires a worker for each, and runs every one through
              policy → quarantine → review.
            </span>
            <button className="btn-teal" disabled={busy || text.trim().length < 8}>
              {busy ? "Starting…" : "Give it to the company"}
            </button>
          </div>
          {err && <div className="err" style={{ marginTop: 10 }}>{err}</div>}
        </form>
      </div>

      <div className="co-card-meta" style={{ margin: "0 2px 22px", gap: 20, fontSize: 12.5 }}>
        <span>{active.length} running</span>
        <span>{escs.length} waiting on you</span>
        <span>{goals.filter((g) => g.status === "done").length} completed</span>
        <span>${totalSpend.toFixed(2)} spent</span>
      </div>

      {escs.length > 0 && (
        <Section title="Waiting on you">
          <div className="rowlist">
            {escs.map((e) => (
              <Link className="r" to={`/c/${companyId}/decisions`} key={e.id}>
                <div>
                  <div className="t">{e.reason || "A worker needs a decision"}</div>
                  <div className="m">task {e.task_id}</div>
                </div>
                <span className="pill warn">review</span>
              </Link>
            ))}
          </div>
        </Section>
      )}

      <Section title="Current work" cta={<Link to={`/c/${companyId}/work`} className="small muted">All work →</Link>}>
        {active.length === 0 ? (
          <div className="empty">
            <h3>Nothing running</h3>
            <p>Give the company an objective above and it gets to work.</p>
          </div>
        ) : (
          <div className="rowlist">
            {active.map((g) => (
              <Link className="r" to={`/c/${companyId}/work/${g.id}`} key={g.id}>
                <div>
                  <div className="t">{g.text}</div>
                  <div className="m">
                    {g.tasks.length} task{g.tasks.length === 1 ? "" : "s"} ·{" "}
                    {g.tasks.filter((t) => t.status === "done").length} done
                  </div>
                </div>
                <span className={`pill ${PILL[g.status] ?? ""}`}>{g.status}</span>
              </Link>
            ))}
          </div>
        )}
      </Section>

      {recent.length > 0 && (
        <Section title="Recent results">
          <div className="rowlist">
            {recent.map((g) => (
              <Link className="r" to={`/c/${companyId}/work/${g.id}`} key={g.id}>
                <div>
                  <div className="t">{g.text}</div>
                  <div className="m">{new Date(g.updated_at).toLocaleString()}</div>
                </div>
                <span className="pill ok">done</span>
              </Link>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}

function Section({
  title,
  cta,
  children,
}: {
  title: string;
  cta?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 26 }}>
      <div className="between" style={{ marginBottom: 12 }}>
        <h2 style={{ font: "700 15px/1.2 var(--display)", letterSpacing: "-0.01em", margin: 0 }}>{title}</h2>
        {cta}
      </div>
      {children}
    </div>
  );
}
