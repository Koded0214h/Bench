import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api";
import type { Escalation, Paginated } from "../../types";
import type { WsContext } from "./Workspace";
import { useCompanyScope } from "./scope";

export function Decisions() {
  const { companyId } = useOutletContext<WsContext>();
  const { taskIds, ready } = useCompanyScope(companyId, 4000);
  const [escs, setEscs] = useState<Escalation[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    const d = await api<Paginated<Escalation>>("/escalations/?pending=1");
    setEscs(d.results.filter((e) => taskIds.has(e.task_id)));
  }

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => load().catch(() => {}), 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, [...taskIds].join()]);

  async function resolve(id: string, approved: boolean) {
    setBusy(id);
    try {
      await api(`/escalations/${id}/resolve/`, { method: "POST", body: { approved } });
      await load();
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="pg-head">
        <h1>Decisions</h1>
        <p>Anything the company can’t do without you. Approvals, reviews, and stuck workers.</p>
      </div>

      {escs.length === 0 ? (
        <div className="empty">
          <h3>{ready ? "Nothing needs you" : "…"}</h3>
          {ready && <p>When a worker hits something that needs a human call, it shows up here.</p>}
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {escs.map((e) => (
            <div className="goalbox" key={e.id} style={{ marginBottom: 0 }}>
              <div className="m" style={{ fontFamily: "var(--mono)", fontSize: 11.5, color: "var(--mid)" }}>
                task {e.task_id}
              </div>
              <div style={{ margin: "8px 0 14px", fontSize: 15 }}>{e.reason || "A worker needs a decision."}</div>
              <div style={{ display: "flex", gap: 10 }}>
                <button className="btn-teal" disabled={busy === e.id} onClick={() => resolve(e.id, true)}>
                  Approve
                </button>
                <button
                  className="ghost"
                  style={{ borderColor: "var(--bad)", color: "var(--bad)" }}
                  disabled={busy === e.id}
                  onClick={() => resolve(e.id, false)}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
