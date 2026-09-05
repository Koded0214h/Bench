import { useEffect, useState } from "react";
import { api } from "../../api";
import type { PolicyRule } from "../../types";

const EFFECT_PILL: Record<string, string> = {
  ALLOW: "ok", DENY: "bad", ESCALATE: "warn", AUDIT: "run",
};

export function Policies() {
  const [rules, setRules] = useState<PolicyRule[] | null>(null);

  useEffect(() => {
    api<{ results: PolicyRule[] } | PolicyRule[]>("/policy/rules/")
      .then((d) => setRules(Array.isArray(d) ? d : d.results))
      .catch(() => setRules([]));
  }, []);

  return (
    <>
      <div className="pg-head">
        <h1>Policies</h1>
        <p>
          The rules every task is checked against before a worker is hired. Evaluated in order;
          the first match that denies or escalates wins.
        </p>
      </div>

      {!rules && <p className="muted">…</p>}
      {rules && rules.length === 0 && (
        <div className="empty"><h3>No policy rules</h3><p>Nothing is being blocked or escalated by policy.</p></div>
      )}

      {rules && rules.length > 0 && (
        <div className="rowlist">
          {rules.map((r) => (
            <div className="r" key={r.name} style={{ gridTemplateColumns: "1fr auto", alignItems: "start" }}>
              <div>
                <div className="t" style={{ fontFamily: "var(--mono)", fontSize: 13 }}>{r.name}</div>
                {r.reason && <div className="m" style={{ fontFamily: "var(--sans)", whiteSpace: "normal" }}>{r.reason}</div>}
                <div className="m">{JSON.stringify(r.match)}</div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                {!r.enabled && <span className="pill">off</span>}
                <span className={`pill ${EFFECT_PILL[r.effect] ?? ""}`}>{r.effect}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
