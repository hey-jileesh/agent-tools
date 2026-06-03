---
name: bitbucket-project-enablement
description: "Drive an end-to-end 'agent enablement' pass across every repository in a Bitbucket Server / Data Center project. Actions: list all repos in a project, clone each one, create and checkout the feature/agent-enablement branch, orchestrate architecture analysis and doc generation, commit the generated docs, and push the branch. Domains: Bitbucket Data Center REST API 1.0, git automation, multi-repo batch workflows, ReactJS / Angular / Java Spring Boot / Python codebases. Triggers: 'enable agents across our Bitbucket project', 'run architecture analysis on every repo', 'drop into a bitbucket project and document all repos', 'bootstrap agent.md / architecture.md / PROJECT_SUMMARY.md for all repositories', 'create the feature/agent-enablement branch everywhere'. Use this whenever the user wants to iterate over the repositories of a Bitbucket project and bootstrap agent-enablement documentation, even if they only mention 'all our repos' without naming the API."
---

# Bitbucket Project Enablement

This is the **higher-level orchestrator**. It walks every repository in a single
Bitbucket Server / Data Center *project* and, for each one, produces a consistent set
of agent-enablement documents on a dedicated branch. This file is its complete
runbook — follow it top to bottom (it works for Devin, Cursor, Claude Code, OpenHands,
a CI job, or a human).

It depends on two things:

- **its own Python helper** (`scripts/enable_project.py`) for the deterministic
  mechanics — talking to Bitbucket, cloning, branching, committing, pushing, and
  **tracking per-repo progress so a crashed run can resume**; and
- the **`agent-enablement`** composite tool (`../agent-enablement/SKILL.md`) for the
  *thinking* work — it makes a single checked-out repo agent-ready by producing
  `architecture.md`, `AGENT.md`, and `PROJECT_SUMMARY.md`.

So the layering is: this orchestrator → `agent-enablement` (per repo) → the three
leaf tools (`architecture-analysis`, `agent-md-generator`, `project-summary-generator`).
Keeping the git/REST mechanics in a script and the judgement in the lower tools is
deliberate: plumbing behaves identically every run, while the documentation benefits
from your reasoning about each specific codebase.

## Per-repository outcome

For every repo in the project, after a successful run you should have:

1. A local clone under the work directory.
2. A branch `feature/agent-enablement` checked out.
3. Three generated/updated files at the repo root: `architecture.md`, `AGENT.md`,
   `PROJECT_SUMMARY.md` (with Mermaid diagrams in `architecture.md`).
4. A single commit containing those files.
5. The branch pushed to `origin` (no pull request is opened — that stays a human
   decision).

## Prerequisites

The Python script reads configuration from environment variables so nothing
sensitive is hard-coded:

| Variable | Meaning | Example |
|----------|---------|---------|
| `BITBUCKET_URL` | Base URL of the Bitbucket DC instance (no trailing slash) | `https://bitbucket.mycorp.com` |
| `BITBUCKET_TOKEN` | HTTP access token (sent as `Authorization: Bearer …`) | `NjE2…` |
| `BITBUCKET_PROJECT` | Project key to enumerate | `PLATFORM` |
| `BITBUCKET_WORKDIR` | Where clones + the state file live (optional, defaults to `./.agent-enablement-work`) | `/tmp/enablement` |

`python3` (3.8+) and `git` must be on `PATH`. The script uses **only the Python
standard library**, so no `pip install` is required — it runs in any coding-agent VM
as-is.

## Workflow

Run the steps below in order. All commands are run from the suite root (the folder
that contains `scripts/`). The script prints machine-readable JSON to stdout and
human-readable progress to stderr, so you can both parse results and show progress.

### Step 1 — Confirm scope

```bash
python3 scripts/enable_project.py config
```

Prints the base URL, project key, work directory, and state-file path (token
redacted). If the project key or URL looks wrong, stop and confirm before continuing.

### Step 2 — Initialise the work list + resume state

```bash
python3 scripts/enable_project.py init
```

Fetches every repo in the project (pagination handled transparently via
`isLastPage` / `nextPageStart`) and writes a **state file** at
`$BITBUCKET_WORKDIR/state.json`, one entry per repo with `status: pending`. It is
**idempotent**: re-running keeps existing statuses and only adds new repos, so it is
also how you resume after a crash. It then prints a status summary. Confirm the count
looks right before sweeping.

### Step 3 — Loop until done

Repeat 3a–3d until `next` reports `"done": true`.

**3a. Pick the next repo** (skips anything already `pushed`/`skipped`, so interrupted
work resumes automatically):

```bash
python3 scripts/enable_project.py next        # -> {"slug": "...", ...} or {"done": true}
```

**3b. Clone + branch:**

```bash
python3 scripts/enable_project.py prepare <slug>
```

Clones (or fetches), creates+checks out `feature/agent-enablement` from the default
branch, records `status: prepared`, and prints the working-tree `path`. Idempotent:
an existing branch is reused. Empty repos are auto-marked `skipped` (`"empty": true`)
— loop back to 3a.

**3c. Make the repo agent-ready (your work):** run the **`agent-enablement`** composite
on the repo's `path` — **read and follow `../agent-enablement/SKILL.md`**. It produces
all three docs (`architecture.md`, `AGENT.md`, `PROJECT_SUMMARY.md`) at the repo root,
in dependency order, by delegating to the leaf tools. (These are instructions to
follow, not auto-loading skills.)

Optionally checkpoint with `python3 scripts/enable_project.py set-status <slug> documented`.

**3d. Commit + push:**

```bash
python3 scripts/enable_project.py finalize <slug>
```

Stages the three docs, commits them, pushes `feature/agent-enablement` to `origin`,
and records `status: pushed` (or `failed` with the error). Reports `committed: false`
if docs were unchanged (still marked done). Loop back to 3a.

### Step 4 — Report

```bash
python3 scripts/enable_project.py status
```

Summarise: total repos, how many `pushed`, `skipped` (with reasons), and `failed`
(with errors). Offer a table of repo → status → commit. Remind the reviewer the
branch to review everywhere is `feature/agent-enablement` (no PRs were opened).

## Resumability

The state file is the resume mechanism. Never delete it mid-sweep. If the run dies,
re-run `init` (safe/idempotent) and continue the loop — finished repos are remembered
and skipped, and every step is idempotent (branch reused, docs overwritten, "nothing
to commit" handled, state written atomically). To pilot, just stop the loop after one
or two repos; resume later from the same state.

## Error handling expectations

- **Auth failures (401/403):** the script stops with a clear message — fix
  `BITBUCKET_TOKEN`/permissions. Never retry blindly.
- **Empty repositories:** auto-marked `skipped`.
- **Unrecognised stack:** if the stack comes back `"unknown"`, `agent-enablement` still produces
  best-effort docs and flag it; mark the repo done.
- **Push rejected / blocking repo:** recorded as `failed` (or `skip <slug> "reason"`);
  continue the sweep — one bad repo must not abort the rest.

## Reference

- `scripts/enable_project.py` — orchestrator CLI: `config`, `init`, `status`, `next`,
  `prepare`, `set-status`, `skip`, `finalize`. Bitbucket DC REST 1.0 client + git +
  resumable state, standard-library Python only.
- `../agent-enablement/SKILL.md` — the composite this orchestrator runs per repo
  (which in turn calls the three leaf tools and their detectors).
- `references/bitbucket-dc-api.md` — the exact REST endpoints and response shapes used,
  so the client can be adjusted if your Bitbucket version differs.
