"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError, hasStoredSession, login as apiLogin, logout as apiLogout } from "./api";
import type { Me } from "./types";

type Session = {
  me: Me | null;
  loading: boolean;
  error: ApiError | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const reload = useCallback(async () => {
    try {
      setMe(await api<Me>("/auth/me"));
      setError(null);
    } catch (e) {
      setMe(null);
      // 401 just means "not logged in"; anything else is shown to the user.
      if (!(e instanceof ApiError && e.status === 401)) {
        setError(e instanceof ApiError ? e : new ApiError(0, "unknown", String(e)));
      }
    }
  }, []);

  useEffect(() => {
    if (!hasStoredSession()) {
      setLoading(false);
      return;
    }
    reload().finally(() => setLoading(false));
  }, [reload]);

  const value = useMemo<Session>(
    () => ({
      me,
      loading,
      error,
      reload,
      login: async (email, password) => {
        await apiLogin(email, password);
        await reload();
      },
      logout: async () => {
        await apiLogout();
        setMe(null);
      },
    }),
    [me, loading, error, reload],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
