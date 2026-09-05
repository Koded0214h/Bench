import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { BenchMark } from "../../components/marks";
import { useCompanies } from "../../company";
import type { Goal, Paginated, Spend } from "../../types";
import "../company/company.css";

const RUNNING = ["running", "planning", "pending"];

export function Companies() {
  const { user, logout } = useAuth();
  const { companies, loading, error } = useCompanies();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [spend, setSpend] = useState<Spend | null>(null);

  useEffect(() => {
    const load = () =>
      Promise.all([api<Paginated<Goal>>("/goals/?limit=200"), api<Spend>("/spend")])
        .then(([g, s]) => {
          setGoals(g.results);
          setSpend(s);
        })
        .catch(() => {});
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, []);

  function stateOf(companyId: string) {
    const own = goals.filter((g) => g.company_id === companyId);
    const workers = own
      .filter((g) => RUNNING.includes(g.status))
      .flatMap((g) => g.tasks.filter((t) => t.status === "running")).length;
    const activeTasks = own.flatMap((g) => g.tasks.filter((t) => RUNNING.includes(t.status) || t.status === "dispatching")).length;
    const needsYou = own.flatMap((g) => g.tasks.filter((t) => t.status === "escalated")).length;
    const completed = own.filter((g) => g.status === "done").length;
    const cost = own
      .flatMap((g) => [g.id, ...g.tasks.map((t) => t.id)])
      .reduce((sum, id) => sum + (spend?.tasks[id]?.total_usd ?? 0), 0);
    const busy = own.some((g) => RUNNING.includes(g.status));
    return { workers, activeTasks, needsYou, completed, cost, busy };
  }

  const working = companies?.filter((c) => stateOf(c.id).busy).length ?? 0;

  return (
    <div className="acct">
      <div className="acct-top">
        <Link to="/companies" className="brand">
          <BenchMark size={18} /> Bench
        </Link>
        <span className="spacer" />
        <Link to="/account" className="l-nav-link" style={{ color: "var(--mid)", textDecoration: "none", fontSize: 13 }}>
          {user?.username}
        </Link>
        <button className="ghost small" onClick={logout}>sign out</button>
      </div>

      <div className="acct-headrow">
        <div>
          <h1>Your companies</h1>
          <p className="acct-sub">
            {companies && companies.length > 0
              ? `${companies.length} ${companies.length === 1 ? "company" : "companies"}${working ? ` · ${working} working now` : ""}`
              : "Each one is an AI-run company you give objectives to."}
          </p>
        </div>
        <Link to="/companies/new" className="btn-teal" style={{ textDecoration: "none" }}>
          New company
        </Link>
      </div>

      {error && <div className="err">{error}</div>}
      {loading && <p className="muted">…</p>}

      {companies && companies.length === 0 && (
        <div className="empty">
          <h3>No companies yet</h3>
          <p>Create one, give it an objective, and it starts hiring workers to get it done.</p>
          <p style={{ marginTop: 16 }}>
            <Link to="/companies/new" className="btn-teal" style={{ textDecoration: "none" }}>
              Create your first company
            </Link>
          </p>
        </div>
      )}

      {companies && companies.length > 0 && (
        <div className="co-grid">
          {companies.map((c) => {
            const s = stateOf(c.id);
            return (
              <Link to={`/c/${c.id}`} className="co-card" key={c.id}>
                <div className="co-card-name">{c.name}</div>
                <div className="co-card-purpose">{c.purpose || "No description yet."}</div>
                <div className="co-card-meta">
                  <span>{s.workers} workers</span>
                  <span>{s.activeTasks} active tasks</span>
                  {s.completed > 0 && <span>{s.completed} completed</span>}
                  <span>${s.cost.toFixed(2)} spent</span>
                </div>
                <div
                  className={`co-state ${
                    s.needsYou > 0 ? "is-attention" : s.busy ? "is-working" : ""
                  }`}
                >
                  {s.needsYou > 0
                    ? `Needs you · ${s.needsYou}`
                    : s.busy
                      ? "Company working"
                      : "Idle"}
                </div>
              </Link>
            );
          })}
          <Link to="/companies/new" className="co-new">
            <span className="plus">+</span>
            Create a new company
          </Link>
        </div>
      )}
    </div>
  );
}
