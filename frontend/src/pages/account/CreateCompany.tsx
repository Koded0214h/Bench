import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BenchMark } from "../../components/marks";
import { createCompany } from "../../company";
import "../company/company.css";

type Autonomy = "ask" | "auto";

const INIT_STEPS = [
  "Establishing company identity",
  "Creating the management team",
  "Loading company memory",
  "Applying default policies",
  "Preparing the workforce",
];

export function CreateCompany() {
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [focus, setFocus] = useState("");
  const [autonomy, setAutonomy] = useState<Autonomy>("ask");
  const [phase, setPhase] = useState<"form" | "init">("form");
  const [step, setStep] = useState(0);
  const [companyId, setCompanyId] = useState<string | null>(null);
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const c = await createCompany({ name, purpose, focus, autonomy });
      setCompanyId(c.id);
      setPhase("init");
    } catch (x) {
      setErr(String(x));
    }
  }

  useEffect(() => {
    if (phase !== "init") return;
    if (step >= INIT_STEPS.length) {
      const t = setTimeout(() => nav(`/c/${companyId}`), 700);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setStep((s) => s + 1), 520);
    return () => clearTimeout(t);
  }, [phase, step, companyId, nav]);

  if (phase === "init") {
    return (
      <div className="acct">
        <div className="acct-top">
          <span className="brand"><BenchMark size={18} /> Bench</span>
        </div>
        <div className="init">
          <p style={{ color: "var(--mid)", marginBottom: 18 }}>Creating {name}…</p>
          {INIT_STEPS.map((s, i) => (
            <div key={s} className={`init-line${i < step ? " done" : ""}`}>
              <span className="tick">{i < step ? "✓" : "·"}</span>
              {s}
            </div>
          ))}
          {step >= INIT_STEPS.length && (
            <p style={{ color: "var(--teal-ink)", marginTop: 18 }}>Your company is ready.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="acct">
      <div className="acct-top">
        <Link to="/companies" className="brand"><BenchMark size={18} /> Bench</Link>
      </div>

      <div style={{ marginBottom: 8 }}>
        <Link to="/companies" className="small muted" style={{ textDecoration: "none" }}>← Your companies</Link>
      </div>
      <h1>Create your company</h1>
      <p className="acct-sub" style={{ marginBottom: 30 }}>
        You’re setting up an AI-run company. Give it a name, tell it what it does,
        and point it at what matters.
      </p>

      <form className="form-narrow" onSubmit={submit}>
        <div className="field">
          <label>What’s it called?</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Acme" autoFocus />
        </div>
        <div className="field">
          <label>What does it do?</label>
          <textarea
            rows={3}
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="We build tools for Nigerian freelancers."
          />
        </div>
        <div className="field">
          <label>What should it focus on?</label>
          <textarea
            rows={2}
            value={focus}
            onChange={(e) => setFocus(e.target.value)}
            placeholder="Growth, product, and operations."
          />
          <div className="hint">The management team uses this to decide what work to take on.</div>
        </div>
        <div className="field">
          <label>How much should it run on its own?</label>
          <div className="seg">
            <button type="button" className={autonomy === "ask" ? "on" : ""} onClick={() => setAutonomy("ask")}>
              <span className="seg-t">Ask first</span>
              Sign off before anything leaves the company.
            </button>
            <button type="button" className={autonomy === "auto" ? "on" : ""} onClick={() => setAutonomy("auto")}>
              <span className="seg-t">Run it</span>
              Only stop for what policy forces.
            </button>
          </div>
        </div>

        {err && <div className="err" style={{ marginBottom: 14 }}>{err}</div>}

        <button className="btn-teal" disabled={name.trim().length < 2}>Create company →</button>
      </form>
    </div>
  );
}
