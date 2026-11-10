"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, ApiError, hasStoredSession, login as apiLogin, logout as apiLogout } from "./api";
import type { Me } from "./types";

type Session = {
  me: Me | null;
  loading: boolean;
  error: ApiError | null;
  /** Resolves with recovery codes when this login set two-factor up: show them, then call
   *  `completeLogin`. Otherwise the session is live when it resolves. */
  login: (email: string, password: string, code?: string) => Promise<string[] | null>;
  completeLogin: () => Promise<void>;
  logout: () => Promise<void>;
  loggedOut: boolean;
  /** A session stored in this browser could not be renewed (not: never logged in here). */
  expired: boolean;
  reload: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [loggedOut, setLoggedOut] = useState(false);
  const [expired, setExpired] = useState(false);

  const reload = useCallback(async () => {
    try {
      setMe(await api<Me>("/auth/me"));
      setError(null);
      setExpired(false);
    } catch (e) {
      setMe(null);
      // 401 just means "not logged in"; anything else is shown to the user.
      if (e instanceof ApiError && e.status === 401) {
        setExpired(true);
      } else {
        setError(e instanceof ApiError ? e : new ApiError(0, "unknown", String(e)));
      }
    }
  }, []);

  const completeLogin = useCallback(async () => {
    await reload();
    setLoggedOut(false);
  }, [reload]);

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
      loggedOut,
      expired,
      reload,
      login: async (email, password, code) => {
        const recovery = await apiLogin(email, password, code);
        if (recovery) return recovery;
        await completeLogin();
        return null;
      },
      completeLogin,
      logout: async () => {
        await apiLogout();
        setLoggedOut(true);
        setMe(null);
      },
    }),
    [me, loading, error, loggedOut, expired, reload, completeLogin],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
