# Interpreting the contribution-health metrics

Thresholds and the story each metric tells. These are heuristics, not verdicts —
always read them against the project's nature (see "Non-goals" at the end).

## Liveness

**Time since last commit** is the single strongest liveness signal:

| Days since last commit | Reading |
|---|---|
| < 14 | actively worked on |
| 14–90 | maintained, but slowing or between cycles |
| 90–180 | dormant — verify before depending on it |
| 180–365 | likely paused or maintenance-only |
| > 365 | probably abandoned |

**Last activity on any branch vs. the default branch:** a frozen `main` with an
active feature branch tells a different story than a fully frozen repo. The report
flags `default_branch_behind_some_branch` — real work may be happening off to the side
(or a release is being prepared), or a repo that looks dead on `main` is quietly alive.

## Velocity

Raw commit counts (30/90/365 days) are meaningless alone — read them against the
project's own baseline (`avg_commits_per_active_month`) and team size. If the 30-day
rate annualized is far below the 365-day total, momentum is dropping.

## Trajectory (usually the most insightful)

The **commits-per-month histogram** is the heartbeat. Look at the last 6–12 buckets:

- flat or rising → healthy, sustained or growing
- a downward staircase → declining commitment, *even if the last commit is recent*
- a tail fading to near-zero → winding down
- a recent spike → a burst (migration, rewrite, new owner)

The **rolling-90-day direction** smooths out monthly noise (holidays, etc.) so a real
slowdown is distinguishable from a temporary dip.

## People

- **Total vs. active contributors:** a large historical base shrunk to one active
  person is a project that *lost* its community — more concerning than a project that
  was always solo.
- **Bus factor** (top author's share of recent commits): measures fragility, not
  activity. > 80% from one author → high risk (the project stops the day they leave).
  Spread across 3+ people → resilient. This separates "active" from "resilient."
- **New-contributor inflow:** steady inflow signals an open, growing project; zero
  inflow over a long stretch signals contraction — a leading indicator that shows up
  *before* commit volume drops.
- **Retention vs. prior year:** of contributors active a year ago, how many remain.
  High churn even at constant volume means knowledge keeps walking out the door.

## Substance

- **Churn** (lines added/deleted): steady commits with near-zero churn = light
  maintenance, not active development. High deletions alongside additions = refactoring
  or rewrites.
- **Commit-size distribution:** many small commits = incremental, disciplined work; a
  few huge infrequent commits = batch dumps / irregular, less-reviewable process.

## Cadence

- **Average / median / longest gap:** short and regular implies an engaged team and an
  ongoing process. A large average — or a very long maximum — implies stop-start or
  hobby-pace work; the longest gap often marks when the project nearly died.
- **Day-of-week / hours:** weekday business-hours commits suggest a funded product
  people work on as their job; evenings-and-weekends-only suggests a side project —
  relevant to judging how dependable future maintenance is.

## Breadth

- **Hotspots:** activity confined to config/docs while core modules sit untouched can
  mean the product is frozen and only the edges are maintained. Persistent hotspots
  can also flag fragile, churn-prone code.
- **Branches:** several recently-updated branches = parallel work streams; a pile of
  year-stale branches = organizational debt and a sign flow has stopped.

## The scorecard

| Dimension | Healthy signal |
|---|---|
| Liveness | last commit < 1 month |
| Velocity | trailing-90d at/above the per-active-month baseline |
| Trajectory | monthly slope flat or rising |
| Team size | ≥ 2–3 active contributors (180d) |
| Resilience | top author < 80% of recent commits |
| Growth | > 0 new contributors recently |
| Substance | non-trivial, sustained churn |
| Cadence | short, regular gaps (median ≤ ~2 weeks) |

A project can fail on one axis while passing others. Naming **which** axis fails is the
actual insight, e.g. *active but fragile* (bus factor 1) or *recent but declining*
(a commit last week atop a year-long downward slope).

## Non-goals

- This measures contribution *activity*, not code *quality* (no test coverage,
  complexity, or defect analysis).
- Low activity is not automatically bad — a small, finished, stable library may
  legitimately be quiet. Always factor in the project's nature before judging.
