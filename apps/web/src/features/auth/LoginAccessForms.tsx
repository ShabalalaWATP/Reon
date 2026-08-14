import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, KeyRound, Send } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { ApiError, api } from "../../lib/api/client";

const assistanceSchema = z.object({
  email: z.string().trim().email("Enter a valid work email.").max(254),
});
type AssistanceValues = z.infer<typeof assistanceSchema>;

export function PasswordAssistanceForm({ onBack }: { onBack: () => void }) {
  const [result, setResult] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const {
    formState: { errors, isSubmitting, isValid },
    handleSubmit,
    register,
  } = useForm<AssistanceValues>({
    defaultValues: { email: "" },
    mode: "onChange",
    resolver: zodResolver(assistanceSchema),
  });
  async function submitAssistance(values: AssistanceValues) {
    setFailed(false);
    setResult(null);
    try {
      const response = await api.requestPasswordAssistance(values.email);
      setResult(response.message);
    } catch {
      setFailed(true);
    }
  }
  return (
    <form onSubmit={(event) => void handleSubmit(submitAssistance)(event)} noValidate>
      <header>
        <span>Account assistance</span>
        <h2 id="login-title">Forgotten password</h2>
        <p>
          Enter the work email attached to your account. An administrator will be notified if it
          matches an active account.
        </p>
      </header>
      <label className="form-field" htmlFor="assistance-email">
        Work email <b aria-hidden="true">*</b>
        <input
          aria-invalid={Boolean(errors.email)}
          autoComplete="email"
          autoFocus
          id="assistance-email"
          required
          type="email"
          {...register("email")}
        />
        {errors.email ? <small role="alert">{errors.email.message}</small> : null}
      </label>
      {result ? (
        <p className="form-banner" role="status">
          {result}
        </p>
      ) : null}
      {failed ? (
        <p className="form-banner form-banner--error" role="alert">
          Unable to send the request. Try again shortly.
        </p>
      ) : null}
      <div className="login-recovery-actions">
        <button className="button button--quiet" onClick={onBack} type="button">
          <ArrowLeft aria-hidden="true" size={16} />
          Back to sign in
        </button>
        <button
          className="button button--primary"
          disabled={!isValid || isSubmitting}
          type="submit"
        >
          <KeyRound aria-hidden="true" size={16} />
          {isSubmitting ? "Notifying…" : "Notify administrator"}
        </button>
      </div>
    </form>
  );
}

const accountSchema = z.object({
  displayName: z.string().trim().min(2, "Enter your name.").max(120),
  contactEmail: z.string().trim().email("Enter a valid work email.").max(254),
  reason: z
    .string()
    .trim()
    .min(10, "Explain why you need access in at least 10 characters.")
    .max(1000),
});
type AccountValues = z.infer<typeof accountSchema>;

export function AccountRequestForm() {
  const [result, setResult] = useState<string | null>(null);
  const {
    formState: { errors, isSubmitting, isValid },
    handleSubmit,
    register,
  } = useForm<AccountValues>({
    defaultValues: { contactEmail: "", displayName: "", reason: "" },
    mode: "onChange",
    resolver: zodResolver(accountSchema),
  });
  async function submitRequest(values: AccountValues) {
    setResult(null);
    try {
      await api.requestAccount(values);
      setResult(
        "Request submitted. An administrator will review it and arrange your account details.",
      );
    } catch (error) {
      setResult(
        error instanceof ApiError
          ? error.message
          : "Unable to submit the account request. Try again.",
      );
    }
  }
  return (
    <form onSubmit={(event) => void handleSubmit(submitRequest)(event)} noValidate>
      <header>
        <span>New Customer access</span>
        <h2 id="login-title">Request an account</h2>
        <p>
          Tell the administrator who you are and why you need ISTARI access. Internal teams and
          routing are not part of this request.
        </p>
      </header>
      <label className="form-field" htmlFor="account-display-name">
        Name <b aria-hidden="true">*</b>
        <input
          aria-invalid={Boolean(errors.displayName)}
          autoComplete="name"
          id="account-display-name"
          required
          {...register("displayName")}
        />
        {errors.displayName ? <small role="alert">{errors.displayName.message}</small> : null}
      </label>
      <label className="form-field" htmlFor="account-email">
        Work email <b aria-hidden="true">*</b>
        <input
          aria-invalid={Boolean(errors.contactEmail)}
          autoComplete="email"
          id="account-email"
          required
          type="email"
          {...register("contactEmail")}
        />
        {errors.contactEmail ? <small role="alert">{errors.contactEmail.message}</small> : null}
      </label>
      <label className="form-field" htmlFor="account-reason">
        Reason for access <b aria-hidden="true">*</b>
        <textarea
          aria-invalid={Boolean(errors.reason)}
          id="account-reason"
          required
          rows={4}
          {...register("reason")}
        />
        {errors.reason ? <small role="alert">{errors.reason.message}</small> : null}
      </label>
      {result ? (
        <p className="form-banner" role="status">
          {result}
        </p>
      ) : null}
      <button
        className="button button--primary button--wide"
        disabled={!isValid || isSubmitting}
        type="submit"
      >
        <Send aria-hidden="true" size={17} />
        {isSubmitting ? "Submitting…" : "Submit account request"}
      </button>
    </form>
  );
}
