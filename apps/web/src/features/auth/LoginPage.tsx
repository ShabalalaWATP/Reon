import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Eye, EyeOff, FileCheck2, KeyRound, LogIn, Moon, Route, Send, ShieldCheck, Sun, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { z } from "zod";

import { ApiError, api } from "../../lib/api/client";
import { useAuth } from "../../lib/auth/AuthProvider";
import { revealThroughMist } from "../../lib/mistReveal";
import { homeRouteForRole } from "../../lib/routes";
import { useTheme } from "../../lib/theme/ThemeProvider";
import { ParticleField } from "./ParticleField";

const schema = z.object({
  username: z.string().trim().min(1, "Enter your account ID.").max(64, "Account ID is too long."),
  password: z.string().min(1, "Enter your password.").max(256),
});
type FormValues = z.infer<typeof schema>;
type AuthMode = "sign-in" | "request-account";

const points = [
  {
    icon: FileCheck2,
    title: "Structured from the start",
    detail: "Capture the need, outcome and service product expectations in one clear request.",
  },
  {
    icon: Route,
    title: "Progress stays visible",
    detail: "Follow each routing, assignment, review and dissemination stage from one workspace.",
  },
  {
    icon: Users,
    title: "People make the decisions",
    detail: "Named people handle every routing, production and dissemination choice.",
  },
] as const;

export function LoginPage() {
  const { login, session, status } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const [recovering, setRecovering] = useState(false);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    resetField,
  } = useForm<FormValues>({
    defaultValues: { password: "", username: "" },
    resolver: zodResolver(schema),
  });
  if (status === "authenticated" && session) {
    return <Navigate replace to={homeRouteForRole(session.user.role)} />;
  }

  async function submit(values: FormValues) {
    setAuthError(null);
    try {
      const nextSession = await login(values);
      revealThroughMist();
      void navigate(homeRouteForRole(nextSession.user.role), { replace: true });
    } catch (error) {
      resetField("password");
      setShowPassword(false);
      setAuthError(error instanceof ApiError ? error.message : "Unable to sign in. Try again.");
    }
  }

  function changeMode(nextMode: AuthMode) {
    resetField("password");
    setShowPassword(false);
    setAuthError(null);
    setMode(nextMode);
    setRecovering(false);
  }

  return (
    <main className="login-page">
      <button className="login-theme" onClick={toggleTheme} type="button">
        {theme === "dark" ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
        <span className="sr-only">Use {theme === "dark" ? "light" : "dark"} theme</span>
      </button>
      <div className="login-composition">
        <section className="login-intro" aria-labelledby="brand-title">
          <ParticleField />
          <div className="login-logo-orbit">
            <img alt="" height="224" src="/istari-logo-256.png" width="224" />
          </div>
          <h1 id="brand-title">ISTARI</h1>
          <p className="login-kicker">Request. Coordinate. Deliver.</p>
          <p className="login-pitch">
            A precise workspace for submitting service needs and following product development to dissemination.
          </p>
          <ul className="login-points">
            {points.map(({ detail, icon: Icon, title }) => (
              <li key={title}>
                <Icon aria-hidden="true" size={19} />
                <span><strong>{title}</strong><small>{detail}</small></span>
              </li>
            ))}
          </ul>
        </section>
        <section className="login-panel" aria-labelledby="login-title">
          <div className="access-notice">
            <ShieldCheck aria-hidden="true" size={18} />Authorised account access
          </div>
          <div className="login-mode" aria-label="Account action" role="group">
            <button aria-pressed={mode === "sign-in"} onClick={() => changeMode("sign-in")} type="button">Sign in</button>
            <button aria-pressed={mode === "request-account"} onClick={() => changeMode("request-account")} type="button">Request account</button>
          </div>
          {mode === "sign-in" && recovering ? <PasswordAssistanceForm onBack={() => setRecovering(false)} /> : mode === "sign-in" ? <form onSubmit={(event) => void handleSubmit(submit)(event)} noValidate>
            <header>
              <span>Account access</span><h2 id="login-title">Sign in</h2>
              <p>Use your assigned ISTARI account to continue.</p>
            </header>
            <label className="form-field" htmlFor="username">
              Account ID
              <input autoComplete="username" id="username" {...register("username")} />
              {errors.username ? <small role="alert">{errors.username.message}</small> : null}
            </label>
            <label className="form-field" htmlFor="password">
              Password
              <span className="password-field">
                <input autoComplete="current-password" id="password" type={showPassword ? "text" : "password"} {...register("password")} />
                <button aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((value) => !value)} type="button">
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </span>
              {errors.password ? <small role="alert">{errors.password.message}</small> : null}
            </label>
            <button className="back-link forgot-password-link" onClick={() => { resetField("password"); setShowPassword(false); setRecovering(true); }} type="button">Forgotten password?</button>
            {authError ? <p className="form-error" role="alert">{authError}</p> : null}
            <button className="button button--primary button--wide" disabled={isSubmitting || status === "loading"} type="submit">
              <LogIn aria-hidden="true" size={17} />{status === "loading" ? "Checking session…" : isSubmitting ? "Signing in…" : "Sign in to ISTARI"}
            </button>
          </form> : <AccountRequestForm />}
        </section>
      </div>
    </main>
  );
}

const assistanceSchema = z.object({
  email: z.string().trim().email("Enter a valid work email.").max(254),
});
type AssistanceValues = z.infer<typeof assistanceSchema>;

function PasswordAssistanceForm({ onBack }: { onBack: () => void }) {
  const [result, setResult] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const { formState: { errors, isSubmitting, isValid }, handleSubmit, register } = useForm<AssistanceValues>({
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
  return <form onSubmit={(event) => void handleSubmit(submitAssistance)(event)} noValidate>
    <header><span>Account assistance</span><h2 id="login-title">Forgotten password</h2><p>Enter the work email attached to your account. An administrator will be notified if it matches an active account.</p></header>
    <label className="form-field" htmlFor="assistance-email">Work email <b aria-hidden="true">*</b><input aria-invalid={Boolean(errors.email)} autoComplete="email" autoFocus id="assistance-email" required type="email" {...register("email")} />{errors.email ? <small role="alert">{errors.email.message}</small> : null}</label>
    {result ? <p className="form-banner" role="status">{result}</p> : null}
    {failed ? <p className="form-banner form-banner--error" role="alert">Unable to send the request. Try again shortly.</p> : null}
    <div className="login-recovery-actions"><button className="button button--quiet" onClick={onBack} type="button"><ArrowLeft aria-hidden="true" size={16} />Back to sign in</button><button className="button button--primary" disabled={!isValid || isSubmitting} type="submit"><KeyRound aria-hidden="true" size={16} />{isSubmitting ? "Notifying…" : "Notify administrator"}</button></div>
  </form>;
}

const accountSchema = z.object({
  displayName: z.string().trim().min(2, "Enter your name.").max(120),
  contactEmail: z.string().trim().email("Enter a valid work email.").max(254),
  reason: z.string().trim().min(10, "Explain why you need access in at least 10 characters.").max(1000),
});
type AccountValues = z.infer<typeof accountSchema>;

function AccountRequestForm() {
  const [result, setResult] = useState<string | null>(null);
  const { formState: { errors, isSubmitting, isValid }, handleSubmit, register } = useForm<AccountValues>({
    defaultValues: { contactEmail: "", displayName: "", reason: "" },
    mode: "onChange",
    resolver: zodResolver(accountSchema),
  });
  async function submitRequest(values: AccountValues) {
    setResult(null);
    try {
      await api.requestAccount(values);
      setResult("Request submitted. An administrator will review it and arrange your account details.");
    } catch (error) {
      setResult(error instanceof ApiError ? error.message : "Unable to submit the account request. Try again.");
    }
  }
  return <form onSubmit={(event) => void handleSubmit(submitRequest)(event)} noValidate>
    <header><span>New Customer access</span><h2 id="login-title">Request an account</h2><p>Tell the administrator who you are and why you need ISTARI access. Internal teams and routing are not part of this request.</p></header>
    <label className="form-field" htmlFor="account-display-name">Name <b aria-hidden="true">*</b><input aria-invalid={Boolean(errors.displayName)} autoComplete="name" id="account-display-name" required {...register("displayName")} />{errors.displayName ? <small role="alert">{errors.displayName.message}</small> : null}</label>
    <label className="form-field" htmlFor="account-email">Work email <b aria-hidden="true">*</b><input aria-invalid={Boolean(errors.contactEmail)} autoComplete="email" id="account-email" required type="email" {...register("contactEmail")} />{errors.contactEmail ? <small role="alert">{errors.contactEmail.message}</small> : null}</label>
    <label className="form-field" htmlFor="account-reason">Reason for access <b aria-hidden="true">*</b><textarea aria-invalid={Boolean(errors.reason)} id="account-reason" required rows={4} {...register("reason")} />{errors.reason ? <small role="alert">{errors.reason.message}</small> : null}</label>
    {result ? <p className="form-banner" role="status">{result}</p> : null}
    <button className="button button--primary button--wide" disabled={!isValid || isSubmitting} type="submit"><Send aria-hidden="true" size={17} />{isSubmitting ? "Submitting…" : "Submit account request"}</button>
  </form>;
}
