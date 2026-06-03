#!/usr/bin/env python3
"""Orchestrator for the Bitbucket project agent-enablement sweep.

Targets **Bitbucket Server / Data Center** (REST API 1.0). Standard library only
(urllib + subprocess), so it runs in any VM with Python 3 and git — no pip install.

It owns the deterministic plumbing (REST, git) and keeps a **resumable state file**
so an all-repos run that crashes can pick up exactly where it left off. The actual
architecture analysis and doc writing is done by the agent between `prepare` and
`finalize`; this script never writes prose.

Configuration via environment variables:
    BITBUCKET_URL      base url, e.g. https://bitbucket.mycorp.com (no trailing /)
    BITBUCKET_TOKEN    HTTP access token (sent as `Authorization: Bearer ...`)
    BITBUCKET_PROJECT  project key to enumerate, e.g. PLATFORM
    BITBUCKET_WORKDIR  where clones + state live (default ./.agent-enablement-work)

Subcommands:
    config                 print resolved config (token redacted) + paths
    init                   fetch repos and create/merge the state file (idempotent)
    status                 print the state: per-repo status + counts
    next                   print the next repo that still needs work (resume point)
    prepare <slug>         clone/fetch, create+checkout feature/agent-enablement
    set-status <slug> <s>  record an intermediate status (e.g. "documented")
    skip <slug> [reason]   mark a repo skipped (empty repo, etc.)
    finalize <slug>        commit the 3 docs and push the branch

Status lifecycle per repo:
    pending -> prepared -> documented -> pushed        (happy path)
                       \-> failed   (recorded with an error; `next` re-offers it)
    pending -> skipped  (empty repo / deliberately excluded)

`next` returns any repo not in {pushed, skipped}, so a crash at any point is safe:
re-running the loop re-offers unfinished repos, and every step is idempotent (branch
reused, docs overwritten, "nothing to commit" handled).
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# Repo slugs flow into filesystem paths and URLs; constrain them to a safe charset to
# prevent path traversal (../) and URL/path manipulation.
SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")

BRANCH = "feature/agent-enablement"
DOC_FILES = ["architecture.md", "AGENT.md", "PROJECT_SUMMARY.md", "SCA.html"]
COMMIT_MSG = (
    "docs: add agent-enablement documentation\n\n"
    "Generated architecture.md, AGENT.md, PROJECT_SUMMARY.md and SCA.html on the\n"
    "feature/agent-enablement branch."
)
TERMINAL = {"pushed", "skipped"}


# --- config & io -----------------------------------------------------------

def env(name, required=True):
    v = os.environ.get(name)
    if required and not v:
        die(f"Missing required environment variable: {name}")
    return v


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def log(*parts):
    print(" ".join(str(p) for p in parts), file=sys.stderr)


def emit(obj):
    print(json.dumps(obj, indent=2))


def require_slug(slug):
    """Reject slugs that could traverse the filesystem or manipulate URL paths."""
    if not slug or not SLUG_RE.match(slug) or slug in (".", ".."):
        die(f"Invalid repository slug: {slug!r} (allowed: letters, digits, . _ -)")
    return slug


def quote_seg(s):
    """URL-encode a single path segment so it can't break out of the path."""
    return urllib.parse.quote(str(s), safe="")


def config():
    base = env("BITBUCKET_URL").rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in ("http", "https"):
        die("BITBUCKET_URL must start with http:// or https://")
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        die("BITBUCKET_URL must not contain embedded credentials; use BITBUCKET_TOKEN.")
    return {
        "base_url": base,
        "token": env("BITBUCKET_TOKEN"),
        "project": env("BITBUCKET_PROJECT"),
    }


def workdir():
    return os.path.abspath(os.environ.get("BITBUCKET_WORKDIR",
                                          "./.agent-enablement-work"))


def state_path():
    return os.path.join(workdir(), "state.json")


def load_state():
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def save_state(state):
    os.makedirs(workdir(), exist_ok=True)
    tmp = state_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, state_path())  # atomic: a crash never corrupts the state file


# --- Bitbucket DC REST 1.0 -------------------------------------------------

def api_get(url, token, params=None, soft=False):
    """GET + parse JSON. On error, die() (fatal) — unless soft=True, in which case
    return None so the caller can treat the failure as "not available" (used for the
    best-effort default-branch lookup, which may 404 on empty repos)."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if soft:
            return None
        if e.code in (401, 403):
            die(f"Authentication/authorization failed (HTTP {e.code}). "
                f"Check BITBUCKET_TOKEN and its permissions.", code=3)
        die(f"Bitbucket request failed (HTTP {e.code}) for {url}")
    except urllib.error.URLError as e:
        if soft:
            return None
        die(f"Could not reach Bitbucket at {url}: {e.reason}")


def clone_url(repo):
    clones = (repo.get("links") or {}).get("clone") or []
    for c in clones:
        if c.get("name") in ("http", "https"):
            return c.get("href")
    return clones[0].get("href") if clones else None


def list_repos(cfg):
    endpoint = (f"{cfg['base_url']}/rest/api/1.0/projects/"
                f"{quote_seg(cfg['project'])}/repos")
    out, start = [], 0
    while True:
        page = api_get(endpoint, cfg["token"], {"limit": 100, "start": start})
        for r in page.get("values", []):
            out.append({"slug": r["slug"], "name": r.get("name", r["slug"]),
                        "clone_url": clone_url(r)})
        if page.get("isLastPage", True):
            break
        start = page.get("nextPageStart", start + 100)
    return out


def default_branch(cfg, slug):
    url = (f"{cfg['base_url']}/rest/api/1.0/projects/{quote_seg(cfg['project'])}"
           f"/repos/{quote_seg(slug)}/branches/default")
    res = api_get(url, cfg["token"], soft=True)
    return res.get("displayId") if res else None


# --- git -------------------------------------------------------------------

def git(cwd, *args, check=False):
    res = subprocess.run(["git", *args], cwd=cwd, text=True,
                         capture_output=True)
    if check and res.returncode != 0:
        die(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res


def repo_dir(slug):
    return os.path.join(workdir(), slug)


def repo_empty(cwd):
    return git(cwd, "rev-parse", "--verify", "HEAD").returncode != 0


def clone_or_fetch(slug, url):
    if not url:
        die(f"No clone URL available for {slug}.")
    d = repo_dir(slug)
    if os.path.isdir(os.path.join(d, ".git")):
        git(d, "fetch", "--all", "--prune")
    else:
        os.makedirs(workdir(), exist_ok=True)
        # `--` stops a clone URL that begins with `-` being treated as a git option
        res = subprocess.run(["git", "clone", "--", url, d], text=True,
                             capture_output=True)
        if res.returncode != 0:
            die(f"git clone failed for {slug}: {res.stderr.strip()}")
    return d


def checkout_branch(cwd, base):
    base = (base or git(cwd, "symbolic-ref", "--short", "HEAD").stdout.strip()
            or "main")
    exists = git(cwd, "rev-parse", "--verify", BRANCH).returncode == 0
    if exists:
        git(cwd, "checkout", BRANCH, check=True)
        return base, False
    git(cwd, "checkout", base)
    git(cwd, "pull", "--ff-only")
    git(cwd, "checkout", "-b", BRANCH, check=True)
    return base, True


def commit_docs(cwd):
    for f in DOC_FILES:
        if os.path.exists(os.path.join(cwd, f)):
            git(cwd, "add", f)
    if not git(cwd, "status", "--porcelain").stdout.strip():
        sha = git(cwd, "rev-parse", "HEAD").stdout.strip()
        return False, sha
    git(cwd, "commit", "-m", COMMIT_MSG, check=True)
    return True, git(cwd, "rev-parse", "HEAD").stdout.strip()


def push_branch(cwd):
    res = git(cwd, "push", "--set-upstream", "origin", BRANCH)
    if res.returncode == 0:
        return True, None
    return False, res.stderr.strip()


# --- state helpers ---------------------------------------------------------

def require_state():
    st = load_state()
    if st is None:
        die("No state file. Run `init` first.")
    return st


def update_repo(st, slug, **fields):
    st["repos"].setdefault(slug, {})
    st["repos"][slug].update(fields)
    save_state(st)


# --- subcommands -----------------------------------------------------------

def cmd_config(_):
    cfg = config()
    tok = cfg["token"]
    emit({"base_url": cfg["base_url"], "project": cfg["project"],
          "token": (tok[:4] + "...redacted") if tok else "(unset)",
          "workdir": workdir(), "state_file": state_path()})


def cmd_init(_):
    cfg = config()
    repos = list_repos(cfg)
    st = load_state() or {"project": cfg["project"], "repos": {}}
    added = 0
    for r in repos:
        if r["slug"] not in st["repos"]:
            st["repos"][r["slug"]] = {"name": r["name"], "clone_url": r["clone_url"],
                                      "status": "pending"}
            added += 1
        else:  # refresh metadata but keep status (resumability)
            st["repos"][r["slug"]].update(
                {"name": r["name"], "clone_url": r["clone_url"]})
    save_state(st)
    log(f"Project {cfg['project']}: {len(repos)} repos "
        f"({added} new, {len(st['repos'])} tracked)")
    cmd_status(_)


def cmd_status(_):
    st = require_state()
    counts = {}
    table = []
    for slug, r in sorted(st["repos"].items()):
        s = r.get("status", "pending")
        counts[s] = counts.get(s, 0) + 1
        table.append({"slug": slug, "status": s,
                      "commit": r.get("commit"), "error": r.get("error")})
    emit({"project": st.get("project"), "counts": counts,
          "total": len(table), "repos": table})


def cmd_next(_):
    st = require_state()
    for slug, r in st["repos"].items():
        if r.get("status") not in TERMINAL:
            out = {"slug": slug, "status": r.get("status", "pending"),
                   "name": r.get("name")}
            if os.path.isdir(repo_dir(slug)):
                out["path"] = repo_dir(slug)
            emit(out)
            return
    emit({"slug": None, "done": True,
          "message": "All repos are pushed or skipped."})


def cmd_prepare(args):
    if not args:
        die("Usage: prepare <slug>")
    slug = require_slug(args[0])
    st = require_state()
    r = st["repos"].get(slug)
    if not r:
        die(f"Unknown repo '{slug}'. Run `init` (or check the slug).")
    cfg = config()
    log(f"Cloning {slug} ...")
    try:
        d = clone_or_fetch(slug, r["clone_url"])
    except SystemExit:
        update_repo(st, slug, status="failed", error="clone failed")
        raise
    if repo_empty(d):
        update_repo(st, slug, status="skipped", error="empty repository", path=d)
        log(f"{slug} is empty — skipped")
        emit({"slug": slug, "path": d, "empty": True})
        return
    base, created = checkout_branch(d, default_branch(cfg, slug))
    update_repo(st, slug, status="prepared", path=d, default_branch=base,
                error=None)
    log(f"{slug} ready on {BRANCH} "
        f"({'new branch' if created else 'existing branch'})")
    emit({"slug": slug, "path": d, "default_branch": base, "empty": False})


def cmd_set_status(args):
    if len(args) < 2:
        die("Usage: set-status <slug> <status>")
    slug = require_slug(args[0])
    st = require_state()
    if slug not in st["repos"]:
        die(f"Unknown repo '{slug}'")
    update_repo(st, slug, status=args[1])
    log(f"{slug} -> {args[1]}")
    emit({"slug": slug, "status": args[1]})


def cmd_skip(args):
    if not args:
        die("Usage: skip <slug> [reason]")
    slug = require_slug(args[0])
    st = require_state()
    if slug not in st["repos"]:
        die(f"Unknown repo '{slug}'")
    reason = " ".join(args[1:]) or "skipped"
    update_repo(st, slug, status="skipped", error=reason)
    emit({"slug": slug, "status": "skipped", "reason": reason})


def cmd_finalize(args):
    if not args:
        die("Usage: finalize <slug>")
    slug = require_slug(args[0])
    st = require_state()
    d = repo_dir(slug)
    if not os.path.isdir(d):
        die(f"Working tree not found for {slug} — run `prepare` first.")
    committed, sha = commit_docs(d)
    # Always push: it's idempotent, and this guarantees a repo that committed cleanly
    # on a previous run but failed to push doesn't get silently marked done. The repo
    # is only TERMINAL (pushed) once the branch actually reaches origin.
    if committed:
        log(f"{slug}: committed docs at {sha} — pushing ...")
    else:
        log(f"{slug}: no doc changes — ensuring branch is pushed ...")
    pushed, err = push_branch(d)
    update_repo(st, slug, status="pushed" if pushed else "failed",
                commit=sha, error=err)
    if not pushed:
        log(f"{slug}: PUSH FAILED: {err}")
    emit({"slug": slug, "committed": committed, "pushed": pushed,
          "commit": sha, "error": err})


COMMANDS = {
    "config": cmd_config, "init": cmd_init, "status": cmd_status,
    "next": cmd_next, "prepare": cmd_prepare, "set-status": cmd_set_status,
    "skip": cmd_skip, "finalize": cmd_finalize,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        log("Usage: python3 enable_project.py "
            "{config|init|status|next|prepare|set-status|skip|finalize} [args]")
        return 2
    COMMANDS[argv[1]](argv[2:])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
