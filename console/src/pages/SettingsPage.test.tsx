import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "../shared/i18n/LocaleProvider";
import { SettingsPage } from "./SettingsPage";

vi.mock("../features/updates/desktopUpdater", () => ({
  isDesktopRuntime: () => false,
  installDesktopUpdate: vi.fn(),
}));
vi.mock("../features/updates/updatesClient", () => ({
  checkApplicationUpdate: async () => ({
    currentVersion: "0.1.0",
    latestVersion: "0.2.0",
    available: true,
    installable: true,
    releaseUrl: "https://example.test/release",
    publishedAt: "2026-07-28T00:00:00Z",
  }),
  checkSandboxUpdate: async () => ({
    currentVersion: null,
    latestVersion: "1.4.0",
    image: "ghcr.io/haodehaode378/strix-for-see-sandbox:1.4.0",
    digest: `sha256:${"a".repeat(64)}`,
    sizeBytes: 104857600,
    compatible: true,
    available: true,
  }),
  authorizeApplicationUpdate: vi.fn(),
  startSandboxPull: vi.fn(),
  getSandboxPullStatus: vi.fn(),
}));

describe("SettingsPage", () => {
  it("shows real application and compatible Sandbox release metadata", async () => {
    render(
      <LocaleProvider>
        <SettingsPage />
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Check for updates" }));

    await waitFor(() => expect(screen.getByText("0.2.0")).toBeInTheDocument());
    expect(screen.getByText("1.4.0")).toBeInTheDocument();
    expect(screen.getByText("100 MB")).toBeInTheDocument();
    expect(screen.getByText(/Browser mode can check versions/)).toBeInTheDocument();
  });
});
