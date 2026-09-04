import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth";
import { ApiError } from "../api";

export function Login() {
  const { user, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  if (user) return <Navigate to="/" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      if (mode === "login") await login(username, password);
      else await register(username, email, password);
    } catch (x) {
      const b = x instanceof ApiError ? x.body : null;
      setErr(
        b && typeof b === "object"
          ? Object.values(b).flat().join(" ")
          : mode === "login"
            ? "wrong username or password"
            : "could not register",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <h1 className="mono" style={{ letterSpacing: 3, textAlign: "center" }}>BENCH</h1>
      <p className="muted small" style={{ textAlign: "center", marginTop: -6 }}>
        a company staffed by AI agents that actually do the work
      </p>
      <div className="panel" style={{ marginTop: 24 }}>
        <div className="tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Sign in</button>
          <button className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>Register</button>
        </div>
        <form className="stack" onSubmit={submit}>
          <div>
            <label>Username</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
          </div>
          {mode === "register" && (
            <div>
              <label>Email (optional)</label>
              <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" autoComplete="email" />
            </div>
          )}
          <div>
            <label>Password</label>
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>
          {err && <div className="err">{err}</div>}
          <button disabled={busy || !username || !password}>
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
