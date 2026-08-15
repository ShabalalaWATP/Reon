import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, FileCheck2, LogIn, Moon, Route, ShieldCheck, Sun, Users } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { z } from "zod";

import { ApiError } from "../../lib/api/client";
import { useAuth } from "../../lib/auth/AuthProvider";
import { revealThroughMist } from "../../lib/mistReveal";
import { homeRouteForRole } from "../../lib/routes";
import { useTheme } from "../../lib/theme/ThemeProvider";
import { CloudField } from "./CloudField";
import { AccountRequestForm, PasswordAssistanceForm } from "./LoginAccessForms";

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
  const controller = useLoginController();
  if (controller.status === "authenticated" && controller.session) {
    return <Navigate replace to={homeRouteForRole(controller.session.user.role)} />;
  }
  return <LoginExperience controller={controller} />;
}

function useLoginController() {
  const { login, session, status } = useAuth();
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

  return {
    authError,
    changeMode,
    errors,
    handleSubmit,
    isSubmitting,
    mode,
    recovering,
    register,
    resetField,
    session,
    setRecovering,
    setShowPassword,
    showPassword,
    status,
    submit,
  };
}

type LoginController = ReturnType<typeof useLoginController>;

function LoginExperience({ controller }: { controller: LoginController }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <main className="login-page">
      <ThemeButton theme={theme} toggleTheme={toggleTheme} />
      <div className="login-composition">
        <LoginIntroduction />
        <LoginPanel controller={controller} />
      </div>
    </main>
  );
}

function ThemeButton({ theme, toggleTheme }: { theme: "dark" | "light"; toggleTheme: () => void }) {
  const dark = theme === "dark";
  return (
    <button className="login-theme" onClick={toggleTheme} type="button">
      {dark ? <Sun aria-hidden="true" size={17} /> : <Moon aria-hidden="true" size={17} />}
      <span className="sr-only">Use {dark ? "light" : "dark"} theme</span>
    </button>
  );
}

function LoginIntroduction() {
  return (
    <section className="login-intro" aria-labelledby="brand-title">
      <CloudField />
      <div className="login-logo-orbit">
        <img alt="" height="224" src="/mist-logo-256.png" width="224" />
      </div>
      <h1 id="brand-title">Mist</h1>
      <p className="login-kicker">Request. Coordinate. Deliver.</p>
      <p className="login-pitch">
        A precise workspace for submitting service needs and following product development to
        dissemination.
      </p>
      <ul className="login-points">
        {points.map(({ detail, icon: Icon, title }) => (
          <li key={title}>
            <Icon aria-hidden="true" size={19} />
            <span>
              <strong>{title}</strong>
              <small>{detail}</small>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function LoginPanel({ controller }: { controller: LoginController }) {
  return (
    <section className="login-panel" aria-labelledby="login-title">
      <div className="access-notice">
        <ShieldCheck aria-hidden="true" size={18} />
        Authorised account access
      </div>
      <div className="login-mode" aria-label="Account action" role="group">
        <button
          aria-pressed={controller.mode === "sign-in"}
          onClick={() => controller.changeMode("sign-in")}
          type="button"
        >
          Sign in
        </button>
        <button
          aria-pressed={controller.mode === "request-account"}
          onClick={() => controller.changeMode("request-account")}
          type="button"
        >
          Request account
        </button>
      </div>
      <LoginPanelContent controller={controller} />
    </section>
  );
}

function LoginPanelContent({ controller }: { controller: LoginController }) {
  if (controller.mode === "request-account") return <AccountRequestForm />;
  if (controller.recovering)
    return <PasswordAssistanceForm onBack={() => controller.setRecovering(false)} />;
  return <SignInForm controller={controller} />;
}

function SignInForm({ controller }: { controller: LoginController }) {
  const forgottenPassword = () => {
    controller.resetField("password");
    controller.setShowPassword(false);
    controller.setRecovering(true);
  };
  return (
    <form onSubmit={(event) => void controller.handleSubmit(controller.submit)(event)} noValidate>
      <header>
        <span>Account access</span>
        <h2 id="login-title">Sign in</h2>
        <p>Use your assigned Mist account to continue.</p>
      </header>
      <label className="form-field" htmlFor="username">
        Account ID
        <input autoComplete="username" id="username" {...controller.register("username")} />
        {controller.errors.username ? (
          <small role="alert">{controller.errors.username.message}</small>
        ) : null}
      </label>
      <PasswordField controller={controller} />
      <button className="back-link forgot-password-link" onClick={forgottenPassword} type="button">
        Forgotten password?
      </button>
      {controller.authError ? (
        <p className="form-error" role="alert">
          {controller.authError}
        </p>
      ) : null}
      <SignInButton controller={controller} />
    </form>
  );
}

function PasswordField({ controller }: { controller: LoginController }) {
  return (
    <label className="form-field" htmlFor="password">
      Password
      <span className="password-field">
        <input
          autoComplete="current-password"
          id="password"
          type={controller.showPassword ? "text" : "password"}
          {...controller.register("password")}
        />
        <button
          aria-label={controller.showPassword ? "Hide password" : "Show password"}
          onClick={() => controller.setShowPassword((value) => !value)}
          type="button"
        >
          {controller.showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </span>
      {controller.errors.password ? (
        <small role="alert">{controller.errors.password.message}</small>
      ) : null}
    </label>
  );
}

function SignInButton({ controller }: { controller: LoginController }) {
  let label = "Sign in to Mist";
  if (controller.status === "loading") label = "Checking session…";
  else if (controller.isSubmitting) label = "Signing in…";
  return (
    <button
      className="button button--primary button--wide"
      disabled={controller.isSubmitting || controller.status === "loading"}
      type="submit"
    >
      <LogIn aria-hidden="true" size={17} />
      {label}
    </button>
  );
}
