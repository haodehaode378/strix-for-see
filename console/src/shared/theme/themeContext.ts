import { createContext } from "react";

export type ThemePreference = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

export interface ThemeContextValue {
  preference: ThemePreference;
  resolvedTheme: ResolvedTheme;
  cycleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);
