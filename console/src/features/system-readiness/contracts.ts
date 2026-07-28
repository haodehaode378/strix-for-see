export type CheckStatus = "ready" | "warning" | "missing" | "error";

export interface SystemCheck {
  id: string;
  status: CheckStatus;
  requirement: "required" | "optional";
  value: string | null;
  issue: string | null;
}

export interface SystemReport {
  schemaVersion: number;
  generatedAt: string;
  summary: {
    ready: boolean;
    requiredTotal: number;
    requiredReady: number;
    requiredFailures: number;
    optionalWarnings: number;
  };
  checks: SystemCheck[];
}

export interface DiagnosticReport {
  schemaVersion: number;
  serviceVersion: string;
  system: SystemReport;
}
