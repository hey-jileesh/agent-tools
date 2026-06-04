---
name: agent-enablement
description: "Make a single repository 'agent-ready' in one pass by running the per-repo skills on it. Composite tool: by default runs all five — architecture-analysis, agent-md-generator, project-summary-generator, sca-documentation, and repo-activity-analysis — on one checked-out repo to produce architecture.md, AGENT.md, PROJECT_SUMMARY.md, SCA.html, and REPO_ACTIVITY.html. A subset can be selected. Actions: detect/analyze the repo once and create or update the chosen enablement artifacts at the repo root. Domains: ReactJS, Angular, Java Spring Boot, Python, codebase onboarding, agent readiness, dependency analysis, repo health. Triggers: 'make this repo agent-ready', 'agent-enable this project', 'generate the agent docs for this codebase', 'onboard an agent to this repository', 'run all the repo skills on this project'. Use whenever someone wants the full (or a chosen subset of the) agent-enablement artifacts for one repo — for a whole Bitbucket project use bitbucket-project-enablement, which calls this per repo."
---

# Agent Enablement (single repo)

This is a **composite tool**. It makes one already-checked-out repository agent-ready
by running the per-repo skills on it and delegating to each leaf tool. It does not
touch git or Bitbucket — give it a path to a working tree and it fills in the
artifacts. (To do this across every repo in a Bitbucket project, use
`bitbucket-project-enablement`, which clones/branches each repo and calls this tool.)

## The five skills it runs (all by default)

| Skill | Output | Run via |
|-------|--------|---------|
| `architecture-analysis` | `architecture.md` (Mermaid C4/component/ER/sequence) | `../architecture-analysis/SKILL.md` |
| `agent-md-generator` | `AGENT.md` (build/test/run commands, conventions) | `../agent-md-generator/SKILL.md` |
| `project-summary-generator` | `PROJECT_SUMMARY.md` (annotated index, pinned deps) | `../project-summary-generator/SKILL.md` |
| `sca-documentation` | `SCA.html` (searchable dependency tree + conflicts) | `../sca-documentation/SKILL.md` |
| `repo-activity-analysis` | `REPO_ACTIVITY.html` (contribution-health scorecard) | `../repo-activity-analysis/SKILL.md` |

## Inputs

- `<repo-path>` — path to the checked-out repository.
- **Skill selection (optional)** — by default **run all five**. To run a subset,
  either:
  - the caller names the skills to run (e.g. "agent-enable this repo with just
    architecture-analysis and sca-documentation"), or
  - set `AGENT_ENABLEMENT_SKILLS` to a space/comma-separated list of skill names from
    the table above (unset or empty = all). This makes selection machine-driveable
    from CI or the Bitbucket sweep.

  Run exactly the selected skills and skip the rest.

`python3` (3.8+) and `git` should be available; the leaf tools' scripts are
standard-library Python (no install).

## Workflow

Determine the skill set first: if `AGENT_ENABLEMENT_SKILLS` is set (or the caller
named a subset), use that; otherwise use all five. Then run the selected skills **in
the order below**, writing each output into `<repo-path>`. For each, **read and
follow** the referenced leaf tool's `SKILL.md` (these are instructions to follow, not
auto-loading skills):

1. **`architecture-analysis` → `architecture.md`** — detects the stack and maps
   structure, then writes the doc with Mermaid diagrams.
2. **`agent-md-generator` → `AGENT.md`** — pulls the repo's real build/test/run/lint
   commands, then writes the doc.
3. **`project-summary-generator` → `PROJECT_SUMMARY.md`** — gathers dependencies (with
   versions) and the key-file inventory, then writes the index.
4. **`sca-documentation` → `SCA.html`** — runs the dependency-tree command
   (Maven / npm / pip) and renders the searchable tree. Skip if the repo has no
   resolvable dependency manifest.
5. **`repo-activity-analysis` → `REPO_ACTIVITY.html`** — computes the contribution-
   health scorecard from git history.

Order matters only among the three markdown docs (1→3), which build on the analysis
earlier ones surface; `SCA.html` and `REPO_ACTIVITY.html` are independent and may run
in any order. The markdown docs **create or update** their file (human prose and notes
preserved, generated sections refreshed); the two HTML reports are regenerated each
run (snapshots).

If the stack comes back `unknown`, still produce best-effort docs from a manual read
and flag the uncertainty.

## Why a separate composite

- You can run the **full set (or a chosen subset) on a single repo** without any
  Bitbucket machinery.
- The higher-level `bitbucket-project-enablement` orchestrator stays thin — it handles
  walking the project and git, and calls this tool per repo (it commits whichever
  artifacts were produced, so subset selection flows through automatically).
- It is the **extension point**: to add a new per-repo skill, add it as a leaf tool,
  add a row to the table above and a step to the workflow — every caller picks it up.
  `sca-documentation` and `repo-activity-analysis` were both added this way.

## Reference

- The five leaf tools listed in the table above.
- `../bitbucket-project-enablement/SKILL.md` — runs this across every repo in a
  Bitbucket project.
