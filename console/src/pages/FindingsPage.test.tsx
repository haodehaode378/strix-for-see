import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { NavigationProvider } from "../shared/navigation/NavigationProvider";
import { FindingsPage } from "./FindingsPage";

vi.mock("../features/findings/useFindings", () => ({
  useFindings: () => ({
    state: "ready",
    refresh: vi.fn(),
    data: {
      schemaVersion: 1,
      generatedAt: "2026-07-28T02:00:00Z",
      severityCounts: { critical: 0, high: 1, medium: 0, low: 1 },
      findings: [
        {
          id: "xss",
          fingerprintVersion: 1,
          title: "Stored <script>alert(1)</script>",
          severity: "high",
          workflowState: "pending",
          target: "https://example.com",
          description: null,
          impact: null,
          technicalAnalysis: null,
          evidence: null,
          pocDescription: null,
          pocScriptCode: null,
          remediationSteps: null,
          endpoint: "/profile",
          method: "POST",
          cve: null,
          cwe: "CWE-79",
          cvss: 8.1,
          locations: [],
          occurrences: [
            {
              runId: "run-one",
              runName: "run-one",
              target: "https://example.com",
              sourceFindingId: "vuln-1",
              observedAt: "2026-07-28T02:00:00Z",
            },
          ],
          history: [],
        },
        {
          id: "header",
          fingerprintVersion: 1,
          title: "Verbose response header",
          severity: "low",
          workflowState: "confirmed",
          target: "https://api.example.com",
          description: null,
          impact: null,
          technicalAnalysis: null,
          evidence: null,
          pocDescription: null,
          pocScriptCode: null,
          remediationSteps: null,
          endpoint: "/",
          method: "GET",
          cve: null,
          cwe: null,
          cvss: null,
          locations: [],
          occurrences: [
            {
              runId: "run-two",
              runName: "run-two",
              target: "https://api.example.com",
              sourceFindingId: "vuln-2",
              observedAt: "2026-07-27T02:00:00Z",
            },
          ],
          history: [],
        },
      ],
    },
  }),
}));

describe("FindingsPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("strix-console.locale", "en-US");
    window.history.replaceState({}, "", "/findings");
  });

  it("shows scan tasks before vulnerability details", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <FindingsPage />
        </NavigationProvider>
      </LocaleProvider>,
    );

    expect(screen.getByRole("link", { name: /run-one/ })).toHaveAttribute(
      "href",
      "/findings/task/run-one",
    );
    expect(screen.getByRole("link", { name: /run-two/ })).toBeInTheDocument();
    expect(screen.queryByText("Stored <script>alert(1)</script>")).not.toBeInTheDocument();
  });

  it("renders untrusted titles as inert text and filters one task's findings", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <FindingsPage runName="run-one" />
        </NavigationProvider>
      </LocaleProvider>,
    );

    expect(screen.getByText("Stored <script>alert(1)</script>")).toBeInTheDocument();
    expect(document.querySelector("script")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Severity"), {
      target: { value: "low" },
    });
    expect(screen.queryByText("Stored <script>alert(1)</script>")).not.toBeInTheDocument();
    expect(screen.getByText("Verbose response header")).toBeInTheDocument();
    expect(window.location.search).toContain("severity=low");
  });
});
