#!/usr/bin/env python3
"""Detector specialized for AGENT.md generation.

Where architecture-analysis cares about *structure*, this cares about *operations*:
the real commands an agent needs to build, run, test, and lint a repo. It detects the
stack, then pulls the actual commands the repo defines (package.json scripts, Makefile
targets, Maven/Gradle, pyproject/tox) and flags environment/service requirements.

Usage:
    python3 detect_commands.py <repo-path>

Output (JSON):
    {"primary": "...", "language": "...", "build_tool": "...",
     "package_scripts": {name: command, ...},   # raw npm scripts (repo truth)
     "make_targets": [...],                       # Makefile targets (repo truth)
     "suggested_commands": {                      # best-effort defaults for the stack
        "install": ..., "build": ..., "run": ..., "test": ...,
        "test_single": ..., "lint": ..., "format": ..., "typecheck": ...},
     "entrypoints": [...],
     "env_files": [...],                          # .env.example, application.yml, ...
     "services": [...]}                           # docker-compose, Dockerfile, ...

Prefer `package_scripts` / `make_targets` (what the repo actually declares) over
`suggested_commands` (generic defaults). Standard library only — no install needed.
"""
import json
import os
import re
import sys
from pathlib import Path


SKIP_DIRS = {"node_modules", ".git", "target", "build", "dist", "__pycache__",
             ".venv", "venv", ".idea", ".gradle", "out", "vendor"}
MAX_READ_BYTES = 5 * 1024 * 1024
MAX_SCAN_FILES = 5000


def read_text(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read(MAX_READ_BYTES)
    except Exception:
        return None


def walk_files(root, suffix):
    """Yield files with the given suffix, pruning SKIP_DIRS and capping the count."""
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


def read_json(p):
    t = read_text(p)
    try:
        return json.loads(t) if t else None
    except Exception:
        return None


def exists(root, rel):
    return (root / rel).exists()


def rel(root, p):
    try:
        return str(Path(p).resolve().relative_to(root.resolve()))
    except Exception:
        return str(p)


# --- stack detection (compact core) ----------------------------------------

def detect_stack(root):
    pkg = read_json(root / "package.json") or {}
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    dep_set = {d.lower() for d in deps}
    angular = exists(root, "angular.json") or "@angular/core" in dep_set
    react = (not angular) and bool(dep_set & {"react", "react-dom", "next"})
    pom = exists(root, "pom.xml")
    gradle = exists(root, "build.gradle") or exists(root, "build.gradle.kts")
    java_txt = (read_text(root / "pom.xml") or read_text(root / "build.gradle")
                or read_text(root / "build.gradle.kts") or "")
    spring = "spring-boot" in java_txt.lower()
    py = any(exists(root, m) for m in
             ("requirements.txt", "pyproject.toml", "setup.py", "Pipfile"))
    if spring:
        primary = "spring-boot"
    elif react:
        primary = "react"
    elif angular:
        primary = "angular"
    elif pom or gradle:
        primary = "java"
    elif py:
        primary = "python"
    else:
        primary = "unknown"
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
    return primary, lang, bt, pkg, deps


# --- command extraction (repo truth) ---------------------------------------

def make_targets(root):
    txt = read_text(root / "Makefile")
    if not txt:
        return []
    return sorted({m.group(1) for m in
                   re.finditer(r"(?m)^([a-zA-Z][a-zA-Z0-9_.-]*):", txt)})


def entrypoints(root, primary):
    out = []
    if primary in ("react", "angular"):
        for c in ("src/main.ts", "src/main.tsx", "src/index.tsx", "src/index.ts",
                  "src/main.js", "src/index.js"):
            if exists(root, c):
                out.append(c)
    elif primary in ("spring-boot", "java"):
        for p in walk_files(root, ".java"):
            t = read_text(p)
            if t and "@SpringBootApplication" in t:
                out.append(rel(root, p))
    elif primary == "python":
        for c in ("manage.py", "app.py", "main.py", "run.py", "wsgi.py", "asgi.py"):
            if exists(root, c):
                out.append(c)
    return sorted(set(out))[:8]


def suggested(primary, build_tool, deps):
    dep_set = {d.lower() for d in deps}
    if primary in ("react", "angular"):
        run = ["npm", "run"]
        pm = build_tool if build_tool in ("npm", "yarn", "pnpm") else "npm"
        prefix = {"npm": "npm run", "yarn": "yarn", "pnpm": "pnpm"}[pm]
        install = {"npm": "npm ci", "yarn": "yarn install --frozen-lockfile",
                   "pnpm": "pnpm install --frozen-lockfile"}[pm]
        ng = primary == "angular"
        return {
            "install": install,
            "build": "ng build" if ng else f"{prefix} build",
            "run": "ng serve" if ng else f"{prefix} dev (or {prefix} start)",
            "test": "ng test" if ng else f"{prefix} test",
            "test_single": ("ng test --include='**/foo.spec.ts'" if ng
                            else f"{prefix} test -- <pattern>"),
            "lint": "ng lint" if ng else f"{prefix} lint",
            "format": "npx prettier --write .",
            "typecheck": "npx tsc --noEmit",
        }
    if primary in ("spring-boot", "java"):
        mvn = build_tool == "maven"
        return {
            "install": "mvn -q -DskipTests package" if mvn else "./gradlew assemble",
            "build": "mvn clean package" if mvn else "./gradlew build",
            "run": "mvn spring-boot:run" if mvn else "./gradlew bootRun",
            "test": "mvn test" if mvn else "./gradlew test",
            "test_single": ("mvn -Dtest=ClassName#method test" if mvn
                            else "./gradlew test --tests \"pkg.Class.method\""),
            "lint": "(plugin-dependent: checkstyle/spotless)",
            "format": "(plugin-dependent: spotless:apply)",
            "typecheck": "(compiled by build)",
        }
    if primary == "python":
        poetry = build_tool.startswith("poetry")
        pre = "poetry run " if poetry else ""
        run = ("python manage.py runserver" if "django" in dep_set
               else "uvicorn app.main:app --reload" if "fastapi" in dep_set
               else "flask run" if "flask" in dep_set else "python main.py")
        return {
            "install": "poetry install" if poetry else "pip install -r requirements.txt",
            "build": "(none / packaging via build backend)",
            "run": pre + run,
            "test": pre + "pytest",
            "test_single": pre + "pytest path/to/test.py::TestClass::test_x",
            "lint": pre + ("ruff check ." if "ruff" in dep_set else "flake8"),
            "format": pre + ("ruff format ." if "ruff" in dep_set else "black ."),
            "typecheck": pre + "mypy ." if "mypy" in dep_set else "(no mypy configured)",
        }
    return {k: "(unknown — inspect the repo)" for k in
            ("install", "build", "run", "test", "test_single", "lint",
             "format", "typecheck")}


def env_files(root):
    out = []
    for f in (".env.example", ".env.sample", ".env.template"):
        if exists(root, f):
            out.append(f)
    for p in list(root.glob("**/application*.yml"))[:5] + \
            list(root.glob("**/application*.properties"))[:5] + \
            list(root.glob("**/settings.py"))[:3]:
        out.append(rel(root, p))
    return sorted(set(out))


def services(root):
    out = []
    for f in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml",
              "Dockerfile"):
        if exists(root, f):
            out.append(f)
    return out


def main(argv):
    if len(argv) < 2:
        print("Usage: python3 detect_commands.py <repo-path>", file=sys.stderr)
        return 2
    root = Path(argv[1]).expanduser().resolve()
    if not root.exists():
        print(f"Path does not exist: {root}", file=sys.stderr)
        return 2
    primary, lang, bt, pkg, deps = detect_stack(root)
    report = {
        "primary": primary,
        "language": lang,
        "build_tool": bt,
        "package_scripts": pkg.get("scripts") or {},
        "make_targets": make_targets(root),
        "suggested_commands": suggested(primary, bt, deps),
        "entrypoints": entrypoints(root, primary),
        "env_files": env_files(root),
        "services": services(root),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
