export interface ServiceHealth {
  status: "ok";
  serviceVersion: string;
  schemaVersion: number;
  platform: "windows";
}

export interface SessionResponse {
  accessToken: string;
}
