import { createContext } from "react";

import type { Locale, MessageKey } from "./messages";

export interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
}

export const LocaleContext = createContext<LocaleContextValue | null>(null);
