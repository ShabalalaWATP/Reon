import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleX, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, ApiError } from "../../lib/api/client";
import type { RequestDetail } from "../../lib/api/types";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { isComplete } from "../../lib/status";

const schema = z.object({
  reason: z
    .string()
    .trim()
    .min(10, "Explain why the request is no longer required in at least 10 characters.")
    .max(1000),
});
type Values = z.infer<typeof schema>;

export function RequestCancellation({ request }: { request: RequestDetail }) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const {
    formState: { errors, isValid },
    handleSubmit,
    register,
    reset,
  } = useForm<Values>({
    defaultValues: { reason: "" },
    mode: "onChange",
    resolver: zodResolver(schema),
  });
  const mutation = useMutation({
    mutationFn: (values: Values) =>
      api.cancelRequest(
        request.id,
        { expectedVersion: request.version, reason: values.reason.trim() },
        session!.csrfToken,
      ),
    onSuccess: (cancelled) => {
      queryClient.setQueryData(queryKeys.request(request.id), cancelled);
      void queryClient.invalidateQueries({ queryKey: queryKeys.requests() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.actionsRoot() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.notificationCount() });
      reset();
      setOpen(false);
    },
  });

  if (isComplete(request.status)) return null;
  if (!open) {
    return (
      <section
        className="request-cancellation request-cancellation--closed"
        aria-labelledby="cancel-request-title"
      >
        <div>
          <span>Request control</span>
          <h2 id="cancel-request-title">No longer required?</h2>
          <p>Cancel this request and close the active workflow.</p>
        </div>
        <button className="button button--quiet" onClick={() => setOpen(true)} type="button">
          <CircleX aria-hidden="true" size={17} />
          Cancel request
        </button>
      </section>
    );
  }
  return (
    <section className="request-cancellation" aria-labelledby="cancel-request-title">
      <header>
        <TriangleAlert aria-hidden="true" size={19} />
        <div>
          <span>Permanent action</span>
          <h2 id="cancel-request-title">Cancel this request</h2>
          <p>
            This closes the request, stops active work and notifies the people already involved. It
            cannot be undone.
          </p>
        </div>
      </header>
      <form
        noValidate
        onSubmit={(event) => void handleSubmit((values) => mutation.mutate(values))(event)}
      >
        <label className="form-field">
          <span>
            Cancellation reason <b aria-hidden="true">*</b>
          </span>
          <textarea
            aria-invalid={Boolean(errors.reason)}
            required
            rows={4}
            {...register("reason")}
          />
          {errors.reason ? (
            <small role="alert">{errors.reason.message}</small>
          ) : (
            <small>10 to 1,000 characters. The reason is stored in request activity.</small>
          )}
        </label>
        {mutation.isError ? (
          <p className="form-banner form-banner--error" role="alert">
            {mutation.error instanceof ApiError
              ? mutation.error.message
              : "The request could not be cancelled."}
          </p>
        ) : null}
        <div className="form-actions">
          <button
            className="button button--danger"
            disabled={!isValid || mutation.isPending}
            type="submit"
          >
            {mutation.isPending ? "Cancelling…" : "Confirm cancellation"}
          </button>
          <button
            className="button"
            disabled={mutation.isPending}
            onClick={() => {
              reset();
              setOpen(false);
            }}
            type="button"
          >
            Keep request open
          </button>
        </div>
      </form>
    </section>
  );
}
