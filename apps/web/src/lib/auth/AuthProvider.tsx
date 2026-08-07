/* eslint-disable react-refresh/only-export-components -- provider and its hook form one small boundary. */
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, ApiError, SESSION_EXPIRED_EVENT } from "../api/client";
import type { Session } from "../api/types";

type AuthStatus = "loading" | "authenticated" | "anonymous";
type AuthContextValue = {
  session: Session | null;
  status: AuthStatus;
  login: (input: { username: string; password: string }) => Promise<Session>;
  elevate: (password: string) => Promise<string>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");

  useEffect(() => {
    let active = true;
    void api
      .session()
      .then((nextSession) => {
        if (active) {
          queryClient.clear();
          setSession(nextSession);
          setStatus("authenticated");
        }
      })
      .catch((error: unknown) => {
        if (active) {
          queryClient.clear();
          setSession(null);
          setStatus("anonymous");
          if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
        }
      });
    return () => {
      active = false;
    };
  }, [queryClient]);

  useEffect(() => {
    const expireSession = () => {
      queryClient.clear();
      setSession(null);
      setStatus("anonymous");
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      status,
      login: async (input) => {
        const nextSession = await api.login(input);
        queryClient.clear();
        setSession(nextSession);
        setStatus("authenticated");
        return nextSession;
      },
      elevate: async (password) => {
        if (!session) throw new ApiError("Sign in is required.", 401);
        const result = await api.elevate(password, session.csrfToken);
        setSession({ ...session, elevatedUntil: result.elevatedUntil });
        return result.elevatedUntil;
      },
      logout: async () => {
        if (session) await api.logout(session.csrfToken);
        queryClient.clear();
        setSession(null);
        setStatus("anonymous");
      },
    }),
    [queryClient, session, status],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}

export function isSessionElevated(session: Session | null): boolean {
  return Boolean(
    session?.elevatedUntil
      && Date.parse(session.elevatedUntil) > Date.now(),
  );
}
