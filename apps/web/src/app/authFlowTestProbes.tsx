import { useState } from "react";

import { useAuth } from "../lib/auth/AuthProvider";
import { useTheme } from "../lib/theme/ThemeProvider";

export function ThemeHookProbe() {
  useTheme();
  return null;
}

export function AuthHookProbe() {
  useAuth();
  return null;
}

export function AnonymousElevateProbe() {
  const { elevate } = useAuth();
  const [message, setMessage] = useState("");
  return (
    <>
      <button
        onClick={() => void elevate("admin").catch((error: Error) => setMessage(error.message))}
        type="button"
      >
        Attempt step-up
      </button>
      {message ? <p role="alert">{message}</p> : null}
    </>
  );
}
