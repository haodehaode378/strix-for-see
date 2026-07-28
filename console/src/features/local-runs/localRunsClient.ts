import {
  controlServiceJson,
  downloadControlServiceFile,
} from "../../shared/api/controlServiceClient";
import type { LocalRun, LocalRunsResponse } from "./contracts";

export function getLocalRuns(signal?: AbortSignal): Promise<LocalRunsResponse> {
  return controlServiceJson<LocalRunsResponse>("/api/local-runs", { signal });
}

export function getLocalRun(id: string, signal?: AbortSignal): Promise<LocalRun> {
  return controlServiceJson<LocalRun>(`/api/local-runs/${encodeURIComponent(id)}`, {
    signal,
  });
}

export function downloadArtifact(runId: string, name: string): Promise<void> {
  return downloadControlServiceFile(
    `/api/local-runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(name)}`,
    name,
  );
}
