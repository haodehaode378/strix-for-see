# Strix Console Product Requirements

## Product Goal and Boundaries

Build `Strix Console` (`Strix 控制台`), a local-first Windows application for controlling and
observing authorized Strix penetration tests. The React interface must work inside a Tauri desktop
shell and from a local browser. It is independent of the bundled Viewer and may consult that code
only for behavior, events, and run-file formats.

The first release serves one Windows user without login, cloud sync, telemetry, scheduling, or
remote access. Docker Desktop is an external prerequisite; the application detects it and explains
how to install or repair it. The desktop package bundles a compatible control service and Strix
runtime, so users do not install Python or Strix separately.

## Language and Appearance

All user-facing copy, statuses, validation messages, dates, and reports support Simplified Chinese
and English. The first launch follows the Windows display language: Chinese systems use Simplified
Chinese and all others use English. Language changes apply immediately. Report language is selected
separately.

Use a professional security-console style. Dark is the default theme, with light and
follow-Windows options. Avoid decorative “hacker” effects and fake progress percentages. Technical
logs are collapsed by default.

## Core Business Objects

| Object | Responsibility |
| --- | --- |
| `Scan` | Configuration, queue position, and lifecycle of one run |
| `Target` | One primary URL, local directory, Git repository, IP, or domain |
| `Agent` | Root or child worker, parent, task, status, and last activity |
| `Event` | Ordered lifecycle, message, finding, usage, error, or tool activity |
| `ToolCall` | Tool name, redacted input/output summary, state, and duration |
| `Finding` | Severity, evidence, PoC, affected location, workflow state, and remediation |
| `Runtime` | Docker, sandbox image, workspace, mounts, network, and health |
| `Report` | Local HTML, PDF, Markdown, or JSON artifact |
| `SteeringMessage` | Operator instruction sent to an active scan |

## Information Architecture

- `/setup`: first-run readiness and guided remediation.
- `/dashboard`: active/queued task, recent findings and runs, environment health, and create action.
- `/scans/new`: guided scan creation.
- `/scans` and `/scans/:id`: scan history and live/historical workspace.
- `/local-runs` and `/local-runs/:id`: disk-backed records and artifacts.
- `/findings`: findings aggregated across scans.
- `/settings`: language, theme, providers, defaults, paths, notifications, and updates.
- `/system/environment`: detailed checks, versions, storage, logs, and diagnostics.

## Environment Readiness

Check Docker CLI, daemon and version; WSL 2 and virtualization; control-service, Strix, and sandbox
versions; model-provider configuration and connectivity; run-directory access; disk capacity; and
optional Git capability. Every check shows required/optional status, detected value, impact,
remediation, documentation, and a recheck action.

A failed required check blocks new scans; an optional failure disables only that feature. Docker
failure never blocks browsing local records. “Copy diagnostics” and diagnostic exports must redact
secrets, usernames, and sensitive local paths.

## Create-Scan Flow

Each scan has one primary target. The first release supports a Web URL, local source directory,
public Git repository, or IP/domain. Related API URLs, subdomains, credentials, and context may be
attached to that target. Private Git authentication is deferred.

1. Configure an OpenAI, Anthropic, Gemini, OpenAI-compatible, or Ollama endpoint; fetch its model
   list or enter a model identifier manually, then verify connectivity.
2. Choose the target type and enter the primary target.
3. Choose a strict, standard, or custom authorization boundary. Suggestions are derived locally
   from the target and never probe it before authorization.
4. Choose safe mode or full mode, request rate, timeout, budget, and instructions.
5. Validate the target, environment, model connectivity, scope, and credentials.
6. Review the plan and acknowledge authorization before launch.

Safe mode is the default. Full mode may submit forms, write data, or upload files and requires a
second confirmation plus a persistent risk indicator. Authentication may include account/password,
Cookie, Bearer token, custom headers, login steps, and client certificates. Secrets are never
written into run files or displayed in full; “use once” secrets are removed after the task.

Providers include OpenAI, Anthropic, Gemini, OpenAI-compatible endpoints, and Ollama. Official and
compatible services accept a custom API base URL. Users can fetch a bounded model list, test
connectivity, and select a configured model per scan. API keys are write-only browser inputs and
model-discovery responses never include credentials. Existing environment configuration may be
detected for import without revealing the full secret.

## Execution and Live Workspace

The first release executes one scan at a time and queues the rest. Users can still browse records,
reports, and edit queued tasks. The workspace header shows the target, lifecycle phase, elapsed
time, usage, cost, stop controls, and steering input. Tabs include Overview, Agents, Activity,
Tools, Findings, Runtime, and Report.

Progress uses phases, completed milestones, active Agents, current activity, findings, elapsed
time, usage, and cost. Users may send additional instructions or adjust focus within the authorized
scope. Safe stop preserves results; emergency termination is separately confirmed. Pause/resume is
not offered until the engine can restore Agent and sandbox state.

Closing the window during a scan minimizes to the system tray. The tray exposes status, open, and
stop actions. Windows notifications report completion, failure, and critical findings. Exiting
during active work requires explicit confirmation.

## Findings and Reports

Finding workflow is `pending -> confirmed -> accepted risk | fixed | false positive`. Store local
notes and status history. Users can filter by target, severity, state, and date, and correlate the
same issue across scans. Details include evidence, reproduction, affected location, and remediation.

Export complete reports or individual findings as HTML, PDF, Markdown, or JSON in Chinese or
English. Sensitive headers, paths, and tokens can be omitted. Email, cloud sharing, and scan archive
import/export are not part of the first release.

## Local Data and Records

Store configuration, cache, logs, and diagnostics under `%LOCALAPPDATA%\StrixConsole\`; store new
runs under `%LOCALAPPDATA%\StrixConsole\runs\` by default. Users may change the destination for new
scans and add existing `strix_runs/` directories as read-only sources without moving them.

The records UI distinguishes queued, active, completed, interrupted, partial, and malformed data.
Malformed records remain visible with diagnostics. Users can open the containing folder and remove
a source without deleting its files. Run deletion resolves an exact path, requires confirmation,
and moves data to the Windows Recycle Bin by default.

No data leaves the device. Logs rotate locally with a configurable retention period. Users can
clear cache, logs, or all local data through progressively stronger confirmations. Uninstalling
preserves scan records by default.

## Distribution and Updates

The first release is a Windows installer; a portable ZIP is deferred until installation and update
flows stabilize. GitHub Releases for `haodehaode378/strix-for-see` is the stable-only application
update channel. The desktop app, control service, and bundled Strix update as one tested version
after user confirmation. Never update during an active scan, silently install, or automatically
downgrade. A failed update preserves the working version.

The Sandbox image updates independently from
`ghcr.io/haodehaode378/strix-for-see-sandbox:<version>`. Show version, size, progress, disk impact,
and compatibility. Do not replace an image used by an active scan or remove old images without
confirmation. The first installer may be unsigned and must document the possible SmartScreen
warning.

## MVP Acceptance

The MVP includes bilingual setup, environment checks, local secret configuration, scan creation
and queueing, start/stop/terminate, live events, Agent and tool observability, steering, local
records, finding workflow, report export, tray notifications, diagnostics, and confirmed updates.
Multi-user access, cloud features, private Git credentials, scheduling, multiple concurrent scans,
portable distribution, scan archive transfer, and pause/resume remain deferred.
