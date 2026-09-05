import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { api } from "../../api";
import type { AuditEvent } from "../../types";
import type { WsContext } from "./Workspace";
import { useCompanyScope } from "./scope";

const LABEL: Record<string, string> = {
  goal_created: "Goal created",
  task_created: "Task created",
  worker_hired: "Worker hired",
  worker_dismissed: "Worker dismissed",
  machine_provisioned: "Machine provisioned",
  machine_destroyed: "Machine destroyed",
  policy_evaluated: "Policy evaluated",
  dispatch_allowed: "Dispatch allowed",
  dispatch_denied: "Dispatch denied",
  worker_started: "Worker started",
  artifact_produced: "Artifact produced",
  quarantine_passed: "Verification passed",
  quarantine_failed: "Verification failed",
};

export function Activity() {
  const { companyId } = useOutletContext<WsContext>();
  const { taskIds, goalIds, ready } = useCompanyScope(companyId, 6000);
  const [events, setEvents] = useState<AuditEvent[]>([]);

  useEffect(() => {
    const load = () =>
      api<{ events: AuditEvent[] }>("/audit?limit=400")
        .then((d) => setEvents(d.events))
        .catch(() => {});
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, [companyId]);

  const mine = events.filter(
    (e) => (e.task_id && (taskIds.has(e.task_id) || goalIds.has(e.task_id))) || (e.worker_id && taskIds.has(e.worker_id)),
  );

  return (
    <>
      <div className="pg-head">
        <h1>Activity</h1>
        <p>The company event stream. Every hire, machine, policy check, and result.</p>
      </div>

      {mine.length === 0 ? (
        <div className="empty">
          <h3>{ready ? "No activity yet" : "…"}</h3>
          {ready && <p>Events land here as the company works.</p>}
        </div>
      ) : (
        <div className="rowlist">
          {mine.slice(0, 200).map((e, i) => (
            <div className="r" key={e.event_id ?? i}>
              <div>
                <div className="t">{LABEL[e.kind] ?? e.kind.replace(/_/g, " ")}</div>
                <div className="m">
                  {e.task_id ? `${e.task_id}` : ""}
                  {e.worker_id ? ` · ${e.worker_id}` : ""}
                  {e.actor ? ` · ${e.actor}` : ""}
                </div>
              </div>
              <span className="m" style={{ whiteSpace: "nowrap" }}>
                {e.ts ? new Date(e.ts).toLocaleTimeString() : ""}
              </span>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
