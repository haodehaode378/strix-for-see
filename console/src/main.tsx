import "@fontsource-variable/geist";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { LocaleProvider } from "./shared/i18n/LocaleProvider";
import { NavigationProvider } from "./shared/navigation/NavigationProvider";
import { ThemeProvider } from "./shared/theme/ThemeProvider";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <LocaleProvider>
        <NavigationProvider>
          <App />
        </NavigationProvider>
      </LocaleProvider>
    </ThemeProvider>
  </StrictMode>,
);
