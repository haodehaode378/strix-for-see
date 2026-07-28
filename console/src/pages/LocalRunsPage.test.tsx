import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { NavigationProvider } from "../shared/navigation/NavigationProvider";
import { LocalRunsPage } from "./LocalRunsPage";

vi.mock("../features/local-runs/useLocalRuns", () => ({
  useLocalRuns: () => ({
    state: "ready",
    refresh: vi.fn(),
    data: {
      schemaVersion: 1,
      scannedAt: "2026-07-28T02:00:00Z",
      sources: [{ id: "source", path: "C:/runs", writable: false, exists: true }],
      runs: [
        {
          id: "run-id",
          sourceId: "source",
          name: "Broken run",
          path: "C:/runs/broken",
          target: null,
          scanMode: null,
          state: "malformed",
          engineStatus: null,
          startTime: null,
          endTime: null,
          updatedAt: "2026-07-28T02:00:00Z",
          severityCounts: { critical: 0, high: 0, medium: 0, low: 0 },
          artifacts: [],
          diagnostic: "invalidRunRecord",
        },
      ],
    },
  }),
}));

describe("LocalRunsPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("strix-console.locale", "en-US");
    window.history.replaceState({}, "", "/local-runs");
  });

  it("keeps malformed disk records visible", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <LocalRunsPage />
        </NavigationProvider>
      </LocaleProvider>,
    );

    expect(screen.getByText("Broken run")).toBeInTheDocument();
    expect(screen.getByText("Malformed")).toBeInTheDocument();
    expect(screen.getByText(/run.json cannot be parsed/)).toBeInTheDocument();
  });
});
