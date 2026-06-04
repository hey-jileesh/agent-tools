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

## License

[Apache-2.0](LICENSE) — free to use, modify, and distribute, including commercially.
