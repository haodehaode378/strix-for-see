export interface PlatformAdapter {
  readonly kind: "browser" | "desktop";
  canOpenNativePaths: boolean;
}
