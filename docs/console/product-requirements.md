# Strix Console Product Requirements

## Product Goal

Build a local-first control and observability console for Strix. It should let an authorized
operator configure a penetration test, launch or stop it, understand what autonomous Agents are
doing, review validated findings, and reopen records stored on disk. The console is independent of
the bundled Viewer and may only reuse its behavioral knowledge and data formats.

The first release targets one local operator. Multi-user tenancy, cloud scheduling, organization
permissions, and true pause/resume are out of scope.

## Core Business Objects

| Object | Responsibility |
| --- | --- |
| `Scan` | Configuration and lifecycle of one penetration-test run |
| `Target` | URL, IP address, local codebase, or remote repository in authorized scope |
| `Agent` | Root or child worker, parent relationship, task, status, and last activity |
| `Event` | Ordered state, message, finding, usage, error, or tool activity |
| `ToolCall` | Tool name, safe input summary, status, duration, and output summary |
| `Finding` | Severity, evidence, PoC, affected location, classification, and remediation |
| `Runtime` | Sandbox backend, image, workspace, mounts, and health |
| `Report` | Persisted Markdown, JSON, SARIF, or PDF artifact |
| `SteeringMessage` | Operator instruction sent to an active scan |

## Information Architecture

- `/dashboard`: active scans, recent high-risk findings, environment health, recent local runs,
  and the primary create-scan action.
- `/scans/new`: guided scan creation.
- `/scans`: filterable scan history.
- `/scans/:id`: live or historical scan workspace.
- `/local-runs`: disk-backed run records discovered from `strix_runs/`.
- `/local-runs/:id`: read-only record details and available artifacts.
- `/findings`: findings aggregated across runs.
- `/settings`: safe defaults and provider/runtime configuration status.
- `/system`: Docker, sandbox image, Strix version, disk, and diagnostic status.

## Create-Scan Flow

1. Select one or more authorized targets.
2. Choose Quick, Standard, Deep, or diff-scoped strategy and enter optional instructions.
3. Select model/runtime settings, budget, timeout, and interactive steering.
4. Validate target syntax, Docker, sandbox image, model connectivity, and required credentials.
5. Review scope and authorization before launch.

Secrets remain in the control service. The browser displays only configured/not-configured status.

## Scan Workspace

The header shows target, lifecycle state, elapsed time, usage, cost, stop action, and steering
entry. The workspace contains:

- **Overview**: current phase, completed milestones, risk summary, and recent activity.
- **Agents**: parent/child topology, task, status, and last activity.
- **Activity**: ordered messages, lifecycle changes, errors, and operator steering.
- **Tools**: tool calls with duration and collapsed safe input/output summaries.
- **Findings**: findings as they are discovered and validated.
- **Runtime**: sandbox, workspace, mount, network, and health information.
- **Report**: final narrative and available downloads.

Autonomous work has no trustworthy percentage. Progress is expressed through phase, milestones,
active Agents, latest activity, findings, elapsed time, usage, and cost.

## Local Records

`/local-runs` indexes `strix_runs/` without changing its contents. It must distinguish active,
completed, interrupted, partial, and malformed records. Each row shows run name, target, mode,
state, timestamps, duration, model, cost, severity counts, artifact availability, and local path.

Users can filter, open details, reuse safe configuration, download artifacts, or request deletion.
Deletion is destructive and requires the exact run to be resolved plus explicit confirmation.
Malformed records remain visible with a parsing diagnostic instead of disappearing.

## MVP Acceptance

The MVP includes environment checks, scan creation, start/stop, scan and local-run lists, live
events, Agent status, tool activity, findings, steering, and report downloads. Cross-run analytics,
multi-user access, remote deployment, scheduling, and pause/resume wait for later decisions.
