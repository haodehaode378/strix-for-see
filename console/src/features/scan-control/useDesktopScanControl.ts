import { useEffect } from "react";

import type { Scan } from "./contracts";
import { stopScan } from "./scanClient";

export function useDesktopScanControl(
  scan: Scan | null,
  setScan: (scan: Scan) => void,
  exitWarning: string,
) {
  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    let unlisten: (() => void) | undefined;
    let unlistenExit: (() => void) | undefined;
    void import("@tauri-apps/api/event").then(async ({ listen }) => {
      unlisten = await listen("tray-stop-scan", () => {
        if (
          scan &&
          ["queued", "preparing", "running", "reporting"].includes(scan.status)
        ) {
          void stopScan(scan.id).then(setScan);
        }
      });
      unlistenExit = await listen("tray-exit-request", () => {
        if (!scan || window.confirm(exitWarning)) {
          void import("@tauri-apps/api/core").then(({ invoke }) => invoke("exit_app"));
        }
      });
    });
    return () => {
      unlisten?.();
      unlistenExit?.();
    };
  }, [exitWarning, scan, setScan]);
}
