---
name: agent-enablement
description: "Make a single repository 'agent-ready' by generating its full set of agent-enablement documents in one pass. Composite tool: runs architecture-analysis, agent-md-generator, and project-summary-generator on one checked-out repo to produce architecture.md, AGENT.md, and PROJECT_SUMMARY.md. Actions: detect the stack once, then create/update all three docs at the repo root in dependency order. Domains: ReactJS, Angular, Java Spring Boot, Python, codebase onboarding, agent readiness. Triggers: 'make this repo agent-ready', 'agent-enable this project', 'generate all the agent docs for this codebase', 'create architecture.md, AGENT.md and PROJECT_SUMMARY.md for this repo', 'onboard an agent to this repository'. Use this whenever someone wants the complete agent-enablement doc set for one repo (not a whole Bitbucket project — for that, use bitbucket-project-enablement, which calls this per repo)."
---

# Agent Enablement (single repo)

This is a **composite tool**. It makes one already-checked-out repository agent-ready
by producing its complete set of enablement documents, by delegating to the leaf
tools. It does not touch git or Bitbucket — give it a path to a working tree and it
fills in the docs. (To do this across every repo in a Bitbucket project, use
`bitbucket-project-enablement`, which clones/branches each repo and calls this tool.)

## What it produces

At the repo root:

- `architecture.md` — design overview with Mermaid C4 / component / ER / sequence diagrams
- `AGENT.md` — build/test/run commands, conventions, project layout
- `PROJECT_SUMMARY.md` — annotated file index, dependencies, patterns (clojure-mcp style)
- `SCA.html` — searchable software-composition (dependency-tree) report

## Inputs

- `<repo-path>` — path to the checked-out repository to document.

`python3` (3.8+) and `git` should be available; the leaf tools' detectors are
standard-library Python (no install).

## Workflow

Generate the documents **in this order** — the markdown docs build on the analysis the
earlier ones surface. For each, **read and follow** the referenced leaf tool's
`SKILL.md` (these are instructions to follow, not auto-loading skills), writing its
output into `<repo-path>`:

1. **`architecture.md`** — read and follow `../architecture-analysis/SKILL.md`.
   It runs `architecture-analysis/scripts/detect_stack.py <repo-path>` to detect the
   stack (ReactJS / Angular / Java Spring Boot / Python) and map structure, then
   writes `architecture.md` from its template with Mermaid diagrams.
2. **`AGENT.md`** — read and follow `../agent-md-generator/SKILL.md`.
   It runs `agent-md-generator/scripts/detect_commands.py <repo-path>` to pull the
   repo's real build/test/run/lint commands, then writes `AGENT.md`.
3. **`PROJECT_SUMMARY.md`** — read and follow `../project-summary-generator/SKILL.md`.
   It runs `project-summary-generator/scripts/scan_inventory.py <repo-path>` for
   dependencies-with-versions and the key-file inventory, then writes
   `PROJECT_SUMMARY.md`.
4. **`SCA.html`** — read and follow `../sca-documentation/SKILL.md`.
   It runs `sca-documentation/scripts/generate_sca.py <repo-path>`, which runs the
   ecosystem's dependency-tree command (Maven / npm / pip) and renders a searchable
   HTML tree. Skip this only if the repo has no resolvable dependency manifest.

The three markdown docs **create or update** their file: if the doc already exists,
the human prose and notes are preserved and the generated sections refreshed. `SCA.html`
is regenerated each run (it's a snapshot of the resolved dependency tree).

If the stack comes back `unknown`, still produce best-effort docs from a manual read
and flag the uncertainty in each document.

## Why a separate composite

Keeping "enable one repo" as its own tool means:

- You can run the **full doc set on a single repo** without any Bitbucket machinery.
- The higher-level `bitbucket-project-enablement` orchestrator stays thin — it only
  handles walking the project and git, and calls this tool per repo.
- It is the **extension point**: to add a new enablement document, add it as a leaf
  tool and reference it here in one place; every caller (including the Bitbucket sweep)
  picks it up automatically. `sca-documentation` (the `SCA.html` step) was added
  exactly this way — a leaf tool plus one line here.

## Reference

- `../architecture-analysis/SKILL.md` — produces `architecture.md`.
- `../agent-md-generator/SKILL.md` — produces `AGENT.md`.
- `../project-summary-generator/SKILL.md` — produces `PROJECT_SUMMARY.md`.
- `../sca-documentation/SKILL.md` — produces `SCA.html`.
- `../bitbucket-project-enablement/SKILL.md` — the higher-level tool that runs this
  across every repo in a Bitbucket project.
