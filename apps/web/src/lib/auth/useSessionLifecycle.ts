import { type QueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, SESSION_EXPIRED_EVENT } from "../api/client";
import { createAppQueryClient } from "../api/queryClient";
import type { Session } from "../api/types";
import { broadcastSessionRotated, broadcastSignedIn, broadcastSignedOut } from "./authSync";

const ACTIVITY_THROTTLE_MS = 30_000;

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export function useSessionLifecycle(initialQueryClient: QueryClient) {
  const [protectedQueryClient, setProtectedQueryClient] = useState(initialQueryClient);
  const [protectedQueryGeneration, setProtectedQueryGeneration] = useState(0);
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const protectedQueryClientRef = useRef(initialQueryClient);
  const sessionRef = useRef<Session | null>(null);
  const operationGenerationRef = useRef(0);
  const idleDeadlineRef = useRef<number | null>(null);
  const lastHeartbeatRef = useRef(0);

  const beginOperation = useCallback(() => {
    operationGenerationRef.current += 1;
    return operationGenerationRef.current;
  }, []);
  const isCurrentOperation = useCallback(
    (generation: number) => operationGenerationRef.current === generation,
    [],
  );
  const invalidateOperations = useCallback(() => {
    operationGenerationRef.current += 1;
  }, []);
  const rotateProtectedQueryClient = useCallback(() => {
    const previous = protectedQueryClientRef.current;
    void previous.cancelQueries();
    previous.clear();
    const next = createAppQueryClient();
    protectedQueryClientRef.current = next;
    setProtectedQueryClient(next);
    setProtectedQueryGeneration((generation) => generation + 1);
  }, []);
  const applySession = useCallback((next: Session | null) => {
    sessionRef.current = next;
    idleDeadlineRef.current = next ? Date.parse(next.idleExpiresAt ?? next.expiresAt) : null;
    setSession(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);
  const clearSession = useCallback(
    (broadcast = true) => {
      invalidateOperations();
      rotateProtectedQueryClient();
      applySession(null);
      if (broadcast) broadcastSignedOut();
    },
    [applySession, invalidateOperations, rotateProtectedQueryClient],
  );

  useEffect(() => {
    let active = true;
    const generation = beginOperation();
    void api
      .session()
      .then((nextSession) => {
        if (!active || !isCurrentOperation(generation)) return;
        protectedQueryClientRef.current.clear();
        applySession(nextSession);
      })
      .catch((error: unknown) => {
        if (!active || !isCurrentOperation(generation)) return;
        protectedQueryClientRef.current.clear();
        invalidateOperations();
        applySession(null);
        if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
      });
    return () => {
      active = false;
      invalidateOperations();
    };
  }, [applySession, beginOperation, invalidateOperations, isCurrentOperation]);

  useEffect(() => {
    const expireSession = () => clearSession();
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, [clearSession]);

  useEffect(() => {
    if (!session) return;
    const absoluteDeadline = Date.parse(session.expiresAt);
    const expireIfNeeded = () => {
      const idleDeadline = idleDeadlineRef.current ?? absoluteDeadline;
      if (Date.now() < Math.min(absoluteDeadline, idleDeadline)) return;
      void api.logout(session.csrfToken).catch(() => undefined);
      clearSession();
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
      void api
        .activity(current.csrfToken)
        .then(() => {
          if (sessionRef.current === current) {
            idleDeadlineRef.current = Date.now() + (current.idleTimeoutSeconds ?? 3_600) * 1_000;
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
    const expiry = window.setTimeout(
      () => {
        const current = sessionRef.current;
        if (current) applySession({ ...current, elevatedUntil: null });
      },
      Math.max(remaining, 0),
    );
    return () => window.clearTimeout(expiry);
  }, [applySession, session?.elevatedUntil]);

  const login = useCallback(
    async (input: { username: string; password: string }) => {
      const generation = beginOperation();
      const next = await api.login(input);
      if (!isCurrentOperation(generation)) {
        throw new ApiError("The sign-in attempt was interrupted.", 409);
      }
      rotateProtectedQueryClient();
      applySession(next);
      broadcastSignedIn();
      return next;
    },
    [applySession, beginOperation, isCurrentOperation, rotateProtectedQueryClient],
  );
  const elevate = useCallback(
    async (password: string) => {
      const current = sessionRef.current;
      if (!current) throw new ApiError("Sign in is required.", 401);
      const result = await api.elevate(password, current.csrfToken);
      const latest = sessionRef.current;
      if (latest && sameCredentialContext(current, latest)) {
        applySession({
          ...latest,
          csrfToken: result.csrfToken,
          elevatedUntil: result.elevatedUntil,
        });
      } else if (latest) {
        try {
          const authoritative = await api.session();
          if (sessionRef.current === latest) applySession(authoritative);
        } catch (error: unknown) {
          if (sessionRef.current === latest) {
            clearSession(false);
            if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
          }
        }
      }
      broadcastSessionRotated();
      return result.elevatedUntil;
    },
    [applySession, clearSession],
  );
  const logout = useCallback(async () => {
    const current = sessionRef.current;
    try {
      if (current) await api.logout(current.csrfToken);
    } finally {
      clearSession();
    }
  }, [clearSession]);

  return useMemo(
    () => ({
      applySession,
      beginOperation,
      clearSession,
      elevate,
      isCurrentOperation,
      login,
      logout,
      protectedQueryClient,
      protectedQueryClientRef,
      protectedQueryGeneration,
      rotateProtectedQueryClient,
      session,
      sessionRef,
      status,
    }),
    [
      applySession,
      beginOperation,
      clearSession,
      elevate,
      isCurrentOperation,
      login,
      logout,
      protectedQueryClient,
      protectedQueryGeneration,
      rotateProtectedQueryClient,
      session,
      status,
    ],
  );
}

export type SessionLifecycle = ReturnType<typeof useSessionLifecycle>;

function sameCredentialContext(left: Session, right: Session) {
  return (
    left.user.id === right.user.id &&
    left.activeContext === right.activeContext &&
    left.contextVersion === right.contextVersion
  );
}
