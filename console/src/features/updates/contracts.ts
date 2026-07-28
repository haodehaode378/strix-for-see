export interface ApplicationUpdate {
  currentVersion: string;
  latestVersion: string | null;
  available: boolean;
  installable: boolean;
  releaseUrl: string | null;
  publishedAt: string | null;
}

export interface SandboxUpdate {
  currentVersion: string | null;
  latestVersion: string;
  image: string;
  digest: string;
  sizeBytes: number;
  compatible: boolean;
  available: boolean;
}

export type SandboxPullState =
  | "idle"
  | "downloading"
  | "verifying"
  | "completed"
  | "failed";

export interface SandboxPullStatus {
  state: SandboxPullState;
  version: string | null;
  image: string | null;
  downloadedBytes: number;
  totalBytes: number;
  errorCode: string | null;
}
