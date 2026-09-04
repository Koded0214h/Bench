import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { api, clearTokens, getTokens, setTokens } from "./api";
import type { User } from "./types";

interface AuthCtx {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const { access } = getTokens();
    if (!access) {
      setLoading(false);
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const data = await api<{ access: string; refresh: string }>("/auth/token", {
      method: "POST",
      body: { username, password },
      auth: false,
    });
    setTokens(data.access, data.refresh);
    setUser(await api<User>("/auth/me"));
  }

  async function register(username: string, email: string, password: string) {
    const data = await api<{ access: string; refresh: string; user: User }>("/auth/register", {
      method: "POST",
      body: { username, email, password },
      auth: false,
    });
    setTokens(data.access, data.refresh);
    setUser(data.user);
  }

  function logout() {
    clearTokens();
    setUser(null);
  }

  return <Ctx.Provider value={{ user, loading, login, register, logout }}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
