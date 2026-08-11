import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { EnvironmentPage } from "./EnvironmentPage";

const mocks = vi.hoisted(() => ({
  prepareSystem: vi.fn(),
  recheck: vi.fn(),
  checkSandboxUpdate: vi.fn(),
  startSandboxPull: vi.fn(),
}));

const report = {
  schemaVersion: 1,
  generatedAt: "2026-07-28T02:00:00Z",
  summary: {
    ready: false,
    requiredTotal: 2,
    requiredReady: 1,
    requiredFailures: 1,
    optionalWarnings: 1,
  },
  checks: [
    {
      id: "controlService",
      status: "ready",
      requirement: "required",
      value: "connected",
      issue: null,
    },
    {
      id: "dockerCli",
      status: "missing",
      requirement: "required",
      value: null,
      issue: "notInstalled",
    },
    {
      id: "git",
      status: "warning",
      requirement: "optional",
      value: null,
      issue: "notInstalled",
    },
  ],
} as const;

vi.mock("../features/system-readiness/useSystemReadiness", () => ({
  useSystemReadiness: () => ({
    state: "ready",
    retry: vi.fn(),
    recheck: mocks.recheck,
    report,
  }),
}));

vi.mock("../features/system-readiness/systemClient", () => ({
  getDiagnostics: vi.fn(),
  prepareSystem: mocks.prepareSystem,
  recheckSystem: vi.fn(),
}));

vi.mock("../features/updates/updatesClient", () => ({
  checkSandboxUpdate: mocks.checkSandboxUpdate,
  getSandboxPullStatus: vi.fn(),
  startSandboxPull: mocks.startSandboxPull,
}));

describe("EnvironmentPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.setItem("strix-console.locale", "en-US");
  });

  it("shows real required failures separately from optional notices", () => {
    render(
      <LocaleProvider>
        <EnvironmentPage />
      </LocaleProvider>,
    );

    expect(screen.getByText("Required items still need attention")).toBeInTheDocument();
    expect(screen.getByText("Docker CLI")).toBeInTheDocument();
    expect(screen.getByText("Git")).toBeInTheDocument();
    expect(screen.getAllByText("No installation was detected.")).toHaveLength(2);
  });

  it("prepares Docker and pulls a missing Sandbox image with one action", async () => {
    mocks.prepareSystem.mockResolvedValue({
      ...report,
      checks: [
        ...report.checks,
        {
          id: "dockerDaemon",
          status: "ready",
          requirement: "required",
          value: "29.6.1",
          issue: null,
        },
      ],
    });
    mocks.checkSandboxUpdate.mockResolvedValue({ available: true });
    mocks.startSandboxPull.mockResolvedValue({
      state: "completed",
      version: "1.3.0",
      image: "ghcr.io/usestrix/strix-sandbox:1.3.0",
      downloadedBytes: 1,
      totalBytes: 1,
      errorCode: null,
    });

    render(
      <LocaleProvider>
        <EnvironmentPage />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Prepare environment" }));

    await waitFor(() => expect(mocks.recheck).toHaveBeenCalled());
    expect(mocks.prepareSystem).toHaveBeenCalledOnce();
    expect(mocks.checkSandboxUpdate).toHaveBeenCalledOnce();
    expect(mocks.startSandboxPull).toHaveBeenCalledOnce();
    expect(screen.getByText("Automatic preparation completed")).toBeInTheDocument();
  });
});
