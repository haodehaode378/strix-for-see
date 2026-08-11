export type TargetType = "web" | "local" | "repository" | "network";
export type RiskMode = "safe" | "full";
export type ScanProfile = "quick" | "standard" | "deep";
export type TerminationPolicy = "consoleLimits" | "strixRules";
export type ScanStatus =
  | "validating"
  | "queued"
  | "preparing"
  | "running"
  | "reporting"
  | "completed"
  | "stopping"
  | "stopped"
  | "terminating"
  | "terminated"
  | "failed";

export interface ScopeConfig {
  allowedHosts: string[];
  allowedPorts: number[];
  allowedPaths: string[];
  exclusions: string[];
}

export interface ScanOptions {
  riskMode: RiskMode;
  scanProfile: ScanProfile;
  terminationPolicy: TerminationPolicy;
  requestRatePerMinute: number;
  maxDurationMinutes: number;
  maxBudgetUsd: number;
  instructions: string;
}

export interface CreateScanRequest {
  targetType: TargetType;
  target: string;
  scope: ScopeConfig;
  options: ScanOptions;
  authorizationConfirmed: boolean;
  fullModeConfirmed: boolean;
}

export interface Scan {
  id: string;
  status: ScanStatus;
  targetType: TargetType;
  target: string;
  scope: ScopeConfig;
  options: ScanOptions;
  queuePosition: number | null;
  engineRunName: string;
  createdAt: string;
  updatedAt: string;
  startedAt: string | null;
  endedAt: string | null;
  processId: number | null;
  errorCode: string | null;
}

export interface ScanListResponse {
  schemaVersion: number;
  scans: Scan[];
}

export type ProviderKind =
  | "openai"
  | "anthropic"
  | "gemini"
  | "openaiCompatible"
  | "ollama";

export interface ProviderStatus {
  configured: boolean;
  provider: ProviderKind | null;
  model: string | null;
  apiBase: string | null;
  hasApiKey: boolean;
  connectionVerified: boolean;
}

export interface ProviderConfigRequest {
  provider: ProviderKind;
  model: string;
  apiBase: string | null;
  apiKey: string | null;
}

export interface ProviderModelsRequest {
  provider: ProviderKind;
  apiBase: string | null;
  apiKey: string | null;
}

export interface ProviderModelsResponse {
  models: string[];
}

export interface ProviderTestResult {
  ok: boolean;
  issue: string | null;
}

export type LiveConnectionState =
  | "connecting"
  | "live"
  | "reconnecting"
  | "closed";

export interface ScanEvent {
  schemaVersion: number;
  eventId: string;
  scanId: string;
  occurredAt: string;
  type: string;
  actor: {
    kind: "scan" | "agent" | "tool" | "runtime" | "operator" | "system";
    id: string | null;
  } | null;
  payload: Record<string, unknown>;
}

export interface SteeringResponse {
  accepted: boolean;
  eventId: string;
}
