import { useEffect, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { deleteCompany, updateCompany } from "../../company";
import type { WsContext } from "./Workspace";

export function CompanySettings() {
  const { companyId, company } = useOutletContext<WsContext>();
  const nav = useNavigate();
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [focus, setFocus] = useState("");
  const [autonomy, setAutonomy] = useState<"ask" | "auto">("ask");
  const [saved, setSaved] = useState(false);
  const [confirm, setConfirm] = useState("");

  useEffect(() => {
    if (!company) return;
    setName(company.name);
    setPurpose(company.purpose);
    setFocus(company.focus);
    setAutonomy(company.autonomy);
  }, [company]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    await updateCompany(companyId, { name, purpose, focus, autonomy });
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
  }

  async function remove() {
    await deleteCompany(companyId);
    nav("/companies");
  }

  return (
    <>
      <div className="pg-head">
        <h1>Settings</h1>
        <p>Identity and defaults for this company. Credentials and members come later.</p>
      </div>

      <form className="form-narrow" onSubmit={save}>
        <div className="field">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label>What it does</label>
          <textarea rows={3} value={purpose} onChange={(e) => setPurpose(e.target.value)} />
        </div>
        <div className="field">
          <label>What it focuses on</label>
          <textarea rows={2} value={focus} onChange={(e) => setFocus(e.target.value)} />
        </div>
        <div className="field">
          <label>Autonomy</label>
          <div className="seg">
            <button type="button" className={autonomy === "ask" ? "on" : ""} onClick={() => setAutonomy("ask")}>
              <span className="seg-t">Ask first</span>Sign off before anything leaves the company.
            </button>
            <button type="button" className={autonomy === "auto" ? "on" : ""} onClick={() => setAutonomy("auto")}>
              <span className="seg-t">Run it</span>Only stop for what policy forces.
            </button>
          </div>
        </div>
        <button className="btn-teal">{saved ? "Saved" : "Save changes"}</button>
      </form>

      <div className="field" style={{ marginTop: 48, maxWidth: 560 }}>
        <label style={{ color: "var(--bad)" }}>Danger zone</label>
        <div className="rowlist" style={{ borderColor: "var(--bad)" }}>
          <div className="r" style={{ gridTemplateColumns: "1fr auto" }}>
            <div>
              <div className="t">Delete this company</div>
              <div className="m" style={{ fontFamily: "var(--sans)", whiteSpace: "normal" }}>
                Removes the company. Its past work stays in your account.
              </div>
            </div>
          </div>
          <div className="r" style={{ gridTemplateColumns: "1fr auto", gap: 10 }}>
            <input
              placeholder={`type "${company?.name ?? ""}" to confirm`}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            <button
              className="ghost"
              style={{ borderColor: "var(--bad)", color: "var(--bad)" }}
              disabled={confirm !== company?.name}
              onClick={remove}
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
