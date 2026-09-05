import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../../api";
import type { Goal, Paginated } from "../../types";
import type { WsContext } from "./Workspace";

const PILL: Record<string, string> = {
  done: "ok", running: "run", planning: "run", pending: "run", blocked: "warn", failed: "bad",
};

type Bucket = "running" | "waiting" | "completed" | "failed";
const BUCKETS: { key: Bucket; label: string }[] = [
  { key: "running", label: "Running" },
  { key: "waiting", label: "Waiting" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
];

function bucketOf(g: Goal): Bucket {
  if (g.status === "done") return "completed";
  if (g.status === "failed") return "failed";
  if (g.status === "blocked" || g.tasks.some((t) => t.status === "escalated")) return "waiting";
  return "running";
}

export function Work() {
  const { companyId } = useOutletContext<WsContext>();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [tab, setTab] = useState<Bucket>("running");

  useEffect(() => {
    const load = () =>
      api<Paginated<Goal>>(`/goals/?company=${companyId}&limit=200`)
        .then((d) => setGoals(d.results))
        .catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [companyId]);

  const counts = useMemo(() => {
    const c: Record<Bucket, number> = { running: 0, waiting: 0, completed: 0, failed: 0 };
    goals.forEach((g) => (c[bucketOf(g)] += 1));
    return c;
  }, [goals]);

  const shown = goals.filter((g) => bucketOf(g) === tab);

  return (
    <>
      <div className="pg-head">
        <h1>Work</h1>
        <p>Everything this company is doing or has done.</p>
      </div>

      <div className="filters">
        {BUCKETS.map((b) => (
          <button key={b.key} className={tab === b.key ? "on" : ""} onClick={() => setTab(b.key)}>
            {b.label} {counts[b.key] > 0 && <span style={{ opacity: 0.6 }}>· {counts[b.key]}</span>}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <div className="empty">
          <h3>Nothing here</h3>
          <p>
            {tab === "running"
              ? "No work in progress. Start something from the company page."
              : `No ${tab} work.`}
          </p>
        </div>
      ) : (
        <div className="rowlist">
          {shown.map((g) => (
            <Link className="r" to={`/c/${companyId}/work/${g.id}`} key={g.id}>
              <div>
                <div className="t">{g.text}</div>
                <div className="m">
                  {g.id} · {g.tasks.length} task{g.tasks.length === 1 ? "" : "s"} ·{" "}
                  {g.tasks.filter((t) => t.status === "done").length} done ·{" "}
                  {new Date(g.created_at).toLocaleDateString()}
                </div>
              </div>
              <span className={`pill ${PILL[g.status] ?? ""}`}>{g.status}</span>
            </Link>
          ))}
        </div>
      )}
    </>
  );
}
