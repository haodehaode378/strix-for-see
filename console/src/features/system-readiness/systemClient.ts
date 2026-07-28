import { controlServiceJson } from "../../shared/api/controlServiceClient";
import type { DiagnosticReport, SystemReport } from "./contracts";

export function getSystemReport(signal?: AbortSignal): Promise<SystemReport> {
  return controlServiceJson<SystemReport>("/api/system", { signal });
}

export function recheckSystem(): Promise<SystemReport> {
  return controlServiceJson<SystemReport>("/api/system/recheck", { method: "POST" });
}

export function getDiagnostics(): Promise<DiagnosticReport> {
  return controlServiceJson<DiagnosticReport>("/api/system/diagnostics");
}
