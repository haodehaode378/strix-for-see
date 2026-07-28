import {
  controlServiceFetch,
  controlServiceJson,
} from "../../shared/api/controlServiceClient";
import type {
  ExportOptions,
  Finding,
  FindingsResponse,
  FindingWorkflowState,
} from "./contracts";

export function getFindings(
  runName?: string,
  signal?: AbortSignal,
): Promise<FindingsResponse> {
  const query = runName ? `?run_name=${encodeURIComponent(runName)}` : "";
  return controlServiceJson<FindingsResponse>(`/api/findings${query}`, { signal });
}

export function getFinding(id: string, signal?: AbortSignal): Promise<Finding> {
  return controlServiceJson<Finding>(`/api/findings/${encodeURIComponent(id)}`, {
    signal,
  });
}

export function updateFinding(
  id: string,
  update: { workflowState?: FindingWorkflowState; note?: string },
): Promise<Finding> {
  return controlServiceJson<Finding>(`/api/findings/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
}

export async function exportFindings(options: ExportOptions): Promise<void> {
  const response = await controlServiceFetch("/api/findings/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  if (!response.ok) {
    throw new Error(`Report export failed with ${response.status}`);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename =
    disposition.match(/filename="([^"]+)"/)?.[1] ?? `strix-findings.${options.format}`;
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
