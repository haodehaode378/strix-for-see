import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  type ResolvedTheme,
  ThemeContext,
  type ThemePreference,
} from "./themeContext";
const STORAGE_KEY = "strix-console.theme";
const themeOrder: ThemePreference[] = ["dark", "light", "system"];

function getInitialPreference(): ThemePreference {
  const savedTheme = window.localStorage.getItem(STORAGE_KEY);
  return savedTheme === "dark" || savedTheme === "light" || savedTheme === "system"
    ? savedTheme
    : "dark";
}

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference !== "system") {
    return preference;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setPreference] = useState<ThemePreference>(getInitialPreference);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    resolveTheme(getInitialPreference()),
  );

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const applyTheme = () => {
      const nextTheme = resolveTheme(preference);
      setResolvedTheme(nextTheme);
      document.documentElement.dataset.theme = nextTheme;
    };

    applyTheme();
    media.addEventListener("change", applyTheme);
    return () => media.removeEventListener("change", applyTheme);
  }, [preference]);

  const cycleTheme = useCallback(() => {
    setPreference((current) => {
      const next = themeOrder[(themeOrder.indexOf(current) + 1) % themeOrder.length];
      window.localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({ preference, resolvedTheme, cycleTheme }),
    [preference, resolvedTheme, cycleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
