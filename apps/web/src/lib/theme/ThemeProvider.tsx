/* eslint-disable react-refresh/only-export-components -- provider and its hook form one small boundary. */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Theme = "dark" | "light";
type ThemeContextValue = { theme: Theme; toggleTheme: () => void };

const storageKey = "istari-service-theme";
const ThemeContext = createContext<ThemeContextValue | null>(null);

function storedTheme(): Theme {
  return window.localStorage.getItem(storageKey) === "light" ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(storageKey, theme);
  }, [theme]);
  const value = useMemo(
    () => ({
      theme,
      toggleTheme: () => setTheme((value) => (value === "dark" ? "light" : "dark")),
    }),
    [theme],
  );
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used within ThemeProvider.");
  return context;
}
