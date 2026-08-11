import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

vi.mock("../features/scan-control/useProvider", () => {
  const status = {
      configured: true,
      provider: "openai",
      model: "openai/gpt-5",
      apiBase: null,
      hasApiKey: true,
      connectionVerified: true,
  } as const;
  return {
    useProvider: () => ({ state: "ready", status, setStatus: vi.fn() }),
  };
});

describe("NewScanPage", () => {
  afterEach(cleanup);

  beforeEach(() => {
    window.localStorage.setItem("strix-console.locale", "en-US");
    window.history.replaceState({}, "", "/scans/new");
  });

  it("configures the model first and derives a strict boundary locally", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <NewScanPage />
        </NavigationProvider>
      </LocaleProvider>,
    );

    const continueButton = screen.getByRole("button", { name: "Continue" });
    expect(screen.getByRole("button", { name: "OpenAI" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(continueButton).toBeEnabled();
    fireEvent.click(continueButton);

    expect(continueButton).toBeDisabled();
    expect(screen.getByRole("button", { name: /Web application/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Local directory/ })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Primary target"), {
      target: { value: "https://example.com" },
    });

    expect(continueButton).toBeEnabled();
    fireEvent.click(continueButton);

    expect(screen.getByRole("button", { name: /Strict boundary/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByLabelText(/Additional allowed hosts/)).toHaveValue(
      "example.com",
    );
    expect(screen.getByLabelText(/Allowed ports/)).toHaveValue("443");
  });

  it("lets the operator choose Strix completion rules", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <NewScanPage />
        </NavigationProvider>
      </LocaleProvider>,
    );

    const continueButton = screen.getByRole("button", { name: "Continue" });
    fireEvent.click(continueButton);
    fireEvent.change(screen.getByLabelText("Primary target"), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(continueButton);
    fireEvent.click(continueButton);

    const consoleLimits = screen.getByRole("button", {
      name: /Console safety limits/,
    });
    const strixRules = screen.getByRole("button", { name: /Follow Strix rules/ });
    expect(consoleLimits).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("Maximum duration (minutes)")).toBeInTheDocument();

    fireEvent.click(strixRules);

    expect(strixRules).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByLabelText("Maximum duration (minutes)")).not.toBeInTheDocument();
    expect(
      screen.getByText(/no Console duration or budget protection/),
    ).toBeInTheDocument();
  });

  it("recognizes a Windows path and removes web-only scope fields", () => {
    render(
      <LocaleProvider>
        <NavigationProvider>
          <NewScanPage />
        </NavigationProvider>
      </LocaleProvider>,
    );

    const continueButton = screen.getByRole("button", { name: "Continue" });
    fireEvent.click(continueButton);
    fireEvent.change(screen.getByLabelText("Primary target"), {
      target: { value: "E:\\projects\\authorized-source" },
    });

    expect(screen.getByRole("button", { name: /Local directory/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    fireEvent.click(continueButton);

    expect(screen.getByText(/selected local directory and its descendants/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Additional allowed hosts/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Allowed ports/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Allowed paths/)).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Explicit exclusions/)).toBeInTheDocument();
  });
});
