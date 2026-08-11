import { describe, expect, it } from "vitest";

import type { Finding } from "./contracts";
import { findingExplanation } from "./findingExplanation";

const finding: Finding = {
  id: "finding-1",
  fingerprintVersion: 1,
  title: "Untranslated source title",
  severity: "high",
  workflowState: "pending",
  target: "https://example.test",
  description: null,
  impact: null,
  technicalAnalysis: null,
  evidence: null,
  pocDescription: null,
  pocScriptCode: null,
  remediationSteps: null,
  endpoint: null,
  method: null,
  cve: null,
  cwe: "CWE-79",
  cvss: null,
  locations: [],
  occurrences: [],
  history: [],
};

describe("findingExplanation", () => {
  it("prefers a stable CWE explanation", () => {
    expect(findingExplanation(finding)).toBe("xss");
  });

  it("falls back to a recognized title and then a generic explanation", () => {
    expect(findingExplanation({ ...finding, cwe: null, title: "SQL injection" })).toBe(
      "sqlInjection",
    );
    expect(findingExplanation({ ...finding, cwe: null })).toBe("generic");
  });
});
