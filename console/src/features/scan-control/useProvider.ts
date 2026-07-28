import { useCallback, useEffect, useState } from "react";

import type { ProviderStatus } from "./contracts";
import { getProvider } from "./scanClient";

export function useProvider() {
  const [status, setStatus] = useState<ProviderStatus | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    getProvider(controller.signal)
      .then((result) => {
        setStatus(result);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, [attempt]);

  return { status, state, refresh, setStatus };
}
