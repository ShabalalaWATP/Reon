/* eslint-disable react-refresh/only-export-components -- context and hook form one boundary. */
import { QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";

import type { AccountContext, Session } from "../api/types";
import { useContextSwitchController } from "./useContextSwitchController";
import { useSessionLifecycle, type AuthStatus } from "./useSessionLifecycle";

type AuthContextValue = {
  session: Session | null;
  status: AuthStatus;
  login: (input: { username: string; password: string }) => Promise<Session>;
  elevate: (password: string) => Promise<string>;
  logout: () => Promise<void>;
  switchContext: (context: AccountContext) => Promise<Session>;
  contextSwitching: boolean;
  contextSwitchError: string | null;
  contextRevision: number;
  dismissContextSwitchError: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const initialQueryClient = useQueryClient();
  const lifecycle = useSessionLifecycle(initialQueryClient);
  const context = useContextSwitchController(lifecycle);
  const login = useCallback(
    async (input: { username: string; password: string }) => {
      const session = await lifecycle.login(input);
      context.recordContextChange();
      return session;
    },
    [context, lifecycle],
  );
  const value = useMemo<AuthContextValue>(
    () => ({
      session: lifecycle.session,
      status: lifecycle.status,
      login,
      elevate: lifecycle.elevate,
      logout: lifecycle.logout,
      switchContext: context.switchContext,
      contextSwitching: context.contextSwitching,
      contextSwitchError: context.contextSwitchError,
      contextRevision: context.contextRevision,
      dismissContextSwitchError: context.dismissContextSwitchError,
    }),
    [context, lifecycle, login],
  );

  return (
    <AuthContext.Provider value={value}>
      <QueryClientProvider
        client={lifecycle.protectedQueryClient}
        key={lifecycle.protectedQueryGeneration}
      >
        {children}
      </QueryClientProvider>
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}

export function isSessionElevated(session: Session | null): boolean {
  return Boolean(session?.elevatedUntil && Date.parse(session.elevatedUntil) > Date.now());
}
