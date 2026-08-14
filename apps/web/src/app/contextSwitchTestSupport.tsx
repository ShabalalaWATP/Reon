/* eslint-disable react-refresh/only-export-components -- test support combines probes and fixtures. */
import { type QueryClient, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { disabledCapabilities } from "../lib/api/capabilityClient";
import { protectedQueryKeys } from "../lib/api/queryKeys";
import type { Session } from "../lib/api/types";
import { useAuth } from "../lib/auth/AuthProvider";
import { requesterSession, staffSession } from "../test/fixtures";
import { json, mockFeatureFetch, type FetchHandler } from "../test/render";

export const dualStaffSession: Session = {
  ...staffSession,
  availableContexts: ["STAFF", "CUSTOMER"],
  contextVersion: 4,
};

export const switchedCustomerSession: Session = {
  ...requesterSession,
  availableContexts: ["STAFF", "CUSTOMER"],
  contextVersion: 5,
  csrfToken: "rotated-customer-csrf",
  user: {
    ...requesterSession.user,
    id: dualStaffSession.user.id,
    username: dualStaffSession.user.username,
    displayName: dualStaffSession.user.displayName,
  },
};

const contextCapabilities = {
  ...disabledCapabilities,
  contextSwitching: true,
};

export function mockContextFetch(handler: FetchHandler) {
  return mockFeatureFetch((url, init) =>
    url.pathname.endsWith("/me/capabilities") ? json(contextCapabilities) : handler(url, init),
  );
}

export function ContextBoundaryProbe() {
  const auth = useAuth();
  const [message, setMessage] = useState("");
  return (
    <>
      <button
        disabled={auth.status !== "authenticated"}
        onClick={() => {
          void auth.switchContext("CUSTOMER").catch((error: unknown) => {
            setMessage(error instanceof Error ? error.message : "Unexpected error");
          });
        }}
        type="button"
      >
        Try unavailable context
      </button>
      <output>{message}</output>
    </>
  );
}

export function LateMutationProbe({
  clients,
  operation,
}: {
  clients: QueryClient[];
  operation: Promise<string>;
}) {
  const auth = useAuth();
  const client = useQueryClient();
  const staffKey = protectedQueryKeys(dualStaffSession).requests();
  const mutation = useMutation({
    mutationFn: () => operation,
    onSuccess: (value) => client.setQueryData(staffKey, value),
  });
  useEffect(() => {
    if (!clients.includes(client)) clients.push(client);
  }, [client, clients]);
  return (
    <>
      <button onClick={() => mutation.mutate()} type="button">
        Start staff request
      </button>
      <button onClick={() => void auth.switchContext("CUSTOMER")} type="button">
        Switch context
      </button>
      <output>{auth.session?.activeContext}</output>
    </>
  );
}
