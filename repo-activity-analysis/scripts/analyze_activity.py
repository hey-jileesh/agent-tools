#!/usr/bin/env python3
"""Repository contribution-health analysis from pure git history.

Answers: *Is this codebase being actively and healthily contributed to — and if not,
when did it slow down or stop?* Works on any clone regardless of host (Bitbucket,
GitHub, GitLab) because it reads only git history.

It computes the metrics in the PRD sections 1-7 (liveness, velocity, trajectory,
people/bus-factor/inflow/retention, substance/churn, cadence, breadth) and rolls them
into the section-9 scorecard, then emits:
  - a JSON summary on stdout (machine-readable), and
  - a self-contained HTML report at <repo>/REPO_ACTIVITY.html (inline SVG histogram,
    scorecard, and per-dimension tables).

Section-8 signals (PR throughput, review participation, issues) live in the host's
API, not in git, so they are intentionally NOT collected here — the report notes this.

Usage:
    python3 analyze_activity.py <repo-path> [--out FILE] [--json-only]

Standard library only. git is invoked with argument lists (never a shell), and every
dynamic value (author names, file paths, branch names — all untrusted) is HTML-escaped
before it reaches the report, so the HTML is safe to open and share.
"""
import argparse
import html
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REC = "\x01"        # record start marker (won't appear in git metadata)
SEP = "\x1f"        # unit separator between fields
MAX_COMMITS = 100000  # safety cap so a giant repo can't exhaust memory


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def git(repo, *args):
    res = subprocess.run(["git", "-C", str(repo), *args],
                         text=True, capture_output=True)
    if res.returncode != 0:
        die(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout


def parse_iso(s):
    # git %aI/%cI are strict ISO-8601 with offset, e.g. 2025-06-01T14:03:11+05:30
    try:
        return datetime.fromisoformat(s.strip())
    except Exception:
        return None


# --- data gathering --------------------------------------------------------

def gather_commits(repo):
    """Return a list of commit dicts from the current branch's history."""
    fmt = REC + SEP.join(["%H", "%an", "%ae", "%aI", "%cI"])
    out = git(repo, "log", "--numstat", "--date=iso-strict", f"--format={fmt}")
    commits = []
    cur = None
    for line in out.split("\n"):
        if line.startswith(REC):
            if cur:
                commits.append(cur)
                if len(commits) >= MAX_COMMITS:
                    cur = None
                    break
            h, an, ae, ai, ci = (line[len(REC):].split(SEP) + ["", "", "", "", ""])[:5]
            cur = {"hash": h, "name": an, "email": ae.lower().strip(),
                   "adate": parse_iso(ai), "cdate": parse_iso(ci),
                   "added": 0, "deleted": 0, "files": [], "size": 0}
        elif line.strip() and cur is not None:
            parts = line.split("\t")
            if len(parts) == 3:
                a, d, path = parts
                ai_n = int(a) if a.isdigit() else 0
                di_n = int(d) if d.isdigit() else 0
                cur["added"] += ai_n
                cur["deleted"] += di_n
                cur["size"] += ai_n + di_n
                cur["files"].append(path)
    if cur:
        commits.append(cur)
    return commits


def gather_branches(repo):
    out = git(repo, "for-each-ref", "--sort=-committerdate",
              "refs/remotes", "refs/heads",
              "--format=%(committerdate:iso-strict)" + SEP + "%(refname:short)")
    branches = []
    for line in out.splitlines():
        if SEP not in line:
            continue
        d, name = line.split(SEP, 1)
        # ignore symbolic refs like origin/HEAD
        if name.endswith("/HEAD"):
            continue
        branches.append({"name": name, "date": parse_iso(d)})
    return branches


# --- metrics ---------------------------------------------------------------

def days_between(a, b):
    return abs((a - b).total_seconds()) / 86400.0


def compute(commits, branches, now):
    commits = [c for c in commits if c["cdate"]]
    commits.sort(key=lambda c: c["cdate"])
    m = {"generated": now.isoformat(), "commit_count": len(commits)}
    if not commits:
        m["empty"] = True
        return m

    cdates = [c["cdate"] for c in commits]
    last = cdates[-1]
    first = cdates[0]

    def since(days):
        cut = now - timedelta(days=days)
        return [c for c in commits if c["cdate"] >= cut]

    # 1. Liveness
    last_any = max([b["date"] for b in branches if b["date"]] + [last])
    m["liveness"] = {
        "days_since_last_commit": round(days_between(now, last), 1),
        "last_commit_iso": last.isoformat(),
        "first_commit_iso": first.isoformat(),
        "age_days": round(days_between(now, first), 1),
        "days_since_last_activity_any_branch": round(days_between(now, last_any), 1),
        "default_branch_behind_some_branch": last_any > last,
    }

    # 2. Velocity
    c30, c90, c365 = len(since(30)), len(since(90)), len(since(365))
    months = Counter(c["cdate"].strftime("%Y-%m") for c in commits)
    active_months = len(months)
    m["velocity"] = {
        "commits_30d": c30, "commits_90d": c90, "commits_365d": c365,
        "active_months": active_months,
        "avg_commits_per_active_month": round(len(commits) / active_months, 2),
    }

    # 3. Trajectory
    # fill the monthly histogram across the whole span so fades are visible
    hist = monthly_series(first, last, months)
    prev90 = [c for c in commits
              if now - timedelta(days=180) <= c["cdate"] < now - timedelta(days=90)]
    m["trajectory"] = {
        "monthly_histogram": hist,
        "rolling_90d_now": c90,
        "rolling_90d_prev": len(prev90),
        "direction": ("rising" if c90 > len(prev90) * 1.1 else
                      "declining" if c90 < len(prev90) * 0.9 else "flat"),
    }

    # 4. People
    first_commit = {}
    for c in commits:
        e = c["email"] or c["name"]
        if e not in first_commit or c["cdate"] < first_commit[e]:
            first_commit[e] = c["cdate"]
    all_authors = {c["email"] or c["name"] for c in commits}
    active180 = since(180)
    active90 = since(90)
    auth180 = Counter(c["email"] or c["name"] for c in active180)
    total180 = sum(auth180.values()) or 1
    top = auth180.most_common(5)
    names = {}
    for c in commits:
        names.setdefault(c["email"] or c["name"], c["name"])
    inflow = lambda d: sum(1 for e, fd in first_commit.items()
                           if fd >= now - timedelta(days=d))
    # retention: of authors active 12-6 months ago, how many active in last 6 months
    win_a = {c["email"] or c["name"] for c in commits
             if now - timedelta(days=365) <= c["cdate"] < now - timedelta(days=180)}
    win_b = {c["email"] or c["name"] for c in active180}
    retained = len(win_a & win_b)
    m["people"] = {
        "total_contributors": len(all_authors),
        "active_90d": len({c["email"] or c["name"] for c in active90}),
        "active_180d": len(win_b),
        "top_recent": [{"name": names.get(e, e),
                        "commits": n, "pct": round(100 * n / total180, 1)}
                       for e, n in top],
        "bus_factor_top1_pct": round(100 * top[0][1] / total180, 1) if top else 0.0,
        "new_contributors_90d": inflow(90),
        "new_contributors_180d": inflow(180),
        "new_contributors_365d": inflow(365),
        "retention_prev_year_pct": (round(100 * retained / len(win_a), 1)
                                    if win_a else None),
    }

    # 5. Substance
    a90 = sum(c["added"] for c in active90)
    d90 = sum(c["deleted"] for c in active90)
    a365 = sum(c["added"] for c in since(365))
    d365 = sum(c["deleted"] for c in since(365))
    sizes = sorted(c["size"] for c in commits)
    buckets = Counter()
    for s in sizes:
        buckets["small (<10)" if s < 10 else "medium (10-100)" if s < 100
                else "large (100-500)" if s < 500 else "huge (500+)"] += 1
    m["substance"] = {
        "churn_90d": {"added": a90, "deleted": d90},
        "churn_365d": {"added": a365, "deleted": d365},
        "median_commit_size": sizes[len(sizes) // 2] if sizes else 0,
        "commit_size_buckets": dict(buckets),
    }

    # 6. Cadence
    gaps = [days_between(cdates[i + 1], cdates[i]) for i in range(len(cdates) - 1)]
    weekday = Counter(c["adate"].weekday() for c in commits if c["adate"])
    hour = Counter(c["adate"].hour for c in commits if c["adate"])
    biz = sum(n for c in commits if c["adate"]
              for n in [1] if c["adate"].weekday() < 5 and 8 <= c["adate"].hour < 18)
    dated = sum(1 for c in commits if c["adate"]) or 1
    m["cadence"] = {
        "avg_gap_days": round(sum(gaps) / len(gaps), 2) if gaps else None,
        "max_gap_days": round(max(gaps), 1) if gaps else None,
        "median_gap_days": round(sorted(gaps)[len(gaps) // 2], 2) if gaps else None,
        "weekday_histogram": {d: weekday.get(d, 0) for d in range(7)},
        "hour_histogram": {h: hour.get(h, 0) for h in range(24)},
        "business_hours_pct": round(100 * biz / dated, 1),
    }

    # 7. Breadth
    hot = Counter()
    for c in active180 if False else since(365):
        for f in c["files"]:
            hot[f] += 1
    stale = sum(1 for b in branches if b["date"]
                and days_between(now, b["date"]) > 365)
    recent_br = sum(1 for b in branches if b["date"]
                    and days_between(now, b["date"]) <= 90)
    m["breadth"] = {
        "hotspots": [{"path": p, "changes": n} for p, n in hot.most_common(10)],
        "branch_count": len(branches),
        "branches_active_90d": recent_br,
        "branches_stale_1y": stale,
    }

    m["scorecard"] = scorecard(m)
    return m


def monthly_series(first, last, months):
    series = []
    y, mo = first.year, first.month
    end_y, end_mo = last.year, last.month
    guard = 0
    while (y, mo) <= (end_y, end_mo) and guard < 1200:
        key = f"{y:04d}-{mo:02d}"
        series.append({"month": key, "count": months.get(key, 0)})
        mo += 1
        if mo > 12:
            mo = 1
            y += 1
        guard += 1
    return series


def scorecard(m):
    v, p = m["velocity"], m["people"]
    rows = []

    def row(dim, value, healthy):
        rows.append({"dimension": dim, "value": value, "healthy": bool(healthy)})

    baseline_90 = v["avg_commits_per_active_month"] * 3
    row("Liveness", f"{m['liveness']['days_since_last_commit']:.0f} days since last commit",
        m["liveness"]["days_since_last_commit"] < 30)
    row("Velocity", f"{v['commits_90d']} commits/90d (baseline ~{baseline_90:.0f})",
        v["commits_90d"] >= baseline_90 * 0.9)
    row("Trajectory", m["trajectory"]["direction"],
        m["trajectory"]["direction"] in ("flat", "rising"))
    row("Team size", f"{p['active_180d']} active (180d)", p["active_180d"] >= 2)
    row("Resilience", f"top author {p['bus_factor_top1_pct']:.0f}% of recent commits",
        p["bus_factor_top1_pct"] < 80)
    row("Growth", f"{p['new_contributors_180d']} new contributors (180d)",
        p["new_contributors_180d"] > 0)
    row("Substance", f"{m['substance']['churn_90d']['added']}+/"
                     f"{m['substance']['churn_90d']['deleted']}- lines (90d)",
        (m["substance"]["churn_90d"]["added"]
         + m["substance"]["churn_90d"]["deleted"]) > 100)
    gap = m["cadence"]["median_gap_days"]
    row("Cadence", f"median gap {gap} days" if gap is not None else "n/a",
        gap is not None and gap <= 14)
    failing = [r["dimension"] for r in rows if not r["healthy"]]
    return {"rows": rows, "failing_dimensions": failing,
            "overall": "healthy" if not failing else "needs attention"}


# --- HTML report (server-rendered; every dynamic value escaped) ------------

def e(x):
    return html.escape(str(x))


def svg_histogram(series):
    if not series:
        return "<p class='empty'>No commits.</p>"
    n = len(series)
    bw, gap, h = 8, 2, 150
    width = max(560, n * (bw + gap) + 40)
    mx = max((s["count"] for s in series), default=1) or 1
    bars, labels, prev_year = [], [], None
    for i, s in enumerate(series):
        x = 30 + i * (bw + gap)
        bh = (s["count"] / mx) * (h - 30)
        y = h - 20 - bh
        bars.append(f'<rect x="{x}" y="{y:.1f}" width="{bw}" height="{bh:.1f}" '
                    f'fill="var(--brand-navy)"><title>{e(s["month"])}: '
                    f'{s["count"]} commits</title></rect>')
        yr = s["month"][:4]
        if yr != prev_year:
            labels.append(f'<text x="{x}" y="{h-4}" class="axis">{e(yr)}</text>')
            prev_year = yr
    return (f'<svg viewBox="0 0 {width} {h}" width="100%" '
            f'preserveAspectRatio="xMinYMin meet" role="img" '
            f'aria-label="Commits per month">'
            f'<text x="0" y="14" class="axis">{mx}</text>'
            f'<line x1="28" y1="{h-20}" x2="{width}" y2="{h-20}" '
            f'stroke="var(--border)"/>'
            + "".join(bars) + "".join(labels) + "</svg>")


def kv_table(pairs):
    rows = "".join(f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in pairs)
    return f"<table class='kv'>{rows}</table>"


def render_html(m, repo_name, branch):
    if m.get("empty"):
        body = "<p class='empty'>This repository has no commits.</p>"
        return HTML_SHELL.replace("__TITLE__", e(f"Repository activity — {repo_name}")) \
                         .replace("__SUB__", e("no commits")) \
                         .replace("__BODY__", body)

    L, V, T = m["liveness"], m["velocity"], m["trajectory"]
    P, S, C, B = m["people"], m["substance"], m["cadence"], m["breadth"]
    sc = m["scorecard"]

    score_rows = "".join(
        f"<tr><td>{e(r['dimension'])}</td><td>{e(r['value'])}</td>"
        f"<td class='{'ok' if r['healthy'] else 'warn'}'>"
        f"{'healthy' if r['healthy'] else 'attention'}</td></tr>"
        for r in sc["rows"])
    overall_cls = "ok" if sc["overall"] == "healthy" else "warn"
    narrative = ("All tracked dimensions look healthy."
                 if not sc["failing_dimensions"]
                 else "Needs attention on: " + ", ".join(sc["failing_dimensions"]))

    top_rows = "".join(
        f"<tr><td>{e(a['name'])}</td><td>{a['commits']}</td>"
        f"<td>{a['pct']}%</td></tr>" for a in P["top_recent"]) or \
        "<tr><td class='empty' colspan='3'>No recent commits</td></tr>"

    hot_rows = "".join(
        f"<tr><td>{e(hp['path'])}</td><td>{hp['changes']}</td></tr>"
        for hp in B["hotspots"]) or \
        "<tr><td class='empty' colspan='2'>No file changes in the last year</td></tr>"

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    wk = C["weekday_histogram"]
    wkmax = max(wk.values()) or 1
    wk_bars = "".join(
        f"<div class='wk'><div class='wkbar' style='height:{(wk[d]/wkmax)*60:.0f}px'>"
        f"</div><span>{days[d]}</span></div>" for d in range(7))

    body = f"""
    <section class="panel score">
      <h2>Health scorecard — <span class="{overall_cls}">{e(sc['overall'])}</span></h2>
      <p class="narrative">{e(narrative)}</p>
      <table class="grid"><thead><tr><th>Dimension</th><th>Signal</th><th>Status</th>
      </tr></thead><tbody>{score_rows}</tbody></table>
    </section>

    <section class="panel">
      <h2>Trajectory — commits per month</h2>
      <div class="chart">{svg_histogram(T['monthly_histogram'])}</div>
      <p class="muted">Direction (rolling 90d vs prior 90d): <b>{e(T['direction'])}</b>
      — {T['rolling_90d_now']} vs {T['rolling_90d_prev']} commits.</p>
    </section>

    <div class="cols">
      <section class="panel">
        <h2>Liveness</h2>
        {kv_table([
            ("Days since last commit", f"{L['days_since_last_commit']:.0f}"),
            ("Last commit", L['last_commit_iso'][:10]),
            ("Last activity (any branch)", f"{L['days_since_last_activity_any_branch']:.0f} days ago"),
            ("Work on a branch ahead of default?", "yes" if L['default_branch_behind_some_branch'] else "no"),
            ("Project age", f"{L['age_days']/365:.1f} years"),
        ])}
      </section>
      <section class="panel">
        <h2>Velocity</h2>
        {kv_table([
            ("Commits — 30 / 90 / 365 days", f"{V['commits_30d']} / {V['commits_90d']} / {V['commits_365d']}"),
            ("Active months", V['active_months']),
            ("Avg commits / active month", V['avg_commits_per_active_month']),
        ])}
      </section>
    </div>

    <div class="cols">
      <section class="panel">
        <h2>People &amp; resilience</h2>
        {kv_table([
            ("Total contributors (all time)", P['total_contributors']),
            ("Active — 90 / 180 days", f"{P['active_90d']} / {P['active_180d']}"),
            ("Bus factor (top author share)", f"{P['bus_factor_top1_pct']:.0f}% of recent commits"),
            ("New contributors — 90 / 180 / 365d", f"{P['new_contributors_90d']} / {P['new_contributors_180d']} / {P['new_contributors_365d']}"),
            ("Retention vs prior year", f"{P['retention_prev_year_pct']}%" if P['retention_prev_year_pct'] is not None else "n/a"),
        ])}
        <h3>Top recent contributors (180d)</h3>
        <table class="grid"><thead><tr><th>Contributor</th><th>Commits</th><th>Share</th></tr></thead>
        <tbody>{top_rows}</tbody></table>
      </section>
      <section class="panel">
        <h2>Substance &amp; cadence</h2>
        {kv_table([
            ("Churn 90d (added / deleted)", f"{S['churn_90d']['added']} / {S['churn_90d']['deleted']}"),
            ("Churn 365d (added / deleted)", f"{S['churn_365d']['added']} / {S['churn_365d']['deleted']}"),
            ("Median commit size (lines)", S['median_commit_size']),
            ("Avg / median / max gap (days)", f"{C['avg_gap_days']} / {C['median_gap_days']} / {C['max_gap_days']}"),
            ("Business-hours commits", f"{C['business_hours_pct']:.0f}%"),
        ])}
        <div class="wkchart">{wk_bars}</div>
      </section>
    </div>

    <div class="cols">
      <section class="panel">
        <h2>Breadth — hotspots (last 12 months)</h2>
        <table class="grid"><thead><tr><th>File / path</th><th>Changes</th></tr></thead>
        <tbody>{hot_rows}</tbody></table>
      </section>
      <section class="panel">
        <h2>Branches</h2>
        {kv_table([
            ("Total branches", B['branch_count']),
            ("Updated in last 90 days", B['branches_active_90d']),
            ("Stale (> 1 year)", B['branches_stale_1y']),
        ])}
      </section>
    </div>

    <section class="panel note">
      <h2>Not collected here (host API)</h2>
      <p class="muted">Pull-request throughput, time-to-merge, review participation,
      and open/closed issues are strong health signals but live in the host's API
      (Bitbucket/GitHub), not in git history. This report covers git-derivable metrics
      only.</p>
    </section>
    """
    sub = (f"branch {branch} · {m['commit_count']} commits · "
           f"generated {m['generated'][:10]} · git history only")
    return HTML_SHELL.replace("__TITLE__", e(f"Repository activity — {repo_name}")) \
                     .replace("__SUB__", e(sub)).replace("__BODY__", body)


HTML_SHELL = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root {
    color-scheme: light;
    --brand-navy:#1A3673; --brand-cyan:#44B8F3; --brand-terra:#E3725F;
    --background:#ffffff; --foreground:#231E33; --card:#ffffff;
    --primary:#1A3673; --muted-foreground:#666666; --border:#D9D9D9;
    --ok:#1A7F4B; --warn:#C0492F;
    --elevation-sm:0px 2px 4px rgba(0,0,0,0.05); --radius:12px; --radius-sm:8px;
    --font-size:16px;
    --text-h3:34px; --text-h4:22px; --text-p:16px; --text-label:13px;
    --fw-regular:400; --fw-medium:500; --fw-semibold:600;
  }
  * { box-sizing: border-box; }
  html { font-size: var(--font-size); }
  body { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
         font-weight: var(--fw-regular); line-height: 1.5; margin: 0;
         background: var(--background); color: var(--foreground); }
  header { background: var(--card); border-bottom: 1px solid var(--border); padding: 1.25rem 1.5rem; }
  h1 { font-size: var(--text-h3); margin: 0 0 .25rem; font-weight: var(--fw-semibold); color: var(--primary); }
  h2 { font-size: var(--text-h4); margin: 0 0 .6rem; font-weight: var(--fw-semibold); color: var(--primary); }
  h3 { font-size: var(--text-p); margin: 1rem 0 .4rem; font-weight: var(--fw-semibold); }
  .sub { color: var(--muted-foreground); font-size: var(--text-label); }
  main { padding: 1.25rem 1.5rem 4rem; max-width: 1100px; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  @media (max-width: 760px) { .cols { grid-template-columns: 1fr; } }
  .panel { background: var(--card); border: 1px solid var(--border);
           border-left: 5px solid var(--primary); border-radius: var(--radius);
           box-shadow: var(--elevation-sm); padding: 1rem 1.1rem; margin-bottom: 1rem; }
  .panel.score { border-left-color: var(--brand-cyan); }
  .panel.note { border-left-color: var(--muted-foreground); }
  table { border-collapse: collapse; width: 100%; font-size: var(--text-label); }
  .kv td { padding: .28rem .4rem; vertical-align: top; }
  .kv td:first-child { color: var(--muted-foreground); width: 55%; }
  .grid th, .grid td { text-align: left; padding: .35rem .5rem; border-bottom: 1px solid var(--border); }
  .grid th { font-weight: var(--fw-semibold); color: var(--muted-foreground);
             text-transform: uppercase; letter-spacing: .03em; font-size: 11px; }
  .ok { color: var(--ok); font-weight: var(--fw-semibold); }
  .warn { color: var(--warn); font-weight: var(--fw-semibold); }
  .narrative { margin: .2rem 0 .8rem; }
  .muted { color: var(--muted-foreground); }
  .empty { color: var(--muted-foreground); }
  .chart { overflow-x: auto; }
  .axis { fill: var(--muted-foreground); font-size: 10px; font-family: inherit; }
  .wkchart { display: flex; gap: .5rem; align-items: flex-end; height: 78px; margin-top: .8rem; }
  .wk { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; flex: 1; }
  .wkbar { width: 70%; background: var(--brand-cyan); border-radius: 3px 3px 0 0; min-height: 2px; }
  .wk span { font-size: 10px; color: var(--muted-foreground); margin-top: 3px; }
</style></head>
<body>
<header><h1>__TITLE__</h1><div class="sub">__SUB__</div></header>
<main>__BODY__</main>
</body></html>
"""


# --- cli -------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(
        description="Analyze a git repo's contribution health (pure git history).")
    ap.add_argument("repo", help="path to the repository (a git clone)")
    ap.add_argument("--out", help="HTML output path (default <repo>/REPO_ACTIVITY.html)")
    ap.add_argument("--json-only", action="store_true",
                    help="print JSON to stdout and skip writing the HTML report")
    args = ap.parse_args(argv[1:])

    repo = Path(args.repo).expanduser().resolve()
    if not repo.exists():
        die(f"Path does not exist: {repo}")
    inside = subprocess.run(["git", "-C", str(repo), "rev-parse",
                             "--is-inside-work-tree"], text=True, capture_output=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        die(f"Not a git repository: {repo}")

    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    commits = gather_commits(repo)
    branches = gather_branches(repo)
    now = datetime.now(timezone.utc)
    m = compute(commits, branches, now)
    m["repo"] = repo.name
    m["branch"] = branch

    if not args.json_only:
        out = Path(args.out) if args.out else (repo / "REPO_ACTIVITY.html")
        out.write_text(render_html(m, repo.name, branch), encoding="utf-8")
        m["report"] = str(out)

    # stdout summary (compact but complete)
    print(json.dumps(m, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
