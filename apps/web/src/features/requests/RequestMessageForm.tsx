import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";

type Props = {
  audience: "CUSTOMER" | "CURRENT_OWNER";
  requestId: string;
};

export function RequestMessageForm({ audience, requestId }: Props) {
  const { session } = useAuth();
  const authenticated = session!;
  const client = useQueryClient();
  const [body, setBody] = useState("");
  const recipient = {
    CUSTOMER: "Customer",
    CURRENT_OWNER: "current owner",
  }[audience];
  const mutation = useMutation({
    mutationFn: () => api.postRequestCoordination(
      requestId,
      { audience, body },
      authenticated.csrfToken,
    ),
    onSuccess: async () => {
      setBody("");
      await client.invalidateQueries({
        queryKey: protectedQueryKeys.request(authenticated.user.id, requestId),
      });
    },
  });
  return (
    <section aria-label={`Message ${recipient}`} className="request-message-form">
      <h3>Message {recipient}</h3>
      <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}>
        <label className="form-field"><span>Question or information</span><textarea maxLength={2000} minLength={3} onChange={(event) => setBody(event.target.value)} required rows={3} value={body} /></label>
        <button className="button" disabled={mutation.isPending} type="submit">{mutation.isPending ? "Sending…" : "Send message"}</button>
      </form>
      {mutation.isError ? <p className="form-banner form-banner--error" role="alert">{mutation.error.message}</p> : null}
    </section>
  );
}
