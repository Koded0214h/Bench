# `frontend/` — the Bench web app

React + Vite + TypeScript. Talks to the control-plane API (module 8) with a JWT.

## Dev

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173  (proxies /api and /healthz to :8000)
```

Run the API alongside it: `python manage.py runserver` (from the repo root).

## Build (served by Django)

```bash
npm run build          # -> frontend/dist, base path /app/
```

Django serves the build at **http://localhost:8000/app/** (root `/` redirects
there). `start.sh` builds it if `dist/` is missing.

## What it does

- **Register / sign in** — `/api/auth/register`, `/api/auth/token`; access +
  refresh tokens in `localStorage`, auto-refresh on 401.
- **Dashboard** — your goals (scoped to you server-side), and a box to submit a
  new one. Submitting runs it immediately.
- **Goal detail** — live view (polls every 2s while running): the CEO's task
  breakdown, each task's policy decision, quarantine checks, and review verdict;
  pending escalations with **Approve / Reject**; live machines with their preview
  / stream links; spend and audit-chain status.

## Layout

```
src/
  api.ts        fetch wrapper: JWT header, refresh-on-401, ApiError
  auth.tsx      AuthProvider / useAuth (login, register, logout, me)
  types.ts      API response shapes
  main.tsx      router (basename /app) + shell
  pages/Login.tsx  Dashboard.tsx  GoalDetail.tsx
  styles.css
```
