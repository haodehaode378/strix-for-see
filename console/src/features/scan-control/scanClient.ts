import { controlServiceJson } from "../../shared/api/controlServiceClient";
import type {
  CreateScanRequest,
  ProviderConfigRequest,
  ProviderStatus,
  ProviderTestResult,
  Scan,
  ScanListResponse,
} from "./contracts";

export function getScans(signal?: AbortSignal): Promise<ScanListResponse> {
  return controlServiceJson<ScanListResponse>("/api/scans", { signal });
}

export function getScan(id: string, signal?: AbortSignal): Promise<Scan> {
  return controlServiceJson<Scan>(`/api/scans/${encodeURIComponent(id)}`, { signal });
}

export function createScan(
  request: CreateScanRequest,
  idempotencyKey: string,
): Promise<Scan> {
  return controlServiceJson<Scan>("/api/scans", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Idempotency-Key": idempotencyKey,
    },
    body: JSON.stringify(request),
  });
}

export function stopScan(id: string): Promise<Scan> {
  return controlServiceJson<Scan>(`/api/scans/${encodeURIComponent(id)}/stop`, {
    method: "POST",
  });
}

export function terminateScan(id: string): Promise<Scan> {
  return controlServiceJson<Scan>(`/api/scans/${encodeURIComponent(id)}/terminate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed: true }),
  });
}

export function getProvider(signal?: AbortSignal): Promise<ProviderStatus> {
  return controlServiceJson<ProviderStatus>("/api/provider", { signal });
}

export function configureProvider(
  request: ProviderConfigRequest,
): Promise<ProviderStatus> {
  return controlServiceJson<ProviderStatus>("/api/provider", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function testProvider(): Promise<ProviderTestResult> {
  return controlServiceJson<ProviderTestResult>("/api/provider/test", {
    method: "POST",
  });
}
