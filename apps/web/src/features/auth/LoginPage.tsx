import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, FileCheck2, LogIn, Moon, Route, Send, ShieldCheck, Sun, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useLocation, useNavigate } from "react-router";
import { z } from "zod";

import { ApiError, api } from "../../lib/api/client";
import { useAuth } from "../../lib/auth/AuthProvider";
import { roleRoutes } from "../../lib/routes";
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
  const location = useLocation();
  const [showPassword, setShowPassword] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [mode, setMode] = useState<AuthMode>("sign-in");
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
  } = useForm<FormValues>({
    defaultValues: { password: "", username: "" },
    resolver: zodResolver(schema),
  });
  const requestedPath = (location.state as { from?: string } | null)?.from;

  if (status === "authenticated" && session) {
    return <Navigate replace to={requestedPath ?? roleRoutes[session.user.role]} />;
  }

  async function submit(values: FormValues) {
    setAuthError(null);
    try {
      const nextSession = await login(values);
      void navigate(requestedPath ?? roleRoutes[nextSession.user.role], { replace: true });
    } catch (error) {
      setAuthError(error instanceof ApiError ? error.message : "Unable to sign in. Try again.");
    }
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
            <button aria-pressed={mode === "sign-in"} onClick={() => setMode("sign-in")} type="button">Sign in</button>
            <button aria-pressed={mode === "request-account"} onClick={() => setMode("request-account")} type="button">Request account</button>
          </div>
          {mode === "sign-in" ? <form onSubmit={(event) => void handleSubmit(submit)(event)} noValidate>
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
    <label className="form-field" htmlFor="account-display-name">Display name <b aria-hidden="true">*</b><input aria-invalid={Boolean(errors.displayName)} id="account-display-name" required {...register("displayName")} />{errors.displayName ? <small role="alert">{errors.displayName.message}</small> : null}</label>
    <label className="form-field" htmlFor="account-email">Work email <b aria-hidden="true">*</b><input aria-invalid={Boolean(errors.contactEmail)} autoComplete="email" id="account-email" required type="email" {...register("contactEmail")} />{errors.contactEmail ? <small role="alert">{errors.contactEmail.message}</small> : null}</label>
    <label className="form-field" htmlFor="account-reason">Reason for access <b aria-hidden="true">*</b><textarea aria-invalid={Boolean(errors.reason)} id="account-reason" required rows={4} {...register("reason")} />{errors.reason ? <small role="alert">{errors.reason.message}</small> : null}</label>
    {result ? <p className="form-banner" role="status">{result}</p> : null}
    <button className="button button--primary button--wide" disabled={!isValid || isSubmitting} type="submit"><Send aria-hidden="true" size={17} />{isSubmitting ? "Submitting…" : "Submit account request"}</button>
  </form>;
}
