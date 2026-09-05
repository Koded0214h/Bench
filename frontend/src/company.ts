// Companies live in the account. Goals belong to a company; the workspace's
// Work / Workforce / Machines / Activity views are the account's data filtered
// to one company.

import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import type { Company, Paginated } from "./types";

export type { Company } from "./types";

export interface CompanyInput {
  name: string;
  purpose: string;
  focus: string;
  autonomy: "ask" | "auto";
}

export function listCompanies() {
  return api<Paginated<Company> | Company[]>("/companies/").then((d) =>
    Array.isArray(d) ? d : d.results,
  );
}

export function getCompany(id: string) {
  return api<Company>(`/companies/${id}/`);
}

export function createCompany(input: CompanyInput) {
  return api<Company>("/companies/", { method: "POST", body: input });
}

export function updateCompany(id: string, patch: Partial<CompanyInput>) {
  return api<Company>(`/companies/${id}/`, { method: "PATCH", body: patch });
}

export function deleteCompany(id: string) {
  return api<void>(`/companies/${id}/`, { method: "DELETE" });
}

/** account-level list, with a manual reload */
export function useCompanies() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState<string>("");

  const reload = useCallback(() => {
    listCompanies()
      .then((c) => setCompanies(c))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => reload(), [reload]);
  return { companies, loading: companies === null && !error, error, reload };
}

/** one company by id */
export function useCompany(id: string | undefined) {
  const [company, setCompany] = useState<Company | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!id) return;
    setCompany(null);
    setError("");
    getCompany(id)
      .then(setCompany)
      .catch((e) => setError(String(e)));
  }, [id]);

  return { company, loading: !!id && company === null && !error, error };
}
