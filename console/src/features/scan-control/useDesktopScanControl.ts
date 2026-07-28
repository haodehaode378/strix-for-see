import { useEffect } from "react";

import type { Scan } from "./contracts";
import { stopScan } from "./scanClient";

export function useDesktopScanControl(
  scan: Scan | null,
  setScan: (scan: Scan) => void,
) {
  useEffect(() => {
    if (!("__TAURI_INTERNALS__" in window)) return;
    let unlisten: (() => void) | undefined;
    void import("@tauri-apps/api/event").then(async ({ listen }) => {
      unlisten = await listen("tray-stop-scan", () => {
        if (
          scan &&
          ["queued", "preparing", "running", "reporting"].includes(scan.status)
        ) {
          void stopScan(scan.id).then(setScan);
        }
      });
    });
    return () => unlisten?.();
  }, [scan, setScan]);
}
