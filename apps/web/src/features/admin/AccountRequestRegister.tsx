import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { mailtoHref } from "../../lib/mailto";

export function AccountRequestRegister() {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const [notes, setNotes] = useState<Record<string, string>>({});
  const key = queryKeys.accountRequests();
  const requests = useQuery({ queryKey: key, queryFn: api.accountRequests });
  const review = useMutation({
    mutationFn: ({
      action,
      id,
      version,
    }: {
      action: "approve" | "reject";
      id: string;
      version: number;
    }) =>
      action === "approve"
        ? api.approveAccountRequest(id, version, session!.csrfToken)
        : api.rejectAccountRequest(id, version, notes[id]?.trim() ?? "", session!.csrfToken),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  });
  if (requests.isPending) return <PageState kind="loading" title="Loading account requests" />;
  if (requests.isError)
    return (
      <PageState
        action={
          <button className="button" onClick={() => void requests.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Account requests could not be loaded"
      />
    );
  const pending = requests.data.items.filter((item) => item.status === "PENDING");
  return (
    <section aria-labelledby="account-requests-title">
      <div className="section-heading">
        <span>Customer access</span>
        <h2 id="account-requests-title">Pending account requests</h2>
        <p>
          Approval creates a Customer account with the next MVP account ID. Arrange the assigned
          credentials with the requester outside Mist.
        </p>
      </div>
      {pending.length ? (
        <div className="account-request-list">
          {pending.map((item) => (
            <article key={item.id}>
              <header>
                <div>
                  <strong>{item.displayName}</strong>
                  <a href={mailtoHref(item.contactEmail)}>{item.contactEmail}</a>
                </div>
                <time dateTime={item.createdAt}>
                  {new Date(item.createdAt).toLocaleDateString("en-GB")}
                </time>
              </header>
              <p>{item.reason}</p>
              <label className="form-field">
                <span>Rejection reason</span>
                <input
                  onChange={(event) =>
                    setNotes((current) => ({ ...current, [item.id]: event.target.value }))
                  }
                  value={notes[item.id] ?? ""}
                />
              </label>
              <div className="form-actions">
                <button
                  className="button button--primary"
                  disabled={review.isPending}
                  onClick={() =>
                    review.mutate({ action: "approve", id: item.id, version: item.version })
                  }
                  type="button"
                >
                  Approve Customer account
                </button>
                <button
                  className="button button--danger"
                  disabled={review.isPending || (notes[item.id]?.trim().length ?? 0) < 3}
                  onClick={() =>
                    review.mutate({ action: "reject", id: item.id, version: item.version })
                  }
                  type="button"
                >
                  Reject
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <PageState kind="empty" title="No pending account requests">
          New requests from the sign-in page will appear here.
        </PageState>
      )}
      {review.isError ? (
        <p className="form-banner form-banner--error" role="alert">
          The account request could not be reviewed. Confirm sensitive changes and try again.
        </p>
      ) : null}
    </section>
  );
}
