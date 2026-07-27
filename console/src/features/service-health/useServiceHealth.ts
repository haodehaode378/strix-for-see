import { useCallback, useEffect, useState } from "react";

import type { ServiceHealth } from "./contracts";
import { getServiceHealth } from "./serviceClient";

type ConnectionState = "loading" | "connected" | "unavailable";

export function useServiceHealth() {
  const [state, setState] = useState<ConnectionState>("loading");
  const [health, setHealth] = useState<ServiceHealth | null>(null);
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setState("loading");
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    getServiceHealth(controller.signal)
      .then((result) => {
        setHealth(result);
        setState("connected");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setHealth(null);
        setState("unavailable");
      });

    return () => controller.abort();
  }, [attempt]);

  return { state, health, retry };
}
