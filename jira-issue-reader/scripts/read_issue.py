#!/usr/bin/env python3
"""Read a Jira issue (story / epic / task / bug / ...) and summarize it.

Given an issue key, it reports the issue type, title, description, acceptance
criteria, fix versions, the people (reporter / assignee / creator / commenters /
editors / watchers), and the full change history. With --since or --since-version it
reports *what changed* after a date or after a fix version was set — so an agent can
answer "what changed in PROJ-123 since 2025-05-01 / since v2.1?".

Works against:
  - Jira Cloud  (<site>.atlassian.net) — set JIRA_EMAIL + JIRA_TOKEN (Basic auth, API v3)
  - Jira Server / Data Center          — set JIRA_TOKEN only      (Bearer PAT, API v2)

Environment:
  JIRA_URL    base URL, e.g. https://acme.atlassian.net or https://jira.acme.com
  JIRA_TOKEN  API token (Cloud) or Personal Access Token (Data Center)
  JIRA_EMAIL  your account email (Cloud only; its presence selects Basic auth + v3)

Usage:
  python3 read_issue.py PROJ-123
  python3 read_issue.py PROJ-123 --since 2025-05-01
  python3 read_issue.py PROJ-123 --since-version 2.1.0
  python3 read_issue.py PROJ-123 --format md
  python3 read_issue.py --from-file issue.json           # parse a saved issue JSON

Standard library only. The token is sent only in the Authorization header (never in
the URL or logs); the issue key is URL-encoded; TLS verification is on.
"""
import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

MAX_CHANGELOG = 2000
MAX_COMMENTS = 25


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# --- config & auth ---------------------------------------------------------

def get_env(name, required=True):
    import os
    v = os.environ.get(name)
    if required and not v:
        die(f"Missing required environment variable: {name}")
    return v


def config():
    import os
    base = get_env("JIRA_URL").rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in ("http", "https"):
        die("JIRA_URL must start with http:// or https://")
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        die("JIRA_URL must not contain embedded credentials; use JIRA_TOKEN.")
    email = os.environ.get("JIRA_EMAIL")
    token = get_env("JIRA_TOKEN")
    if email:  # Jira Cloud: Basic auth, REST v3
        cred = base64.b64encode(f"{email}:{token}".encode()).decode()
        auth = f"Basic {cred}"
        api_version = 3
    else:       # Jira Data Center / Server: Bearer PAT, REST v2
        auth = f"Bearer {token}"
        api_version = 2
    return {"base": base, "auth": auth, "api_version": api_version}


def api_get(url, auth):
    req = urllib.request.Request(url, headers={"Authorization": auth,
                                               "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        if ex.code in (401, 403):
            die(f"Auth failed (HTTP {ex.code}). Check JIRA_TOKEN / JIRA_EMAIL and "
                f"your permissions on this issue.", code=3)
        if ex.code == 404:
            die("Issue not found (HTTP 404) — check the key and your access.", code=4)
        die(f"Jira request failed (HTTP {ex.code}) for {url}")
    except urllib.error.URLError as ex:
        die(f"Could not reach Jira at {url}: {ex.reason}")


# --- value flattening (ADF / wiki / plain) ---------------------------------

def adf_to_text(node, depth=0):
    """Flatten an Atlassian Document Format node (Cloud v3) to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(n, depth) for n in node)
    t = node.get("type")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    out = adf_to_text(node.get("content"), depth + 1)
    if t in ("paragraph", "heading"):
        return out + "\n"
    if t == "listItem":
        return "  " * max(0, depth - 1) + "- " + out
    if t in ("bulletList", "orderedList"):
        return out
    if t == "codeBlock":
        return out + "\n"
    return out


def flatten(value):
    """Coerce a Jira field value (ADF dict, plain string, list, user) to text."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        if value.get("type") == "doc" or "content" in value:
            return adf_to_text(value).strip() or None
        # user-ish or named object
        return value.get("displayName") or value.get("name") or value.get("value")
    if isinstance(value, list):
        parts = [flatten(v) for v in value]
        return ", ".join(p for p in parts if p) or None
    return str(value)


def user(u):
    if not u:
        return None
    return u.get("displayName") or u.get("name") or u.get("emailAddress") or "Unknown"


# --- acceptance criteria ---------------------------------------------------

AC_RE = re.compile(r"accept\w*\s+criteri", re.I)


def find_acceptance_criteria(fields, names, description_text):
    # 1) a custom field whose display name looks like "Acceptance Criteria"
    for fid, disp in (names or {}).items():
        if disp and AC_RE.search(disp) and fields.get(fid):
            val = flatten(fields.get(fid))
            if val:
                return val, f"field '{disp}'"
    # 2) a heading inside the description
    if description_text:
        lines = description_text.splitlines()
        for i, ln in enumerate(lines):
            if AC_RE.search(ln) and len(ln) < 80:
                rest = "\n".join(lines[i + 1:]).strip()
                if rest:
                    return rest, "description heading"
    return None, None


# --- changelog -------------------------------------------------------------

def parse_dt(s):
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    # normalize +0530 -> +05:30
    m = re.search(r"([+-]\d{2})(\d{2})$", s)
    if m:
        s = s[:m.start()] + m.group(1) + ":" + m.group(2)
    # trim fractional seconds to 6 digits
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def normalize_changelog(raw):
    out = []
    for h in (raw or [])[:MAX_CHANGELOG]:
        out.append({
            "created": h.get("created"),
            "author": user(h.get("author")),
            "changes": [{"field": it.get("field"),
                         "from": it.get("fromString"),
                         "to": it.get("toString")}
                        for it in (h.get("items") or [])],
        })
    return out


def filter_since(changelog, since_dt):
    return [h for h in changelog
            if (d := parse_dt(h["created"])) and d >= since_dt]


def version_set_time(changelog, version):
    """Earliest changelog time where a Fix Version change added `version`."""
    best = None
    for h in changelog:
        for c in h["changes"]:
            f = (c["field"] or "").lower()
            if f in ("fix version", "fixversion", "fix versions") and \
                    c["to"] and version.lower() in c["to"].lower():
                d = parse_dt(h["created"])
                if d and (best is None or d < best):
                    best = d
    return best


# --- people ----------------------------------------------------------------

def collect_people(fields, changelog, comments):
    roles = {}

    def add(name, role):
        if name:
            roles.setdefault(name, set()).add(role)

    add(user(fields.get("reporter")), "reporter")
    add(user(fields.get("assignee")), "assignee")
    add(user(fields.get("creator")), "creator")
    for c in comments:
        add(c["author"], "commenter")
    for h in changelog:
        add(h["author"], "editor")
    return [{"name": n, "roles": sorted(r)} for n, r in sorted(roles.items())]


# --- assemble --------------------------------------------------------------

def build(issue, base):
    f = issue.get("fields", {})
    names = issue.get("names", {})
    rendered = issue.get("renderedFields", {})
    desc = flatten(f.get("description")) or (
        flatten(rendered.get("description")) if rendered else None)
    changelog = normalize_changelog((issue.get("changelog") or {}).get("histories"))

    raw_comments = ((f.get("comment") or {}).get("comments")) or []
    comments = [{"author": user(c.get("author")), "created": c.get("created"),
                 "text": (flatten(c.get("body")) or "")[:500]}
                for c in raw_comments[-MAX_COMMENTS:]]

    ac, ac_src = find_acceptance_criteria(f, names, desc)
    itype = (f.get("issuetype") or {}).get("name")
    parent = f.get("parent") or {}
    data = {
        "key": issue.get("key"),
        "url": f"{base}/browse/{issue.get('key')}" if issue.get("key") else None,
        "type": itype,
        "is_epic": bool(itype and itype.lower() == "epic"),
        "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "priority": (f.get("priority") or {}).get("name"),
        "resolution": (f.get("resolution") or {}).get("name"),
        "reporter": user(f.get("reporter")),
        "assignee": user(f.get("assignee")),
        "creator": user(f.get("creator")),
        "created": f.get("created"),
        "updated": f.get("updated"),
        "fix_versions": [v.get("name") for v in (f.get("fixVersions") or [])],
        "affects_versions": [v.get("name") for v in (f.get("versions") or [])],
        "labels": f.get("labels") or [],
        "components": [c.get("name") for c in (f.get("components") or [])],
        "parent": {"key": parent.get("key"),
                   "summary": (parent.get("fields") or {}).get("summary")}
        if parent else None,
        "description": desc,
        "acceptance_criteria": ac,
        "acceptance_criteria_source": ac_src,
        "comments": {"count": len(raw_comments),
                     "authors": sorted({c["author"] for c in comments if c["author"]}),
                     "recent": comments[-5:]},
        "people_involved": collect_people(f, changelog, comments),
        "change_history": changelog,
    }
    return data


def render_md(d):
    L = []
    L.append(f"# {d['key']} — {d.get('summary','')}  ({d.get('type','?')})")
    if d.get("url"):
        L.append(f"<{d['url']}>")
    L.append("")
    L.append(f"- Status: {d.get('status')}  |  Priority: {d.get('priority')}  |  "
             f"Resolution: {d.get('resolution')}")
    L.append(f"- Reporter: {d.get('reporter')}  |  Assignee: {d.get('assignee')}  |  "
             f"Creator: {d.get('creator')}")
    L.append(f"- Created: {d.get('created')}  |  Updated: {d.get('updated')}")
    if d.get("fix_versions"):
        L.append(f"- Fix versions: {', '.join(d['fix_versions'])}")
    if d.get("parent"):
        L.append(f"- Parent/Epic: {d['parent'].get('key')} "
                 f"{d['parent'].get('summary') or ''}")
    L.append("")
    L.append("## Description\n")
    L.append(d.get("description") or "_(none)_")
    L.append("\n## Acceptance criteria\n")
    L.append((d.get("acceptance_criteria") or "_(none found)_") +
             (f"\n\n_source: {d['acceptance_criteria_source']}_"
              if d.get("acceptance_criteria_source") else ""))
    L.append("\n## People involved\n")
    for p in d["people_involved"]:
        L.append(f"- {p['name']} ({', '.join(p['roles'])})")
    if "changes" in d:
        L.append(f"\n## What changed{d.get('changes_label','')}\n")
        src = d["changes"]
    else:
        L.append("\n## Change history\n")
        src = d["change_history"]
    if not src:
        L.append("_(no changes in range)_")
    for h in src:
        L.append(f"**{h['created']}** — {h['author']}")
        for c in h["changes"]:
            L.append(f"  - {c['field']}: {c['from']!r} → {c['to']!r}")
    return "\n".join(L)


# --- cli -------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(description="Read and summarize a Jira issue.")
    ap.add_argument("key", nargs="?", help="issue key, e.g. PROJ-123")
    ap.add_argument("--since", help="report changes on/after this date (YYYY-MM-DD or ISO)")
    ap.add_argument("--since-version", help="report changes after this fix version was set")
    ap.add_argument("--api-version", type=int, choices=[2, 3],
                    help="override REST API version")
    ap.add_argument("--from-file", help="parse a saved issue JSON instead of fetching")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    args = ap.parse_args(argv[1:])

    if args.from_file:
        with open(args.from_file, encoding="utf-8") as fh:
            issue = json.load(fh)
        base = "https://jira.example.com"
    else:
        if not args.key:
            die("Provide an issue key (or use --from-file).")
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]+-\d+$", args.key):
            die(f"Invalid issue key: {args.key!r} (expected like PROJ-123).")
        cfg = config()
        v = args.api_version or cfg["api_version"]
        key = urllib.parse.quote(args.key, safe="")
        url = (f"{cfg['base']}/rest/api/{v}/issue/{key}"
               "?expand=changelog,names,renderedFields")
        issue = api_get(url, cfg["auth"])
        base = cfg["base"]

    data = build(issue, base)

    # what-changed queries
    if args.since or args.since_version:
        cl = data["change_history"]
        cutoff = None
        label = ""
        if args.since_version:
            cutoff = version_set_time(cl, args.since_version)
            if cutoff is None:
                data["changes"] = []
                data["changes_label"] = (f" since version {args.since_version} "
                                         "(version change not found in history)")
                label = data["changes_label"]
            else:
                label = f" since version {args.since_version} was set ({cutoff.date()})"
        if args.since:
            d = parse_dt(args.since) or parse_dt(args.since + "T00:00:00+00:00")
            if d is None:
                die(f"Could not parse --since date: {args.since}")
            cutoff = d if cutoff is None else max(cutoff, d)
            label = f" since {d.date()}"
        if cutoff is not None:
            data["changes"] = filter_since(cl, cutoff)
            data["changes_label"] = label
        data["changes_query"] = {"since": args.since,
                                 "since_version": args.since_version,
                                 "cutoff": cutoff.isoformat() if cutoff else None}

    if args.format == "md":
        print(render_md(data))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
