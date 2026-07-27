import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LocaleProvider } from "./LocaleProvider";
import { useLocale } from "./useLocale";

function Probe() {
  const { t } = useLocale();
  return <span>{t("app.name")}</span>;
}

describe("LocaleProvider", () => {
  it("uses the saved English locale", () => {
    window.localStorage.setItem("strix-console.locale", "en-US");
    render(
      <LocaleProvider>
        <Probe />
      </LocaleProvider>,
    );
    expect(screen.getByText("Strix Console")).toBeInTheDocument();
  });
});
