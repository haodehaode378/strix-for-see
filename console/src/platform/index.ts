import { browserAdapter } from "./browserAdapter";
import { desktopAdapter } from "./desktopAdapter";

function isTauriRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export const platform = isTauriRuntime() ? desktopAdapter : browserAdapter;
