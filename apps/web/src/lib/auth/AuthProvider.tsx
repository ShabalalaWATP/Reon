/* eslint-disable react-refresh/only-export-components -- provider and its hook form one small boundary. */
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

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
const AUTH_SYNC_KEY = "istari:auth-state";
const ACTIVITY_THROTTLE_MS = 30_000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const sessionRef = useRef<Session | null>(null);
  const idleDeadlineRef = useRef<number | null>(null);
  const lastHeartbeatRef = useRef(0);

  const applySession = useCallback((next: Session | null) => {
    sessionRef.current = next;
    idleDeadlineRef.current = next
      ? Date.parse(next.idleExpiresAt ?? next.expiresAt)
      : null;
    setSession(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  const clearSession = useCallback((broadcast = true) => {
    queryClient.clear();
    applySession(null);
    if (broadcast) window.localStorage.setItem(AUTH_SYNC_KEY, `signed-out:${Date.now()}`);
  }, [applySession, queryClient]);

  useEffect(() => {
    let active = true;
    void api
      .session()
      .then((nextSession) => {
        if (active) {
          queryClient.clear();
          applySession(nextSession);
        }
      })
      .catch((error: unknown) => {
        if (active) {
          queryClient.clear();
          applySession(null);
          if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
        }
      });
    return () => {
      active = false;
    };
  }, [applySession, queryClient]);

  useEffect(() => {
    const expireSession = () => {
      clearSession();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, [clearSession]);

  useEffect(() => {
    const synchronise = (event: StorageEvent) => {
      if (event.key === AUTH_SYNC_KEY && event.newValue?.startsWith("signed-out:")) {
        clearSession(false);
      }
    };
    window.addEventListener("storage", synchronise);
    return () => window.removeEventListener("storage", synchronise);
  }, [clearSession]);

  useEffect(() => {
    if (!session) return;
    const absoluteDeadline = Date.parse(session.expiresAt);
    const expireIfNeeded = () => {
      const idleDeadline = idleDeadlineRef.current ?? absoluteDeadline;
      if (Date.now() >= Math.min(absoluteDeadline, idleDeadline)) {
        void api.logout(session.csrfToken).catch(() => undefined);
        clearSession();
      }
    };
    const timer = window.setInterval(expireIfNeeded, 1_000);
    expireIfNeeded();
    return () => window.clearInterval(timer);
  }, [clearSession, session]);

  useEffect(() => {
    if (!session) return;
    const recordActivity = () => {
      const current = sessionRef.current;
      if (!current || document.visibilityState === "hidden") return;
      const now = Date.now();
      if (now - lastHeartbeatRef.current < ACTIVITY_THROTTLE_MS) return;
      lastHeartbeatRef.current = now;
      void api.activity(current.csrfToken)
        .then(() => {
          if (sessionRef.current === current) {
            idleDeadlineRef.current = Date.now()
              + (current.idleTimeoutSeconds ?? 3_600) * 1_000;
          }
        })
        .catch((error: unknown) => {
          if (error instanceof ApiError && error.status === 401) clearSession();
        });
    };
    window.addEventListener("keydown", recordActivity);
    window.addEventListener("pointerdown", recordActivity);
    window.addEventListener("touchstart", recordActivity);
    return () => {
      window.removeEventListener("keydown", recordActivity);
      window.removeEventListener("pointerdown", recordActivity);
      window.removeEventListener("touchstart", recordActivity);
    };
  }, [clearSession, session]);

  useEffect(() => {
    if (!session?.elevatedUntil) return;
    const remaining = Date.parse(session.elevatedUntil) - Date.now();
    if (remaining > 2_147_483_647) return;
    const expiry = window.setTimeout(() => {
      setSession((current) => current ? { ...current, elevatedUntil: null } : current);
    }, Math.max(remaining, 0));
    return () => window.clearTimeout(expiry);
  }, [session?.elevatedUntil]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      status,
      login: async (input) => {
        const nextSession = await api.login(input);
        queryClient.clear();
        applySession(nextSession);
        window.localStorage.setItem(AUTH_SYNC_KEY, `signed-in:${Date.now()}`);
        return nextSession;
      },
      elevate: async (password) => {
        if (!session) throw new ApiError("Sign in is required.", 401);
        const result = await api.elevate(password, session.csrfToken);
        applySession({ ...session, elevatedUntil: result.elevatedUntil });
        return result.elevatedUntil;
      },
      logout: async () => {
        try {
          if (session) await api.logout(session.csrfToken);
        } finally {
          clearSession();
        }
      },
    }),
    [applySession, clearSession, queryClient, session, status],
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
