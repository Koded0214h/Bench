import { Link } from "react-router-dom";
import { useAuth } from "../../auth";
import { BenchMark } from "../../components/marks";
import "../company/company.css";

const SECTIONS = [
  { title: "Profile", body: "Your name and email." },
  { title: "Security", body: "Password and active sessions." },
  { title: "Billing", body: "Payment method and invoices." },
  { title: "Notifications", body: "What Bench emails you about." },
  { title: "Connected accounts", body: "Logins the workforce can reuse." },
];

export function AccountSettings() {
  const { user } = useAuth();

  return (
    <div className="acct">
      <div className="acct-top">
        <Link to="/companies" className="brand"><BenchMark size={18} /> Bench</Link>
        <span className="spacer" />
        <Link to="/companies" className="l-nav-link" style={{ color: "var(--mid)", textDecoration: "none", fontSize: 13 }}>
          Your companies
        </Link>
      </div>

      <h1>Account</h1>
      <p className="acct-sub" style={{ marginBottom: 30 }}>Signed in as {user?.username}{user?.email ? ` · ${user.email}` : ""}</p>

      <div className="rowlist">
        {SECTIONS.map((s) => (
          <div className="r" key={s.title} style={{ gridTemplateColumns: "1fr auto" }}>
            <div>
              <div className="t">{s.title}</div>
              <div className="m" style={{ fontFamily: "var(--sans)" }}>{s.body}</div>
            </div>
            <span className="m">Soon</span>
          </div>
        ))}
      </div>
    </div>
  );
}
