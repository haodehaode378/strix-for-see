import { createContext } from "react";

export interface NavigationContextValue {
  path: string;
  navigate: (path: string) => void;
}

export const NavigationContext = createContext<NavigationContextValue | null>(null);
