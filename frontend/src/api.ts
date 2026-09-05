// Where the backend lives. Empty in dev, where Vite proxies /api to Django;
// set at build time for deployments served from a different origin than the
// API (Vercel in front of api.bench.kodedlabs.com). CORS on the backend
// already allows that origin.
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

const ACCESS = "bench.access";
const REFRESH = "bench.refresh";

export function getTokens() {
  return { access: localStorage.getItem(ACCESS), refresh: localStorage.getItem(REFRESH) };
}
export function setTokens(access: string, refresh?: string) {
  localStorage.setItem(ACCESS, access);
  if (refresh) localStorage.setItem(REFRESH, refresh);
}
export function clearTokens() {
  localStorage.removeItem(ACCESS);
  localStorage.removeItem(REFRESH);
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown) {
    super(typeof body === "object" && body && "detail" in body ? String((body as any).detail) : `HTTP ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function refreshAccess(): Promise<boolean> {
  const { refresh } = getTokens();
  if (!refresh) return false;
  const r = await fetch(`${API_BASE}/api/auth/token/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!r.ok) return false;
  const data = await r.json();
  setTokens(data.access);
  return true;
}

export async function api<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const doFetch = () => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth) {
      const { access } = getTokens();
      if (access) headers["Authorization"] = `Bearer ${access}`;
    }
    return fetch(`${API_BASE}/api${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res = await doFetch();
  if (res.status === 401 && auth && (await refreshAccess())) {
    res = await doFetch();
  }
  const text = await res.text();

  // A misrouted call (a proxy or rewrite serving the SPA shell where the API
  // should be) comes back as HTML with a 200, and parsing it blind reports
  // "unexpected character at line 1 column 1" — which says nothing about the
  // actual problem. Fail with the status and content type instead.
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      const kind = res.headers.get("content-type") || "unknown content type";
      throw new ApiError(res.status, {
        detail: `Expected JSON from /api${path} but got ${kind} (HTTP ${res.status}).`,
      });
    }
  }
  if (!res.ok) throw new ApiError(res.status, parsed);
  return parsed as T;
}
