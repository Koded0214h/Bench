import { useEffect, useState } from "react";
import { Link, useOutletContext } from "react-router-dom";
import { api } from "../../api";
import type { Agent, Paginated } from "../../types";
import type { WsContext } from "./Workspace";
import { useCompanyScope } from "./scope";

export function Workforce() {
  const { companyId } = useOutletContext<WsContext>();
  const { taskIds, ready } = useCompanyScope(companyId);
  const [agents, setAgents] = useState<Agent[]>([]);

  useEffect(() => {
    const load = () =>
      api<Paginated<Agent>>("/agents/").then((d) => setAgents(d.results)).catch(() => {});
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [companyId]);

  const mine = agents.filter((a) => !a.task_id || taskIds.has(a.task_id));
  const management = mine.filter((a) => a.kind === "management");
  const workersActive = mine.filter((a) => a.kind === "worker" && a.status === "active");
  const workersPast = mine.filter((a) => a.kind === "worker" && a.status !== "active");

  return (
    <>
      <div className="pg-head">
        <h1>Workforce</h1>
        <p>Management stays. Workers are hired for a task and let go when it’s done.</p>
      </div>

      <Group title="Management">
        {management.length === 0 && !ready && <p className="muted">…</p>}
        {management.length === 0 && ready && (
          <div className="empty"><h3>No management agents yet</h3><p>They spin up with the company’s first goal.</p></div>
        )}
        {management.length > 0 && (
          <div className="rowlist">
            {management.map((a) => (
              <div className="r" key={a.id}>
                <div>
                  <div className="t" style={{ textTransform: "capitalize" }}>{a.role || "agent"}</div>
                  <div className="m">{a.id}</div>
                </div>
                <span className={`pill ${a.status === "active" ? "run" : ""}`}>{a.status}</span>
              </div>
            ))}
          </div>
        )}
      </Group>

      <Group title={`Workers · ${workersActive.length} active`}>
        {workersActive.length === 0 && (
          <div className="empty"><h3>No workers right now</h3><p>They’re hired when there’s a task to run.</p></div>
        )}
        {workersActive.length > 0 && (
          <div className="rowlist">
            {workersActive.map((a) => (
              <WorkerRow key={a.id} a={a} companyId={companyId} />
            ))}
          </div>
        )}
      </Group>

      {workersPast.length > 0 && (
        <Group title="Recently dismissed">
          <div className="rowlist">
            {workersPast.slice(0, 12).map((a) => (
              <WorkerRow key={a.id} a={a} companyId={companyId} dim />
            ))}
          </div>
        </Group>
      )}
    </>
  );
}

function WorkerRow({ a, companyId, dim }: { a: Agent; companyId: string; dim?: boolean }) {
  const inner = (
    <>
      <div>
        <div className="t" style={{ textTransform: "capitalize", opacity: dim ? 0.65 : 1 }}>
          {a.role || a.capability || "worker"}
        </div>
        <div className="m">{a.capability ? `${a.capability} · ` : ""}{a.id}</div>
      </div>
      <span className={`pill ${a.status === "active" ? "run" : ""}`}>{a.status}</span>
    </>
  );
  return a.task_id ? (
    <Link className="r" to={`/c/${companyId}/work`}>{inner}</Link>
  ) : (
    <div className="r">{inner}</div>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 26 }}>
      <h2 style={{ font: "700 15px/1.2 var(--display)", letterSpacing: "-0.01em", margin: "0 0 12px" }}>{title}</h2>
      {children}
    </div>
  );
}
