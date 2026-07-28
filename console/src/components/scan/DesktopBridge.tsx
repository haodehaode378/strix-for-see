import { useLiveEvents } from "../../features/scan-control/useLiveEvents";
import { useScans } from "../../features/scan-control/useScans";
import { useDesktopScanControl } from "../../features/scan-control/useDesktopScanControl";

const ACTIVE = ["queued", "preparing", "running", "reporting", "stopping"];

export function DesktopBridge() {
  const { scans } = useScans();
  const active = scans.find((scan) => ACTIVE.includes(scan.status)) ?? null;
  useDesktopScanControl(active, () => undefined);
  return active ? <ActiveEventNotifications scanId={active.id} /> : null;
}

function ActiveEventNotifications({ scanId }: { scanId: string }) {
  useLiveEvents(scanId);
  return null;
}
