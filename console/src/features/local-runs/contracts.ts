export type RunState =
  | "active"
  | "completed"
  | "interrupted"
  | "partial"
  | "malformed";

export interface LocalRun {
  id: string;
  sourceId: string;
  name: string;
  path: string;
  target: string | null;
  scanMode: string | null;
  state: RunState;
  engineStatus: string | null;
  startTime: string | null;
  endTime: string | null;
  updatedAt: string;
  severityCounts: Record<"critical" | "high" | "medium" | "low", number>;
  artifacts: Array<{ name: string; mediaType: string; sizeBytes: number }>;
  diagnostic: string | null;
}

export interface LocalRunsResponse {
  schemaVersion: number;
  scannedAt: string;
  sources: Array<{
    id: string;
    path: string;
    writable: boolean;
    exists: boolean;
  }>;
  runs: LocalRun[];
}
