import { useCallback, useEffect, useState } from "react";

import type { SystemReport } from "./contracts";
import { getSystemReport, recheckSystem } from "./systemClient";

type LoadState = "loading" | "ready" | "error";

export function useSystemReadiness() {
  const [state, setState] = useState<LoadState>("loading");
  const [report, setReport] = useState<SystemReport | null>(null);
  const [attempt, setAttempt] = useState(0);

  const retry = useCallback(() => {
    setState("loading");
    setAttempt((value) => value + 1);
  }, []);

  const recheck = useCallback(async () => {
    setState("loading");
    try {
      setReport(await recheckSystem());
      setState("ready");
    } catch {
      setState("error");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getSystemReport(controller.signal)
      .then((result) => {
        setReport(result);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") {
          return;
        }
        setState("error");
      });
    return () => controller.abort();
  }, [attempt]);

  return { state, report, retry, recheck };
}
