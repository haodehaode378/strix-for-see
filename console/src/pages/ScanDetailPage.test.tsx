import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { NavigationProvider } from "../shared/navigation/NavigationProvider";
import { ScanDetailPage } from "./ScanDetailPage";

const { terminateMock } = vi.hoisted(() => ({
  terminateMock: vi.fn(),
}));

vi.mock("../features/scan-control/useScans", () => ({
  useScan: () => ({
    state: "ready",
    refresh: vi.fn(),
    setScan: vi.fn(),
    scan: {
      id: "scan-id",
      status: "running",
      targetType: "web",
      target: "https://example.com",
      scope: {
        allowedHosts: [],
        allowedPorts: [],
        allowedPaths: [],
        exclusions: [],
      },
      options: {
        riskMode: "safe",
        scanProfile: "standard",
        requestRatePerMinute: 30,
        maxDurationMinutes: 60,
        maxBudgetUsd: 10,
        instructions: "",
      },
      queuePosition: null,
      engineRunName: "console-scan-id",
      createdAt: "2026-07-28T02:00:00Z",
      updatedAt: "2026-07-28T02:00:00Z",
      startedAt: "2026-07-28T02:01:00Z",
      endedAt: null,
      processId: 123,
      errorCode: null,
    },
  }),
}));

vi.mock("../features/scan-control/scanClient", () => ({
  stopScan: vi.fn(),
  terminateScan: terminateMock,
}));

describe("ScanDetailPage", () => {
  beforeEach(() => {
    terminateMock.mockReset();
    terminateMock.mockResolvedValue({});
    window.localStorage.setItem("strix-console.locale", "en-US");
    window.history.replaceState({}, "", "/scans/scan-id");
  });

  it("requires a separate emergency termination confirmation", async () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <ScanDetailPage id="scan-id" />
        </NavigationProvider>
      </LocaleProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Emergency terminate" }));
    expect(terminateMock).not.toHaveBeenCalled();
    expect(
      screen.getByText(/Emergency termination can leave partial records/),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Confirm immediate termination" }),
    );
    await waitFor(() => expect(terminateMock).toHaveBeenCalledWith("scan-id"));
  });
});
