import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { Companies } from "./pages/account/Companies";
import { CreateCompany } from "./pages/account/CreateCompany";
import { AccountSettings } from "./pages/account/AccountSettings";
import { Workspace } from "./pages/company/Workspace";
import { CompanyHome } from "./pages/company/CompanyHome";
import { Work } from "./pages/company/Work";
import { GoalDetail } from "./pages/GoalDetail";
import { Workforce } from "./pages/company/Workforce";
import { Machines } from "./pages/company/Machines";
import { Decisions } from "./pages/company/Decisions";
import { Activity } from "./pages/company/Activity";
import { Policies } from "./pages/company/Policies";
import { Memory } from "./pages/company/Memory";
import { CompanySettings } from "./pages/company/CompanySettings";
import "./styles.css";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="app"><p className="muted">…</p></div>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Login />} />

      <Route path="/companies" element={<RequireAuth><Companies /></RequireAuth>} />
      <Route path="/companies/new" element={<RequireAuth><CreateCompany /></RequireAuth>} />
      <Route path="/account" element={<RequireAuth><AccountSettings /></RequireAuth>} />

      <Route path="/c/:companyId" element={<RequireAuth><Workspace /></RequireAuth>}>
        <Route index element={<CompanyHome />} />
        <Route path="work" element={<Work />} />
        <Route path="work/:id" element={<GoalDetail />} />
        <Route path="workforce" element={<Workforce />} />
        <Route path="machines" element={<Machines />} />
        <Route path="decisions" element={<Decisions />} />
        <Route path="activity" element={<Activity />} />
        <Route path="policies" element={<Policies />} />
        <Route path="memory" element={<Memory />} />
        <Route path="settings" element={<CompanySettings />} />
      </Route>

      <Route path="/dashboard" element={<Navigate to="/companies" replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
