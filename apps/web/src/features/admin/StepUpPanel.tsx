import { ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { ApiError } from "../../lib/api/client";
import { isSessionElevated, useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";

export function StepUpPanel() {
  const { elevate, session } = useAuth();
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elevated = isSessionElevated(session);
  const passwordRef = useRef<HTMLInputElement>(null);
  const wasElevated = useRef(elevated);
  useEffect(() => {
    if (wasElevated.current && !elevated) passwordRef.current?.focus();
    wasElevated.current = elevated;
  }, [elevated]);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!password) return;
    setPending(true);
    setError(null);
    try {
      await elevate(password);
      setPassword("");
    } catch (caught) {
      setPassword("");
      setError(caught instanceof ApiError ? caught.message : "Password confirmation failed.");
    } finally {
      setPending(false);
    }
  };
  if (elevated) {
    return (
      <section className="admin-step-up admin-step-up--ready" role="status">
        <ShieldCheck aria-hidden="true" size={18} />
        <div><strong>Sensitive changes enabled</strong><small>Until {formatDate(session!.elevatedUntil!, true)}</small></div>
      </section>
    );
  }
  return (
    <section aria-labelledby="step-up-title" className="admin-step-up">
      <ShieldCheck aria-hidden="true" size={18} />
      <div><strong id="step-up-title">Confirm sensitive changes</strong><p>Enter your current password to enable administration changes for five minutes.</p></div>
      <form onSubmit={(event) => void submit(event)}>
        <label className="sr-only">Account ID<input autoComplete="username" readOnly tabIndex={-1} type="text" value={session?.user.username ?? ""} /></label>
        <label className="form-field"><span>Current password <strong aria-hidden="true">*</strong></span><input autoComplete="current-password" onChange={(event) => setPassword(event.target.value)} ref={passwordRef} required type="password" value={password} /></label>
        <button className="button button--primary" disabled={pending || !password} type="submit">{pending ? "Confirming…" : "Confirm password"}</button>
        {error ? <p className="field-error" role="alert">{error}</p> : null}
      </form>
    </section>
  );
}
