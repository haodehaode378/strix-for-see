import {
  controlServiceFetch,
  controlServiceJson,
} from "../../shared/api/controlServiceClient";
import type {
  ExportOptions,
  ExportResult,
  Finding,
  FindingsResponse,
  FindingWorkflowState,
} from "./contracts";

export function getFindings(
  runId?: string,
  signal?: AbortSignal,
): Promise<FindingsResponse> {
  const path = runId
    ? `/api/runs/${encodeURIComponent(runId)}/findings`
    : "/api/findings";
  return controlServiceJson<FindingsResponse>(path, { signal });
}

export function getFinding(
  id: string,
  runId: string,
  signal?: AbortSignal,
): Promise<Finding> {
  const path = `/api/runs/${encodeURIComponent(runId)}/findings/${encodeURIComponent(id)}`;
  return controlServiceJson<Finding>(path, {
    signal,
  });
}

export function updateFinding(
  id: string,
  update: { workflowState?: FindingWorkflowState; note?: string },
  runId: string,
): Promise<Finding> {
  const path = `/api/runs/${encodeURIComponent(runId)}/findings/${encodeURIComponent(id)}`;
  return controlServiceJson<Finding>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export function exportFindings(options: ExportOptions): Promise<ExportResult> {
  return controlServiceJson<ExportResult>("/api/findings/export-file", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
}

export async function openExportFolder(): Promise<void> {
  const response = await controlServiceFetch("/api/findings/export-folder", {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(`Export folder could not be opened (${response.status})`);
  }
}
