import type { PlatformAdapter } from "./PlatformAdapter";

export const browserAdapter: PlatformAdapter = {
  kind: "browser",
  canOpenNativePaths: false,
};
