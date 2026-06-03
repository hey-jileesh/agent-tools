#!/usr/bin/env python3
"""Detector specialized for PROJECT_SUMMARY.md generation.

Where architecture-analysis cares about *structure* and agent-md cares about
*commands*, this cares about the *index*: the dependencies (with pinned versions) and
the catalogue of key files an AI assistant needs to navigate the codebase.

Usage:
    python3 scan_inventory.py <repo-path>

Output (JSON):
    {"primary": "...", "language": "...", "build_tool": "...",
     "dependencies": [{"name": ..., "version": ...}, ...],   # with versions
     "key_files": {                                           # categorized inventory
        "entrypoints": [...], "config": [...], "routing": [...],
        "manifests": [...], "tests": [...]},
     "file_counts": {dir: n}}                                 # source dir sizes

The agent annotates each key file with a one-line purpose when writing the summary.
Standard library only — no install needed.
"""
import json
import os
import re
import sys
from pathlib import Path


MAX_READ_BYTES = 5 * 1024 * 1024     # cap manifest reads on hostile/huge repos


def read_text(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read(MAX_READ_BYTES)
    except Exception:
        return None


def read_json(p):
    t = read_text(p)
    try:
        return json.loads(t) if t else None
    except Exception:
        return None


def exists(root, rel_):
    return (root / rel_).exists()


def rel(root, p):
    try:
        return str(Path(p).resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)


def detect_stack(root):
    pkg = read_json(root / "package.json") or {}
    dep_set = {d.lower() for d in
               {**(pkg.get("dependencies") or {}),
                **(pkg.get("devDependencies") or {})}}
    angular = exists(root, "angular.json") or "@angular/core" in dep_set
    react = (not angular) and bool(dep_set & {"react", "react-dom", "next"})
    pom = exists(root, "pom.xml")
    gradle = exists(root, "build.gradle") or exists(root, "build.gradle.kts")
    java_txt = (read_text(root / "pom.xml") or read_text(root / "build.gradle")
                or read_text(root / "build.gradle.kts") or "")
    spring = "spring-boot" in java_txt.lower()
    py = any(exists(root, m) for m in
             ("requirements.txt", "pyproject.toml", "setup.py", "Pipfile"))
    primary = ("spring-boot" if spring else "react" if react else "angular" if angular
               else "java" if (pom or gradle) else "python" if py else "unknown")
    lang = {"react": "typescript/javascript", "angular": "typescript/javascript",
            "spring-boot": "java", "java": "java", "python": "python"}.get(
                primary, "unknown")
    if primary in ("react", "angular"):
        bt = ("pnpm" if exists(root, "pnpm-lock.yaml")
              else "yarn" if exists(root, "yarn.lock") else "npm")
    elif primary in ("spring-boot", "java"):
        bt = "maven" if pom else "gradle"
    elif primary == "python":
        bt = ("poetry/pep517" if exists(root, "pyproject.toml")
              else "pipenv" if exists(root, "Pipfile") else "pip")
    else:
        bt = "unknown"
    return primary, lang, bt, pkg


# --- dependencies WITH versions --------------------------------------------

def deps_with_versions(root, primary, pkg):
    out = []
    if primary in ("react", "angular"):
        for section in ("dependencies", "devDependencies"):
            for name, ver in (pkg.get(section) or {}).items():
                out.append({"name": name, "version": str(ver)})
    elif primary in ("spring-boot", "java"):
        pom = read_text(root / "pom.xml")
        if pom:
            for m in re.finditer(
                    r"<artifactId>([^<]+)</artifactId>\s*(?:<version>([^<]+)</version>)?",
                    pom):
                out.append({"name": m.group(1),
                            "version": m.group(2) or "(managed/inherited)"})
        else:
            g = read_text(root / "build.gradle") or \
                read_text(root / "build.gradle.kts") or ""
            for m in re.finditer(
                    r"['\"]([A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+):([A-Za-z0-9_.\-]+)['\"]",
                    g):
                out.append({"name": m.group(1), "version": m.group(2)})
    elif primary == "python":
        reqs = read_text(root / "requirements.txt")
        if reqs:
            for line in reqs.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"([A-Za-z0-9_.\-]+)\s*([=<>!~].*)?$", line)
                if m:
                    out.append({"name": m.group(1),
                                "version": (m.group(2) or "(unpinned)").strip()})
        pyproj = read_text(root / "pyproject.toml")
        if pyproj and not reqs:
            for m in re.finditer(
                    r"(?m)^\s*[\"']?([A-Za-z0-9_.\-]+)[\"']?\s*[=:]\s*[\"']([^\"']+)[\"']",
                    pyproj):
                out.append({"name": m.group(1), "version": m.group(2)})
    # de-dup by name, keep first
    seen, dedup = set(), []
    for d in out:
        if d["name"] not in seen:
            seen.add(d["name"])
            dedup.append(d)
    return dedup


# --- key-file inventory ----------------------------------------------------

def _matches(root, patterns, cap=25):
    out = []
    for pat in patterns:
        for p in sorted(root.glob(pat)):
            if p.is_file() and "/node_modules/" not in str(p) and \
                    "/.git/" not in str(p) and "/target/" not in str(p) and \
                    "/build/" not in str(p) and "/dist/" not in str(p):
                out.append(rel(root, p))
    seen, res = set(), []
    for h in out:
        if h not in seen:
            seen.add(h)
            res.append(h)
    return res[:cap]


def key_files(root, primary):
    manifests = _matches(root, [
        "package.json", "pom.xml", "build.gradle", "build.gradle.kts",
        "pyproject.toml", "requirements.txt", "setup.py", "go.mod", "angular.json"])
    if primary in ("react", "angular"):
        entry = _matches(root, ["src/main.*", "src/index.*", "src/App.*"])
        routing = _matches(root, ["**/*routing*.*", "**/router*.*", "**/routes.*",
                                  "src/app/app.routes.ts"])
        config = _matches(root, ["tsconfig*.json", "vite.config.*", "next.config.*",
                                 ".env.example", "angular.json"])
    elif primary in ("spring-boot", "java"):
        entry = _matches(root, ["**/*Application.java", "**/Main.java"])
        routing = _matches(root, ["**/*Controller.java", "**/*Resource.java"], cap=30)
        config = _matches(root, ["**/application*.yml", "**/application*.properties",
                                 "**/*Config.java"], cap=20)
    elif primary == "python":
        entry = _matches(root, ["manage.py", "app.py", "main.py", "wsgi.py",
                                "asgi.py", "**/main.py"])
        routing = _matches(root, ["**/urls.py", "**/routes.py", "**/router*.py",
                                  "**/views.py"], cap=20)
        config = _matches(root, ["**/settings.py", "**/config.py", ".env.example",
                                 "**/conftest.py"])
    else:
        entry = _matches(root, ["**/main.*", "**/index.*"])
        routing, config = [], []
    tests = _matches(root, ["**/test_*.py", "**/*_test.py", "**/*.spec.ts",
                            "**/*.test.*", "**/*Test.java", "**/*Tests.java"], cap=20)
    return {"entrypoints": entry, "routing": routing, "config": config,
            "manifests": manifests, "tests": tests}


def file_counts(root):
    counts = {}
    skip = {"node_modules", ".git", "target", "build", "dist", "__pycache__",
            ".venv", "venv", ".idea"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip and
                       not d.startswith(".")]
        depth = len(Path(dirpath).resolve().parts) - len(root.resolve().parts)
        if depth > 3:
            dirnames[:] = []
            continue
        n = len([f for f in filenames if not f.startswith(".")])
        if n and dirpath != str(root):
            counts[rel(root, dirpath)] = n
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:40])


def main(argv):
    if len(argv) < 2:
        print("Usage: python3 scan_inventory.py <repo-path>", file=sys.stderr)
        return 2
    root = Path(argv[1]).expanduser().resolve()
    if not root.exists():
        print(f"Path does not exist: {root}", file=sys.stderr)
        return 2
    primary, lang, bt, pkg = detect_stack(root)
    report = {
        "primary": primary,
        "language": lang,
        "build_tool": bt,
        "dependencies": deps_with_versions(root, primary, pkg),
        "key_files": key_files(root, primary),
        "file_counts": file_counts(root),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
