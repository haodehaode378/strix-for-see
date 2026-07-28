import {
  Activity,
  FileSearch,
  LayoutDashboard,
  ListPlus,
  Settings,
  ShieldCheck,
  Wrench,
} from "lucide-react";

import { AppShell, type NavigationItem } from "./components/layout/AppShell";
import { DesktopBridge } from "./components/scan/DesktopBridge";
import { DashboardPage } from "./pages/DashboardPage";
import { EmptySectionPage } from "./pages/EmptySectionPage";
import { EnvironmentPage } from "./pages/EnvironmentPage";
import { FindingDetailPage } from "./pages/FindingDetailPage";
import { FindingsPage } from "./pages/FindingsPage";
import { LocalRunDetailPage } from "./pages/LocalRunDetailPage";
import { LocalRunsPage } from "./pages/LocalRunsPage";
import { NewScanPage } from "./pages/NewScanPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ScansPage } from "./pages/ScansPage";
import { useLocale } from "./shared/i18n/useLocale";
import { useNavigation } from "./shared/navigation/useNavigation";

export function App() {
  const { t } = useLocale();
  const { path } = useNavigation();

  const navigation: NavigationItem[] = [
    { label: t("nav.dashboard"), path: "/dashboard", icon: LayoutDashboard },
    { label: t("nav.newScan"), path: "/scans/new", icon: ListPlus },
    { label: t("nav.scans"), path: "/scans", icon: Activity },
    { label: t("nav.localRuns"), path: "/local-runs", icon: FileSearch },
    { label: t("nav.findings"), path: "/findings", icon: ShieldCheck },
    { label: t("nav.environment"), path: "/system/environment", icon: Wrench },
    { label: t("nav.settings"), path: "/settings", icon: Settings },
  ];

  const page = (() => {
    if (path.startsWith("/findings/")) {
      return <FindingDetailPage id={decodeURIComponent(path.slice("/findings/".length))} />;
    }
    if (path.startsWith("/local-runs/")) {
      return <LocalRunDetailPage id={decodeURIComponent(path.slice("/local-runs/".length))} />;
    }
    if (path.startsWith("/scans/") && path !== "/scans/new") {
      return <ScanDetailPage id={decodeURIComponent(path.slice("/scans/".length))} />;
    }

    switch (path) {
      case "/setup":
        return <EnvironmentPage setup />;
      case "/scans/new":
        return <NewScanPage />;
      case "/scans":
        return <ScansPage />;
      case "/local-runs":
        return <LocalRunsPage />;
      case "/findings":
        return <FindingsPage />;
      case "/system/environment":
        return <EnvironmentPage />;
      case "/settings":
        return (
          <EmptySectionPage
            title={t("settings.title")}
            description={t("settings.phaseNotice")}
            icon={Settings}
          />
        );
      default:
        return <DashboardPage />;
    }
  })();

  return (
    <>
      <DesktopBridge />
      <AppShell navigation={navigation}>{page}</AppShell>
    </>
  );
}
