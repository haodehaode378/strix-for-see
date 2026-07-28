import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { NavigationContext } from "./navigationContext";

function currentPath(): string {
  return window.location.pathname === "/" ? "/dashboard" : window.location.pathname;
}

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [path, setPath] = useState(currentPath);

  useEffect(() => {
    const handlePopState = () => setPath(currentPath());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigate = useCallback((nextPath: string) => {
    if (nextPath === `${window.location.pathname}${window.location.search}`) {
      return;
    }
    window.history.pushState({}, "", nextPath);
    setPath(currentPath());
  }, []);

  const value = useMemo(() => ({ path, navigate }), [path, navigate]);
  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>;
}
