import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useRef } from "react";
import { z } from "zod";

import type { FeedbackInput } from "../../lib/api/types";

const schema = z.object({
  rating: z.number().int().min(1).max(5),
  comments: z.string().trim().min(3, "Tell the team about the service you received.").max(2000),
});
type Values = z.infer<typeof schema>;

export function FeedbackForm({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (input: FeedbackInput) => void;
}) {
  const submissionKey = useRef(globalThis.crypto.randomUUID());
  const {
    formState: { errors },
    handleSubmit,
    register,
  } = useForm<Values>({
    defaultValues: { rating: 5, comments: "" },
    resolver: zodResolver(schema),
  });
  return (
    <form
      className="feedback-form"
      onSubmit={(event) =>
        void handleSubmit((values) =>
          onSubmit({ ...values, submissionKey: submissionKey.current }),
        )(event)
      }
      noValidate
    >
      <p className="required-note">
        <span aria-hidden="true">*</span> Rating and comments are required.
      </p>
      <label className="form-field">
        <span>
          Rating <b aria-hidden="true">*</b>
        </span>
        <select required {...register("rating", { valueAsNumber: true })}>
          <option value="5">5, Excellent</option>
          <option value="4">4, Good</option>
          <option value="3">3, Satisfactory</option>
          <option value="2">2, Needs improvement</option>
          <option value="1">1, Unsatisfactory</option>
        </select>
        {errors.rating ? (
          <small className="field-error" role="alert">
            Choose a rating from 1 to 5.
          </small>
        ) : null}
      </label>
      <label className="form-field">
        <span>
          Service comments <b aria-hidden="true">*</b>
        </span>
        <textarea required rows={4} {...register("comments")} />
        {errors.comments ? (
          <small className="field-error" role="alert">
            {errors.comments.message}
          </small>
        ) : null}
      </label>
      <button className="button button--primary" disabled={disabled} type="submit">
        {disabled ? "Sending…" : "Send feedback"}
      </button>
    </form>
  );
}
