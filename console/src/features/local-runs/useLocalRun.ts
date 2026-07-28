import { useEffect, useState } from "react";

import type { LocalRun } from "./contracts";
import { getLocalRun } from "./localRunsClient";

export function useLocalRun(id: string) {
  const [run, setRun] = useState<LocalRun | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const controller = new AbortController();
    getLocalRun(id, controller.signal)
      .then((result) => {
        setRun(result);
        setState("ready");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("error");
      });
    return () => controller.abort();
  }, [id]);

  return { run, state };
}
