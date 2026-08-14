import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api/client";
import type { AccountContext, Session } from "../api/types";
import { broadcastContextChanged, parseAuthSyncEvent } from "./authSync";
import type { SessionLifecycle } from "./useSessionLifecycle";

const SWITCH_ERROR =
  "The workspace could not be switched. Your session was refreshed to protect your information.";

export function useContextSwitchController(lifecycle: SessionLifecycle) {
  const [contextSwitching, setContextSwitching] = useState(false);
  const [contextSwitchError, setContextSwitchError] = useState<string | null>(null);
  const [contextRevision, setContextRevision] = useState(0);

  const recordContextChange = useCallback(() => {
    setContextRevision((revision) => revision + 1);
  }, []);
  const dismissContextSwitchError = useCallback(() => {
    setContextSwitchError(null);
  }, []);

  const reconcileExternalContext = useCallback(() => {
    const generation = lifecycle.beginOperation();
    setContextSwitchError(null);
    setContextSwitching(true);
    lifecycle.rotateProtectedQueryClient();
    void api
      .session()
      .then((nextSession) => {
        if (!lifecycle.isCurrentOperation(generation)) return;
        lifecycle.applySession(nextSession);
        recordContextChange();
      })
      .catch((error: unknown) => {
        if (!lifecycle.isCurrentOperation(generation)) return;
        setContextSwitching(false);
        lifecycle.clearSession(false);
        if (!(error instanceof ApiError) || error.status !== 401) console.error(error);
      })
      .finally(() => {
        if (lifecycle.isCurrentOperation(generation)) setContextSwitching(false);
      });
  }, [lifecycle, recordContextChange]);

  useEffect(() => {
    const synchronise = (event: StorageEvent) => {
      const message = parseAuthSyncEvent(event);
      if (message.kind === "signed-out") {
        setContextSwitching(false);
        lifecycle.clearSession(false);
      } else if (message.kind === "context-changed") {
        reconcileExternalContext();
      }
    };
    window.addEventListener("storage", synchronise);
    return () => window.removeEventListener("storage", synchronise);
  }, [lifecycle, reconcileExternalContext]);

  const switchContext = useCallback(
    async (context: AccountContext) => {
      const current = lifecycle.sessionRef.current;
      validateContext(current, context);
      if (current.activeContext === context) return current;
      const generation = lifecycle.beginOperation();
      setContextSwitchError(null);
      setContextSwitching(true);
      lifecycle.rotateProtectedQueryClient();
      try {
        const next = await api.switchContext(context, current.csrfToken);
        if (!lifecycle.isCurrentOperation(generation)) return next;
        lifecycle.applySession(next);
        recordContextChange();
        broadcastContextChanged(next);
        return next;
      } catch (error: unknown) {
        const terminate = await recoverFailedSwitch(
          lifecycle,
          current,
          generation,
          recordContextChange,
        );
        if (terminate && lifecycle.isCurrentOperation(generation)) {
          setContextSwitching(false);
          lifecycle.clearSession();
        } else if (lifecycle.isCurrentOperation(generation)) {
          setContextSwitchError(SWITCH_ERROR);
        }
        throw error;
      } finally {
        if (lifecycle.isCurrentOperation(generation)) setContextSwitching(false);
      }
    },
    [lifecycle, recordContextChange],
  );

  return useMemo(
    () => ({
      contextRevision,
      contextSwitchError,
      contextSwitching,
      dismissContextSwitchError,
      recordContextChange,
      switchContext,
    }),
    [
      contextRevision,
      contextSwitchError,
      contextSwitching,
      dismissContextSwitchError,
      recordContextChange,
      switchContext,
    ],
  );
}

function validateContext(
  session: Session | null,
  context: AccountContext,
): asserts session is Session {
  if (!session) throw new ApiError("Sign in is required.", 401);
  if (!session.availableContexts.includes(context)) {
    throw new ApiError("That account context is not available.", 403);
  }
}

async function recoverFailedSwitch(
  lifecycle: SessionLifecycle,
  previous: Session,
  generation: number,
  recordContextChange: () => void,
): Promise<boolean> {
  let recovered: Session | null = null;
  try {
    recovered = await api.session();
  } catch {
    // A session that cannot be reconciled is terminated below.
  }
  if (!lifecycle.isCurrentOperation(generation)) return false;
  lifecycle.protectedQueryClientRef.current.clear();
  if (!recovered) return true;
  lifecycle.applySession(recovered);
  if (
    recovered.activeContext !== previous.activeContext ||
    recovered.contextVersion !== previous.contextVersion
  ) {
    recordContextChange();
    broadcastContextChanged(recovered);
  }
  return false;
}
