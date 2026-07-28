interface SessionResponse {
  accessToken: string;
}

export class ControlServiceError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
  ) {
    super(code);
  }
}

const SERVICE_BASE_URL =
  import.meta.env.VITE_CONTROL_SERVICE_URL ?? "http://127.0.0.1:43110";
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

async function getSessionToken(): Promise<string> {
  if (sessionToken) {
    return sessionToken;
  }

  const bootstrapToken = takeBootstrapToken();
  if (!bootstrapToken) {
    throw new Error("No in-memory control-service token");
  }

  const response = await fetch(`${SERVICE_BASE_URL}/api/session`, {
    method: "POST",
    headers: { "X-Strix-Bootstrap": bootstrapToken },
  });
  if (!response.ok) {
    throw new Error("Session bootstrap failed");
  }

  const session = (await response.json()) as SessionResponse;
  sessionToken = session.accessToken;
  return sessionToken;
}

export async function controlServiceJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await getSessionToken();
  const headers = new Headers(init.headers);
  headers.set("X-Strix-Access-Token", token);
  const response = await fetch(`${SERVICE_BASE_URL}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let code = `http${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (typeof body.detail === "string") code = body.detail;
    } catch {
      // The status remains sufficient when an upstream response has no JSON body.
    }
    throw new ControlServiceError(response.status, code);
  }
  return (await response.json()) as T;
}

export async function downloadControlServiceFile(
  path: string,
  filename: string,
): Promise<void> {
  const token = await getSessionToken();
  const response = await fetch(`${SERVICE_BASE_URL}${path}`, {
    headers: { "X-Strix-Access-Token": token },
  });
  if (!response.ok) {
    throw new Error(`Artifact request failed with ${response.status}`);
  }

  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
