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
import { DashboardPage } from "./pages/DashboardPage";
import { EmptySectionPage } from "./pages/EmptySectionPage";
import { EnvironmentPage } from "./pages/EnvironmentPage";
import { LocalRunDetailPage } from "./pages/LocalRunDetailPage";
import { LocalRunsPage } from "./pages/LocalRunsPage";
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
    if (path.startsWith("/local-runs/")) {
      return <LocalRunDetailPage id={decodeURIComponent(path.slice("/local-runs/".length))} />;
    }

    switch (path) {
      case "/setup":
        return <EnvironmentPage setup />;
      case "/scans/new":
        return (
          <EmptySectionPage
            title={t("newScan.title")}
            description={t("newScan.phaseNotice")}
            icon={ListPlus}
          />
        );
      case "/scans":
        return (
          <EmptySectionPage
            title={t("scans.title")}
            description={t("scans.empty")}
            icon={Activity}
          />
        );
      case "/local-runs":
        return <LocalRunsPage />;
      case "/findings":
        return (
          <EmptySectionPage
            title={t("findings.title")}
            description={t("findings.empty")}
            icon={ShieldCheck}
          />
        );
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

  return <AppShell navigation={navigation}>{page}</AppShell>;
}
