#!/usr/bin/env python3
"""Detect the primary stack of a repository and extract high-signal facts that
seed an architecture analysis.

Usage:
    python3 detect_stack.py <repo-path>

Prints a JSON report to stdout:
    {"primary": "react"|"angular"|"spring-boot"|"java"|"python"|"unknown",
     "candidates": [...],          strongest first
     "language": "...",
     "build_tool": "...",
     "entrypoints": [...],         likely application entry points (repo-relative)
     "dependencies": [...],        notable libraries/frameworks
     "source_roots": [...],
     "dir_summary": {dir: file_count},
     "markers": [...]}             marker files that were found

Pure, read-only inspection — never modifies the repo. Standard library only, so it
runs in any VM with Python 3 and needs no `pip install`.
"""
import json
import os
import re
import sys
from pathlib import Path

# Directories never worth scanning, and caps so a huge/hostile repo can't make the
# detector read unbounded data or walk forever.
SKIP_DIRS = {"node_modules", ".git", "target", "build", "dist", "__pycache__",
             ".venv", "venv", ".idea", ".gradle", "out", "vendor"}
MAX_READ_BYTES = 5 * 1024 * 1024     # cap per-file reads
MAX_SCAN_FILES = 5000                # cap files visited when hunting entry points


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(MAX_READ_BYTES)
    except Exception:
        return None


def walk_files(root, suffix):
    """Yield files under root with the given suffix, pruning SKIP_DIRS and stopping
    after MAX_SCAN_FILES so a pathological tree can't stall the detector."""
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(suffix):
                yield Path(dirpath) / fn
                seen += 1
                if seen >= MAX_SCAN_FILES:
                    return


def read_json(path):
    txt = read_text(path)
    if txt is None:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def exists(root, rel):
    return (root / rel).exists()


def rel(root, p):
    try:
        return str(Path(p).resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)


# --- dependency extraction -------------------------------------------------

def npm_deps(root):
    pkg = read_json(root / "package.json")
    if not pkg:
        return None
    deps = {}
    deps.update(pkg.get("dependencies") or {})
    deps.update(pkg.get("devDependencies") or {})
    return sorted(deps.keys())


def maven_deps(root):
    s = read_text(root / "pom.xml")
    if not s:
        return None
    found = re.findall(r"<artifactId>([^<]+)</artifactId>", s)
    return sorted(set(found))


def gradle_deps(root):
    s = read_text(root / "build.gradle") or read_text(root / "build.gradle.kts")
    if not s:
        return None
    found = re.findall(r"['\"]([A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+)(?::[^'\"]+)?['\"]", s)
    return sorted(set(found))


def python_deps(root):
    out = []
    reqs = read_text(root / "requirements.txt")
    if reqs:
        for line in reqs.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(re.split(r"[=<>!~\[ ]", line)[0])
    pyproj = read_text(root / "pyproject.toml")
    if pyproj:
        out += re.findall(r"(?m)^\s*[\"']?([A-Za-z0-9_.\-]+)[\"']?\s*[=:]", pyproj)
    out = sorted({d for d in out if d})
    return out or None


# --- entry points ----------------------------------------------------------

def find_files(root, patterns, cap=5):
    hits = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if p.is_file():
                hits.append(rel(root, p))
    # de-dupe, preserve order, cap
    seen, out = set(), []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
        if len(out) >= cap:
            break
    return out


def spring_entrypoints(root):
    hits = []
    for p in walk_files(root, ".java"):
        txt = read_text(p)
        if txt and "@SpringBootApplication" in txt:
            hits.append(rel(root, p))
    return sorted(hits)


def react_angular_entrypoints(root):
    return find_files(root, [
        "src/main.ts", "src/main.tsx", "src/main.js", "src/main.jsx",
        "src/index.ts", "src/index.tsx", "src/index.js", "src/index.jsx",
        "src/App.ts", "src/App.tsx", "src/App.js", "src/App.jsx",
    ], cap=8)


def python_entrypoints(root):
    out = []
    if exists(root, "manage.py"):
        out.append("manage.py")
    for name in ("app.py", "main.py", "run.py", "wsgi.py", "asgi.py"):
        if exists(root, name):
            out.append(name)
    out += find_files(root, ["**/wsgi.py", "**/asgi.py", "**/main.py"], cap=6)
    seen, res = set(), []
    for h in out:
        if h not in seen:
            seen.add(h)
            res.append(h)
    return res[:8]


# --- directory summary -----------------------------------------------------

def dir_summary(root, source_roots, max_depth=3):
    summary = {}
    for sr in source_roots:
        base = root / sr
        if not base.exists():
            continue
        base_depth = len(base.resolve().parts)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                           and not d.startswith(".")]
            dp = Path(dirpath)
            if len(dp.resolve().parts) - base_depth > max_depth:
                dirnames[:] = []
                continue
            n = len([f for f in filenames if not f.startswith(".")])
            if n:
                summary[rel(root, dp)] = n
    return summary


# --- detection -------------------------------------------------------------

def detect(root):
    npm = npm_deps(root)
    npm_set = {d.lower() for d in (npm or [])}
    has_angular = exists(root, "angular.json") or ("@angular/core" in npm_set)
    has_react = (not has_angular) and bool(
        npm_set & {"react", "react-dom", "next"})

    pom = exists(root, "pom.xml")
    gradle = exists(root, "build.gradle") or exists(root, "build.gradle.kts")
    java_deps = maven_deps(root) if pom else (gradle_deps(root) if gradle else None)
    spring = any("spring-boot" in d.lower() for d in (java_deps or []))
    python_proj = any(exists(root, m) for m in
                      ("requirements.txt", "pyproject.toml", "setup.py", "Pipfile"))

    candidates = []
    if spring:
        candidates.append("spring-boot")
    if has_react:
        candidates.append("react")
    if has_angular:
        candidates.append("angular")
    if (pom or gradle) and not spring:
        candidates.append("java")
    if python_proj:
        candidates.append("python")
    primary = candidates[0] if candidates else "unknown"

    markers = []
    for f in ("package.json", "angular.json", "pom.xml", "build.gradle",
              "requirements.txt", "pyproject.toml", "setup.py"):
        if exists(root, f):
            markers.append(f)

    if primary in ("react", "angular"):
        build_tool = ("pnpm" if exists(root, "pnpm-lock.yaml")
                      else "yarn" if exists(root, "yarn.lock") else "npm")
        specifics = {
            "language": "typescript/javascript",
            "build_tool": build_tool,
            "entrypoints": react_angular_entrypoints(root),
            "dependencies": npm or [],
            "source_roots": [d for d in ("src", "app", "public") if exists(root, d)],
        }
    elif primary in ("spring-boot", "java"):
        specifics = {
            "language": "java",
            "build_tool": "maven" if pom else "gradle",
            "entrypoints": (spring_entrypoints(root) if spring
                            else find_files(root, ["**/Main.java"], cap=5)),
            "dependencies": java_deps or [],
            "source_roots": [d for d in ("src/main/java", "src/main/resources",
                                         "src/main/kotlin") if exists(root, d)],
        }
    elif primary == "python":
        top_dirs = sorted(
            d.name for d in root.iterdir()
            if d.is_dir() and not d.name.startswith("."))[:12]
        specifics = {
            "language": "python",
            "build_tool": ("poetry/pep517" if exists(root, "pyproject.toml")
                           else "pipenv" if exists(root, "Pipfile") else "pip"),
            "entrypoints": python_entrypoints(root),
            "dependencies": python_deps(root) or [],
            "source_roots": top_dirs,
        }
    else:
        specifics = {
            "language": "unknown",
            "build_tool": "unknown",
            "entrypoints": [],
            "dependencies": [],
            "source_roots": [d for d in ("src", "lib", "app") if exists(root, d)],
        }

    report = {"primary": primary, "candidates": candidates, "markers": markers}
    report.update(specifics)
    report["dir_summary"] = dir_summary(root, specifics["source_roots"])
    return report


def main(argv):
    if len(argv) < 2:
        print("Usage: python3 detect_stack.py <repo-path>", file=sys.stderr)
        return 2
    root = Path(argv[1]).expanduser().resolve()
    if not root.exists():
        print(f"Path does not exist: {root}", file=sys.stderr)
        return 2
    print(json.dumps(detect(root), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
