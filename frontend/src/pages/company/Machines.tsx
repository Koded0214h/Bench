import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api";
import type { Machine, Paginated } from "../../types";
import type { WsContext } from "./Workspace";
import { useCompanyScope } from "./scope";

export function Machines() {
  const { companyId } = useOutletContext<WsContext>();
  const { taskIds, ready } = useCompanyScope(companyId);
  const [machines, setMachines] = useState<Machine[]>([]);

  useEffect(() => {
    const load = () =>
      api<Paginated<Machine>>("/machines/").then((d) => setMachines(d.results)).catch(() => {});
    load();
    const t = setInterval(load, 3500);
    return () => clearInterval(t);
  }, [companyId]);

  const mine = machines.filter((m) => m.task_id && taskIds.has(m.task_id));
  const live = mine.filter((m) => m.status !== "destroyed");
  const gone = mine.filter((m) => m.status === "destroyed");

  return (
    <>
      <div className="pg-head">
        <h1>Machines</h1>
        <p>Every worker gets one. It’s created for the task and destroyed with it.</p>
      </div>

      <div className="co-card-meta" style={{ margin: "0 2px 20px", gap: 20, fontSize: 12.5 }}>
        <span>{live.length} running</span>
        <span>{gone.length} destroyed</span>
      </div>

      {mine.length === 0 && (
        <div className="empty">
          <h3>{ready ? "No machines" : "…"}</h3>
          {ready && <p>Machines appear here the moment a worker is hired.</p>}
        </div>
      )}

      {live.length > 0 && (
        <div className="rowlist" style={{ marginBottom: 18 }}>
          {live.map((m) => (
            <div className="r" key={m.id}>
              <div>
                <div className="t">{m.kind} <span className="pill run" style={{ marginLeft: 6 }}>{m.status}</span></div>
                <div className="m">{m.id.slice(0, 52)}</div>
              </div>
              <div style={{ display: "flex", gap: 10, fontSize: 12 }}>
                {m.stream_url && <a href={m.stream_url} target="_blank" rel="noreferrer">live session</a>}
                {Object.entries(m.preview_urls || {}).map(([p, u]) => (
                  <a key={p} href={u} target="_blank" rel="noreferrer">:{p}</a>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {gone.length > 0 && (
        <div className="rowlist">
          {gone.slice(0, 15).map((m) => (
            <div className="r" key={m.id}>
              <div>
                <div className="t" style={{ opacity: 0.6 }}>{m.kind}</div>
                <div className="m">{m.id.slice(0, 52)}</div>
              </div>
              <span className="pill">destroyed</span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
