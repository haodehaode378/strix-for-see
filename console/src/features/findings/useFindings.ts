import { useCallback, useEffect, useState } from "react";

import type { Finding, FindingsResponse } from "./contracts";
import { getFinding, getFindings } from "./findingsClient";

export function useFindings(runId?: string) {
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const refresh = useCallback(() => {
    setState("loading");
    setAttempt((value) => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getFindings(runId, controller.signal).then(
      (value) => {
        setData(value);
        setState("ready");
      },
      (error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      },
    );
    return () => controller.abort();
  }, [attempt, runId]);
  return { data, state, refresh };
}

export function useFinding(id: string, runId: string) {
  const [finding, setFinding] = useState<Finding | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    getFinding(id, runId, controller.signal).then(
      (value) => {
        setFinding(value);
        setState("ready");
      },
      (error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setFinding(null);
        setState("error");
      },
    );
    return () => controller.abort();
  }, [id, runId]);
  return { finding, setFinding, state };
}
