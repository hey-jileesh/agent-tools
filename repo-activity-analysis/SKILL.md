---
name: repo-activity-analysis
description: "Assess the contribution health of a git repository from its history alone — is it actively and healthily maintained, and if not, when did it slow down or stop? Actions: compute liveness (time since last commit), velocity (commit volume in trailing windows), trajectory (commits-per-month trend), people (contributors, bus factor, new-contributor inflow, retention), substance (code churn, commit sizes), cadence (gaps, day/hour rhythm), and breadth (file hotspots, branches), then roll them into a health scorecard. Renders a JSON summary and a self-contained HTML report with a commits-per-month chart. Works on any clone (Bitbucket, GitHub, GitLab) since it reads only git. Domains: repository health, contribution metrics, project liveness, bus factor, commit activity, maintenance assessment, due diligence, repo triage. Triggers: 'is this repo still active', 'repository activity analysis', 'contribution health', 'when did this project slow down', 'who maintains this and how fragile is it', 'commit activity report', 'is this codebase maintained', 'bus factor'. Use whenever someone wants to know how alive/healthy a repo is or who is contributing, even if they just ask 'is this project still maintained?'."
---

# Repository Activity / Contribution-Health Analysis

Answer one question from git history alone: **is this codebase being actively and
healthily contributed to — and if not, when did it slow down or stop?**

No single number decides this. The insight is in *which* dimension fails: a repo can
be *active but fragile* (busy, but one person writes everything) or *recent but
declining* (a commit last week, but a year-long downward slope). This tool computes
the metrics and combines them into a scorecard that names the failing axis.

Because it reads only git, it works on a clone from any host — Bitbucket, GitHub,
GitLab. Host-only signals (pull requests, reviews, issues) are out of scope here; see
"Beyond git" below.

## How to run it

```bash
python3 scripts/analyze_activity.py <repo-path>
```

It analyzes the checked-out branch's history (plus a glance at all branches for
liveness), prints a full JSON summary to stdout, and writes a self-contained HTML
report to `<repo>/REPO_ACTIVITY.html` (inline SVG commits-per-month chart, the
scorecard, and per-dimension tables). Flags:

- `--out <path>` — choose the HTML output location.
- `--json-only` — print the JSON and skip the HTML (useful when you only need the
  numbers to reason over).

Standard-library Python; no install. It runs read-only `git` commands (no writes to
the repo, no network).

## What it measures (and how to read it)

The metrics map to the PRD sections; `references/interpretation.md` has the full
thresholds and the story each tells. The headlines:

1. **Liveness** — days since last commit (the strongest single signal), and whether a
   side branch is alive while the default branch looks frozen.
2. **Velocity** — commits in 30/90/365-day windows, and an "avg per active month"
   baseline to judge them against.
3. **Trajectory** — the commits-per-month histogram (the project's heartbeat) and the
   rolling-90-day direction (rising / flat / declining). *Slope matters more than
   level.*
4. **People** — total vs. active contributors, **bus factor** (top author's share of
   recent commits), new-contributor inflow, and retention vs. the prior year.
5. **Substance** — code churn (lines added/deleted) and commit-size distribution, so
   steady-but-trivial upkeep is distinguished from real feature work.
6. **Cadence** — average/median/longest gap between commits, and the weekday/hours
   pattern (business-hours vs. nights-and-weekends).
7. **Breadth** — file/directory hotspots and branch count/recency.

## Interpreting the result

Lead with the scorecard's `overall` and `failing_dimensions`, then tell the story:
a healthy project commits recently and regularly, at a steady-or-rising rate, with
work spread across several people (joined by new ones), making substantive changes
across the codebase. State *which* axis fails rather than a single pass/fail.

Two cautions from the PRD's non-goals: this measures contribution *activity*, not code
*quality*; and low activity is not automatically bad — a small, finished, stable
library may legitimately be quiet. Interpretation must consider the project's nature.

## Beyond git — host/API signals (not collected here)

Pull-request throughput and merge rate, time-to-merge, review participation, and
open/closed issue counts are strong health indicators but live in the host's API, not
in git history. The `bitbucket-project-enablement` tool already authenticates to
Bitbucket Data Center — pairing this analysis with that token to pull PR/issue stats
is the natural extension if you need section-8 signals.

## Security

Runs only read-only `git` commands with argument lists (never a shell). Every dynamic
value in the report — author names, file paths, branch names, all untrusted — is
HTML-escaped, so `REPO_ACTIVITY.html` is safe to open and share.

## Reference

- `scripts/analyze_activity.py` — git history gathering, metric computation, scorecard,
  and the HTML renderer. Standard-library Python.
- `references/interpretation.md` — per-metric thresholds and the story each tells.
