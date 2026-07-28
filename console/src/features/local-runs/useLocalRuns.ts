import { useCallback, useEffect, useState } from "react";

import type { LocalRunsResponse } from "./contracts";
import { getLocalRuns } from "./localRunsClient";

export function useLocalRuns() {
  const [data, setData] = useState<LocalRunsResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const refresh = useCallback(() => {
    setState("loading");
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getLocalRuns(controller.signal)
      .then((result) => {
        setData(result);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, [attempt]);

  return { data, state, refresh };
}
