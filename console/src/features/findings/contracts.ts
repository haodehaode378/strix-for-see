export type FindingSeverity = "critical" | "high" | "medium" | "low";
export type FindingWorkflowState =
  | "pending"
  | "confirmed"
  | "acceptedRisk"
  | "fixed"
  | "falsePositive";

export interface FindingLocation {
  file: string | null;
  startLine: number | null;
  endLine: number | null;
  label: string | null;
  snippet: string | null;
}

export interface FindingOccurrence {
  runId: string;
  runName: string;
  target: string | null;
  sourceFindingId: string | null;
  observedAt: string | null;
}

export interface FindingHistoryEntry {
  id: string;
  occurredAt: string;
  kind: "stateChanged" | "noteAdded";
  fromState: FindingWorkflowState | null;
  toState: FindingWorkflowState | null;
  note: string | null;
}

export interface Finding {
  id: string;
  fingerprintVersion: number;
  title: string;
  severity: FindingSeverity;
  workflowState: FindingWorkflowState;
  target: string | null;
  description: string | null;
  impact: string | null;
  technicalAnalysis: string | null;
  evidence: string | null;
  pocDescription: string | null;
  pocScriptCode: string | null;
  remediationSteps: string | null;
  endpoint: string | null;
  method: string | null;
  cve: string | null;
  cwe: string | null;
  cvss: number | null;
  locations: FindingLocation[];
  occurrences: FindingOccurrence[];
  history: FindingHistoryEntry[];
}

export interface FindingsResponse {
  schemaVersion: number;
  generatedAt: string;
  findings: Finding[];
  severityCounts: Record<FindingSeverity, number>;
}

export type ReportFormat = "html" | "pdf" | "markdown" | "json";

export interface ExportOptions {
  format: ReportFormat;
  locale: "zh-CN" | "en-US";
  findingIds?: string[];
  redaction: {
    omitEvidence: boolean;
    omitPoc: boolean;
    omitPaths: boolean;
  };
}
