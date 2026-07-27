import type { ServiceHealth, SessionResponse } from "./contracts";

const SERVICE_BASE_URL = import.meta.env.VITE_CONTROL_SERVICE_URL ?? "http://127.0.0.1:43110";
let sessionToken: string | null = import.meta.env.VITE_CONTROL_TOKEN ?? null;

function takeBootstrapToken(): string | null {
  const url = new URL(window.location.href);
  const bootstrapToken = url.searchParams.get("bootstrap");
  if (!bootstrapToken) {
    return null;
  }

  url.searchParams.delete("bootstrap");
  window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  return bootstrapToken;
}

async function bootstrapSession(): Promise<string | null> {
  if (sessionToken) {
    return sessionToken;
  }

  const bootstrapToken = takeBootstrapToken();
  if (!bootstrapToken) {
    return null;
  }

  const response = await fetch(`${SERVICE_BASE_URL}/api/session`, {
    method: "POST",
    headers: {
      "X-Strix-Bootstrap": bootstrapToken,
    },
  });
  if (!response.ok) {
    throw new Error("Session bootstrap failed");
  }

  const session = (await response.json()) as SessionResponse;
  sessionToken = session.accessToken;
  return sessionToken;
}

export async function getServiceHealth(signal?: AbortSignal): Promise<ServiceHealth> {
  const token = await bootstrapSession();
  if (!token) {
    throw new Error("No in-memory control-service token");
  }

  const response = await fetch(`${SERVICE_BASE_URL}/api/health`, {
    headers: {
      "X-Strix-Access-Token": token,
    },
    signal,
  });
  if (!response.ok) {
    throw new Error(`Health request failed with ${response.status}`);
  }
  return (await response.json()) as ServiceHealth;
}
