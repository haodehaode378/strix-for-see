import { controlServiceJson } from "../../shared/api/controlServiceClient";
import type { ServiceHealth } from "./contracts";

export async function getServiceHealth(signal?: AbortSignal): Promise<ServiceHealth> {
  return controlServiceJson<ServiceHealth>("/api/health", { signal });
}
