import { controlServiceJson } from "../../shared/api/controlServiceClient";
import type {
  ApplicationUpdate,
  SandboxPullStatus,
  SandboxUpdate,
} from "./contracts";

export function checkApplicationUpdate(): Promise<ApplicationUpdate> {
  return controlServiceJson<ApplicationUpdate>("/api/updates/application");
}

export function authorizeApplicationUpdate(): Promise<{ allowed: boolean }> {
  return controlServiceJson("/api/updates/application/authorize", { method: "POST" });
}

export function checkSandboxUpdate(): Promise<SandboxUpdate> {
  return controlServiceJson<SandboxUpdate>("/api/updates/sandbox");
}

export function startSandboxPull(): Promise<SandboxPullStatus> {
  return controlServiceJson<SandboxPullStatus>("/api/updates/sandbox/pull", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed: true }),
  });
}

export function getSandboxPullStatus(): Promise<SandboxPullStatus> {
  return controlServiceJson<SandboxPullStatus>("/api/updates/sandbox/pull");
}
