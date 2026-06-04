# agent-tools

A small collection of **agent skills** for working with code repositories. Each skill
is a self-contained folder (a `SKILL.md` plus standard-library-Python scripts, no
install) that a coding agent — Claude Code/Cowork, Devin, Windsurf, GitHub Copilot, or
a human — runs by reading its `SKILL.md` and following it.

## Skills

| Skill | What it does |
|-------|--------------|
| [`architecture-analysis`](architecture-analysis/SKILL.md) | Detects the stack (React / Angular / Spring Boot / Python) and writes **`architecture.md`** with Mermaid C4, component, ER, and sequence diagrams. |
| [`agent-md-generator`](agent-md-generator/SKILL.md) | Writes **`AGENT.md`** — the repo's real build/test/run/lint commands, conventions, and layout. |
| [`project-summary-generator`](project-summary-generator/SKILL.md) | Writes **`PROJECT_SUMMARY.md`** — an annotated key-file index with version-pinned dependencies. |
| [`sca-documentation`](sca-documentation/SKILL.md) | Software composition analysis: runs the dependency-tree command (Maven / npm / pip) and renders a searchable **`SCA.html`** tree that flags version conflicts. |
| [`repo-activity-analysis`](repo-activity-analysis/SKILL.md) | Contribution-health scorecard from pure git history — liveness, velocity, trajectory, bus factor, churn, cadence — as **`REPO_ACTIVITY.html`** + JSON. |
| [`jira-issue-reader`](jira-issue-reader/SKILL.md) | Reads a Jira issue (story/epic/task/bug): type, title, description, acceptance criteria, fix versions, people involved, and change history — and answers *what changed since a date or version*. Jira Cloud + Data Center. |
| [`prd`](prd/SKILL.md) | Interactive requirement analyst — turns a fuzzy idea or feature request into a precise, problem-focused **PRD** using Rich Hickey's "Design in Practice" (Socratic questioning, decision matrices, phased design). |
| [`agent-enablement`](agent-enablement/SKILL.md) | Composite: runs the five per-repo skills above on a single repo (all by default; choose a subset via `AGENT_ENABLEMENT_SKILLS`). |
| [`bitbucket-project-enablement`](bitbucket-project-enablement/SKILL.md) | Walks every repo in a Bitbucket Data Center project and runs `agent-enablement` on each, on a `feature/agent-enablement` branch (resumable). |

## Install

Each agent looks for skills in a different directory. The installer syncs the skills
you choose into the right one:

| Agent | Skills directory |
|-------|------------------|
| Windsurf / GitHub Copilot | `.agent/skills` *(default)* |
| Claude Code / Cowork | `.claude/skills` |
| Devin | `.cognition/skills` |

```bash
# macOS / Linux (run from the agent-tools repo)
./install.sh --target /path/to/your-project                 # all skills -> .agent/skills
./install.sh --target /path/to/your-project --agent claude  # -> .claude/skills
./install.sh --target /path/to/your-project --agent devin --skills "architecture-analysis repo-activity-analysis"
./install.sh --list                                         # list available skills
```

```bat
:: Windows
install.cmd --target C:\path\to\your-project --agent claude
```

- Run with **no flags** for an interactive picker (agent + skills).
- Defaults: **all skills**, **`.agent/skills`**.
- Re-running **syncs** — existing skills are mirrored (updated, with removed files
  pruned), so install also works as update.

The standalone analysis tools also run without installing — just point them at a repo:

```bash
python3 repo-activity-analysis/scripts/analyze_activity.py /path/to/repo
python3 sca-documentation/scripts/generate_sca.py /path/to/repo
```

## Prompts

Paste one of these to a coding agent working in your project to install and verify the
skills. Adjust the repo URL/path if you've cloned it elsewhere.

**Install (all skills, auto-detect agent):**
> Clone `https://github.com/hey-jileesh/agent-tools` into a temp folder, then run its
> `install.sh` to add all skills to this project. Use `--agent claude` for Claude Code,
> `--agent devin` for Devin, or the default (`.agent/skills`) for Windsurf/Copilot.
> Set `--target` to this project's root. Then show me what was installed.

**Install a subset:**
> Using the agent-tools `install.sh`, install only the `architecture-analysis` and
> `repo-activity-analysis` skills into this project, then list the result.

**Validate the install:**
> Validate the agent-tools installation in this project: confirm every folder under the
> skills directory (`.agent/skills`, `.claude/skills`, or `.cognition/skills`) contains a
> `SKILL.md`; compare the installed set against `./install.sh --list`; and smoke-test the
> script-based skills by running
> `repo-activity-analysis/scripts/analyze_activity.py .` and
> `sca-documentation/scripts/generate_sca.py .` against this repo. Report any skill that
> is missing, has no `SKILL.md`, or whose script errors.

**Install then validate, in one go:**
> Install all the agent-tools skills into this project for Claude Code, re-running the
> installer to sync if they already exist, then validate that each installed skill has a
> `SKILL.md` and that the two script-based skills run without error. Summarize pass/fail
> per skill.

## License

[PolyForm Shield 1.0.0](LICENSE) — free to use and modify, including inside your own
commercial software. You may **not** repackage or redistribute it as a product that
competes with it. Source-available, not OSI open-source.
