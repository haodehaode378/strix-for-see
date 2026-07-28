import type { Locale } from "../../shared/i18n/messages";

export function formatRunDate(value: string | null, locale: Locale): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(locale, {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
}
