import type { LucideIcon } from "lucide-react";
import { Languages, Moon, Shield, Sun } from "lucide-react";
import type { ReactNode } from "react";

import { useLocale } from "../../shared/i18n/useLocale";
import { NavigationLink } from "../../shared/navigation/NavigationLink";
import { useNavigation } from "../../shared/navigation/useNavigation";
import { useTheme } from "../../shared/theme/useTheme";

export interface NavigationItem {
  label: string;
  path: string;
  icon: LucideIcon;
}

interface AppShellProps {
  navigation: NavigationItem[];
  children: ReactNode;
}

export function AppShell({ navigation, children }: AppShellProps) {
  const { locale, setLocale, t } = useLocale();
  const { path } = useNavigation();
  const { resolvedTheme, cycleTheme } = useTheme();
  const ThemeIcon = resolvedTheme === "dark" ? Moon : Sun;

  return (
    <div className="mx-auto grid min-h-[100dvh] max-w-[1600px] grid-cols-1 md:grid-cols-[240px_1fr]">
      <a
        href="#main-content"
        className="fixed top-2 left-2 z-50 -translate-y-20 rounded-lg bg-[var(--surface)] px-3 py-2 text-sm font-semibold focus:translate-y-0"
      >
        {t("actions.skipToContent")}
      </a>
      <aside className="border-b border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] px-4 py-4 backdrop-blur-xl md:border-r md:border-b-0 md:px-5 md:py-6">
        <div className="flex items-center justify-between gap-4 md:block">
          <NavigationLink
            to="/dashboard"
            className="flex items-center gap-3 rounded-xl text-[var(--text)]"
            aria-label={t("app.name")}
          >
            <span className="grid size-9 place-items-center rounded-xl border border-[var(--border-strong)] bg-[var(--surface-raised)]">
              <Shield className="size-[18px] text-[var(--accent)]" strokeWidth={1.8} />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-[-0.02em]">{t("app.name")}</span>
              <span className="block text-[11px] text-[var(--text-muted)]">{t("app.localOnly")}</span>
            </span>
          </NavigationLink>

          <div className="flex items-center gap-1 md:hidden">
            <HeaderAction
              label={t("actions.switchLanguage")}
              onClick={() => setLocale(locale === "zh-CN" ? "en-US" : "zh-CN")}
              icon={Languages}
            />
            <HeaderAction label={t("actions.switchTheme")} onClick={cycleTheme} icon={ThemeIcon} />
          </div>
        </div>

        <nav
          className="nav-scroll mt-4 flex gap-1 overflow-x-auto pb-1 md:mt-8 md:block md:space-y-1 md:overflow-visible"
          aria-label={t("nav.primary")}
        >
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavigationLink
                key={item.path}
                to={item.path}
                className={
                  [
                    "group flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition duration-200 active:scale-[0.98]",
                    path === item.path ||
                    (item.path === "/local-runs" && path.startsWith("/local-runs/")) ||
                    (item.path === "/scans" &&
                      path.startsWith("/scans/") &&
                      path !== "/scans/new")
                      ? "bg-[var(--accent-soft)] text-[var(--accent-strong)]"
                      : "text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text)]",
                  ].join(" ")
                }
              >
                <Icon className="size-[17px]" strokeWidth={1.8} />
                {item.label}
              </NavigationLink>
            );
          })}
        </nav>

        <div className="mt-8 hidden border-t border-[var(--border)] pt-4 md:flex md:items-center md:justify-between">
          <HeaderAction
            label={t("actions.switchLanguage")}
            onClick={() => setLocale(locale === "zh-CN" ? "en-US" : "zh-CN")}
            icon={Languages}
            value={locale === "zh-CN" ? "中" : "EN"}
          />
          <HeaderAction
            label={t("actions.switchTheme")}
            onClick={cycleTheme}
            icon={ThemeIcon}
          />
        </div>
      </aside>

      <main id="main-content" className="min-w-0 px-4 py-6 sm:px-6 lg:px-10 lg:py-9">
        {children}
      </main>
    </div>
  );
}

interface HeaderActionProps {
  label: string;
  onClick: () => void;
  icon: LucideIcon;
  value?: string;
}

function HeaderAction({ label, onClick, icon: Icon, value }: HeaderActionProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      aria-label={label}
      className="flex h-9 items-center gap-2 rounded-lg px-2.5 text-xs font-semibold text-[var(--text-muted)] transition hover:bg-[var(--surface-muted)] hover:text-[var(--text)] active:scale-[0.98]"
    >
      <Icon className="size-4" strokeWidth={1.8} />
      {value ? <span>{value}</span> : null}
    </button>
  );
}
