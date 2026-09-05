import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import { useAuth } from "../../auth";
import { BenchMark } from "../../components/marks";
import { listCompanies, useCompany } from "../../company";
import type { Company, Escalation, Goal, Paginated } from "../../types";
import "./company.css";

const NAV = [
  { group: "Workspace", items: [{ to: "", label: "Company", ico: "✦", end: true }] },
  {
    group: "Work",
    items: [
      { to: "work", label: "Work", ico: "◇" },
      { to: "workforce", label: "Workforce", ico: "◉" },
      { to: "machines", label: "Machines", ico: "▣" },
    ],
  },
  {
    group: "Control",
    items: [
      { to: "decisions", label: "Decisions", ico: "!", badge: true },
      { to: "activity", label: "Activity", ico: "≡" },
    ],
  },
  {
    group: "Knowledge",
    items: [
      { to: "memory", label: "Memory", ico: "⌁" },
      { to: "policies", label: "Policies", ico: "⛨" },
    ],
  },
];

export function Workspace() {
  const { companyId } = useParams();
  const nav = useNavigate();
  const { logout } = useAuth();
  const { company, loading, error } = useCompany(companyId);
  const [pendingDecisions, setPendingDecisions] = useState(0);

  useEffect(() => {
    if (!companyId) return;
    let alive = true;
    const poll = () =>
      Promise.all([
        api<Paginated<Goal>>(`/goals/?company=${companyId}`),
        api<Paginated<Escalation>>(`/escalations/?pending=1`),
      ])
        .then(([g, e]) => {
          if (!alive) return;
          const taskIds = new Set(g.results.flatMap((x) => x.tasks.map((t) => t.id)));
          setPendingDecisions(e.results.filter((x) => taskIds.has(x.task_id)).length);
        })
        .catch(() => {});
    poll();
    const t = setInterval(poll, 6000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [companyId]);

  if (error) {
    return (
      <div className="ws-main" style={{ maxWidth: 520, margin: "12vh auto" }}>
        <div className="empty">
          <h3>Company not found</h3>
          <p>It may have been deleted, or the link is wrong.</p>
          <p style={{ marginTop: 14 }}>
            <Link to="/companies" className="btn-teal" style={{ textDecoration: "none" }}>
              Back to your companies
            </Link>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="ws">
      <aside className="ws-side">
        <Link to="/companies" className="ws-brand">
          <BenchMark size={18} /> Bench
        </Link>

        <Switcher current={company} loading={loading} companyId={companyId} onNav={nav} />

        {NAV.map((sec) => (
          <div key={sec.group}>
            <div className="ws-group">{sec.group}</div>
            {sec.items.map((it) => (
              <NavLink
                key={it.label}
                to={it.to ? `/c/${companyId}/${it.to}` : `/c/${companyId}`}
                end={"end" in it ? it.end : false}
                className={({ isActive }) => `ws-link${isActive ? " active" : ""}`}
              >
                <span className="ico">{it.ico}</span>
                {it.label}
                {"badge" in it && it.badge && pendingDecisions > 0 && (
                  <span className="badge">{pendingDecisions}</span>
                )}
              </NavLink>
            ))}
          </div>
        ))}

        <div className="ws-spacer" />
        <NavLink to={`/c/${companyId}/settings`} className={({ isActive }) => `ws-link${isActive ? " active" : ""}`}>
          <span className="ico">⚙</span> Settings
        </NavLink>
        <button className="ws-link" style={{ border: 0, background: "none", cursor: "pointer" }} onClick={logout}>
          <span className="ico">⏻</span> Sign out
        </button>
      </aside>

      <main className="ws-main">
        <Outlet context={{ companyId, company }} />
      </main>
    </div>
  );
}

function Switcher({
  current,
  loading,
  companyId,
  onNav,
}: {
  current: Company | null;
  loading: boolean;
  companyId?: string;
  onNav: ReturnType<typeof useNavigate>;
}) {
  const [open, setOpen] = useState(false);
  const [all, setAll] = useState<Company[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) listCompanies().then(setAll).catch(() => {});
  }, [open]);

  useEffect(() => {
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);

  const others = useMemo(() => all.filter((c) => c.id !== companyId), [all, companyId]);

  return (
    <div className="switch" ref={ref}>
      <button className="switch-btn" onClick={() => setOpen((o) => !o)}>
        {loading ? "…" : current?.name ?? "Company"}
        <span className="chev">▾</span>
      </button>
      {open && (
        <div className="switch-menu">
          {current && (
            <span className="sm-cur" style={{ padding: "9px 10px", fontSize: 13, fontWeight: 600 }}>
              {current.name}
            </span>
          )}
          {others.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                setOpen(false);
                onNav(`/c/${c.id}`);
              }}
            >
              {c.name} <span className="sm-sub">{c.id}</span>
            </button>
          ))}
          <div className="sm-div" />
          <button
            onClick={() => {
              setOpen(false);
              onNav("/companies/new");
            }}
          >
            + Create company
          </button>
          <button
            onClick={() => {
              setOpen(false);
              onNav("/companies");
            }}
          >
            Manage companies
          </button>
        </div>
      )}
    </div>
  );
}

export interface WsContext {
  companyId: string;
  company: Company | null;
}
