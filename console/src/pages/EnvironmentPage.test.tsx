import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { EnvironmentPage } from "./EnvironmentPage";

vi.mock("../features/system-readiness/useSystemReadiness", () => ({
  useSystemReadiness: () => ({
    state: "ready",
    retry: vi.fn(),
    recheck: vi.fn(),
    report: {
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
    },
  }),
}));

describe("EnvironmentPage", () => {
  beforeEach(() => {
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
});
