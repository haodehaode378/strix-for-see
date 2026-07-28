import { useCallback, useEffect, useState } from "react";

import type { Scan } from "./contracts";
import { getScan, getScans } from "./scanClient";

type LoadState = "loading" | "ready" | "error";

export function useScans() {
  const [scans, setScans] = useState<Scan[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [attempt, setAttempt] = useState(0);
  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      getScans(controller.signal)
        .then((result) => {
          setScans(result.scans);
          setState("ready");
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setState("error");
        });
    void load();
    const interval = window.setInterval(() => void load(), 2000);
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [attempt]);

  return { scans, state, refresh };
}

export function useScan(id: string) {
  const [scan, setScan] = useState<Scan | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [attempt, setAttempt] = useState(0);
  const refresh = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const load = () =>
      getScan(id, controller.signal)
        .then((result) => {
          setScan(result);
          setState("ready");
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setState("error");
        });
    void load();
    const interval = window.setInterval(() => void load(), 1500);
    return () => {
      controller.abort();
      window.clearInterval(interval);
    };
  }, [id, attempt]);

  return { scan, state, refresh, setScan };
}
