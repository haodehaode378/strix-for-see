# Finding Identity and Local Review

Strix run files remain authoritative. The Console reads each run's `vulnerabilities.json` and
never writes workflow state or notes back into it.

## Stable Identity

Fingerprint version 1 normalizes and hashes the run target, title, CWE, endpoint, HTTP method, and
the first code location's file and start line. Source finding IDs such as `vuln-0001` are retained
as occurrence metadata but are not stable across runs.

Two records with the same fingerprint appear as one finding with multiple occurrences. A change to
the target, vulnerable endpoint, method, or primary code location intentionally creates a distinct
finding. The fingerprint algorithm is versioned so a future migration can preserve review data.

## Local Workflow

The review overlay is stored under `%LOCALAPPDATA%\StrixConsole\state\findings.json`. It contains
only the fingerprint, current state, notes, and append-only history. Valid transitions are:

```text
pending -> confirmed -> accepted risk | fixed | false positive
```

Notes may be added at any state. Removing a run removes its occurrence from the rebuilt index but
does not modify other run records.

## Safe Presentation and Export

Browser projections redact common credentials and the current user profile path. Finding content
is rendered as text or inside inert code blocks; the Console does not interpret source HTML or
Markdown. Exported HTML escapes all finding fields and applies a restrictive Content Security
Policy.

HTML, PDF, Markdown, and JSON exports support independent report language and options to omit
evidence, proof-of-concept content, and local paths. Credentials remain redacted regardless of
those options.
