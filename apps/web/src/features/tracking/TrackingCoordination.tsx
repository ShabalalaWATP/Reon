import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TrackedRequestDetail } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";

export function TrackingCoordination({ request }: { request: TrackedRequestDetail }) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const authenticated = session!;
  const client = useQueryClient();
  const [targetUnitId, setTargetUnitId] = useState(request.route[0].id);
  const [reason, setReason] = useState("");
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: queryKeys.trackedRequest(request.id) });
  };
  const ownershipReturn = useMutation({
    mutationFn: () =>
      api.requestOwnershipReturn(request.id, { targetUnitId, reason }, authenticated.csrfToken),
    onSuccess: async () => {
      setReason("");
      await refresh();
    },
  });
  return (
    <section
      aria-labelledby="tracking-coordination-title"
      className="detail-section tracking-coordination"
    >
      <div className="section-heading">
        <span>Governed ownership</span>
        <h2 id="tracking-coordination-title">Request ownership return</h2>
      </div>
      <div className="tracking-coordination__forms tracking-coordination__forms--single">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            ownershipReturn.mutate();
          }}
        >
          <h3>Ask for ownership to be returned</h3>
          <p>This records a request for the current owner. It does not seize their work.</p>
          <label className="form-field">
            <span>Return to</span>
            <select
              onChange={(event) => setTargetUnitId(event.target.value)}
              required
              value={targetUnitId}
            >
              {request.route.map((unit) => (
                <option key={unit.id} value={unit.id}>
                  {unit.name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span>Reason</span>
            <textarea
              maxLength={2000}
              minLength={10}
              onChange={(event) => setReason(event.target.value)}
              required
              rows={4}
              value={reason}
            />
          </label>
          <button className="button" disabled={ownershipReturn.isPending} type="submit">
            {ownershipReturn.isPending ? "Requesting…" : "Request return"}
          </button>
        </form>
      </div>
      {ownershipReturn.error ? (
        <p className="form-banner form-banner--error" role="alert">
          {ownershipReturn.error.message}
        </p>
      ) : null}
    </section>
  );
}
