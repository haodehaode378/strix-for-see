import type { Finding } from "./contracts";

export type FindingExplanation =
  | "xss"
  | "sqlInjection"
  | "commandInjection"
  | "pathTraversal"
  | "ssrf"
  | "csrf"
  | "authentication"
  | "informationExposure"
  | "generic";

const cweExplanations: Record<string, FindingExplanation> = {
  "CWE-22": "pathTraversal",
  "CWE-78": "commandInjection",
  "CWE-79": "xss",
  "CWE-89": "sqlInjection",
  "CWE-200": "informationExposure",
  "CWE-287": "authentication",
  "CWE-352": "csrf",
  "CWE-918": "ssrf",
};

const titlePatterns: Array<[RegExp, FindingExplanation]> = [
  [/cross[- ]site scripting|\bxss\b/i, "xss"],
  [/sql injection|\bsqli\b/i, "sqlInjection"],
  [/command injection|remote code execution|\brce\b/i, "commandInjection"],
  [/path traversal|directory traversal/i, "pathTraversal"],
  [/server[- ]side request forgery|\bssrf\b/i, "ssrf"],
  [/cross[- ]site request forgery|\bcsrf\b/i, "csrf"],
  [/authentication|authorization|access control/i, "authentication"],
  [/information disclosure|information exposure|verbose|sensitive data/i, "informationExposure"],
];

export function findingExplanation(finding: Finding): FindingExplanation {
  if (finding.cwe && cweExplanations[finding.cwe.toUpperCase()]) {
    return cweExplanations[finding.cwe.toUpperCase()];
  }
  const searchable = [finding.title, finding.description, finding.technicalAnalysis]
    .filter(Boolean)
    .join(" ");
  return titlePatterns.find(([pattern]) => pattern.test(searchable))?.[1] ?? "generic";
}
