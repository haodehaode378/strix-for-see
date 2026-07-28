import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { NavigationProvider } from "../shared/navigation/NavigationProvider";
import { NewScanPage } from "./NewScanPage";

vi.mock("../features/system-readiness/useSystemReadiness", () => ({
  useSystemReadiness: () => ({
    state: "ready",
    report: { summary: { ready: true } },
    retry: vi.fn(),
    recheck: vi.fn(),
  }),
}));

describe("NewScanPage", () => {
  beforeEach(() => {
    window.localStorage.setItem("strix-console.locale", "en-US");
    window.history.replaceState({}, "", "/scans/new");
  });

  it("requires one primary target before advancing", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <NewScanPage />
        </NavigationProvider>
      </LocaleProvider>,
    );

    const continueButton = screen.getByRole("button", { name: "Continue" });
    expect(continueButton).toBeDisabled();
    expect(screen.getByRole("button", { name: /Web application/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Local directory/ })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Primary target"), {
      target: { value: "https://example.com" },
    });

    expect(continueButton).toBeEnabled();
  });
});
