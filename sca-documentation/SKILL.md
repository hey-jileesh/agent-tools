---
name: sca-documentation
description: "Document a repository's software composition (its full dependency tree) as a self-contained, searchable HTML report. Actions: detect the ecosystem, run the native dependency-tree command (Maven / npm / pip), normalize the result into a tree, and render an interactive HTML file where you can search for a library and version, expand/collapse the tree, and see version conflicts. Domains: software composition analysis, SCA, dependency tree, supply-chain, transitive dependencies, vulnerable libraries (e.g. log4j), Java Maven, Node/npm, Python. Triggers: 'software composition analysis', 'generate a dependency tree', 'document dependencies', 'show the dependency tree as HTML', 'can I search whether log4j 1.2 is pulled in', 'SCA report', 'list transitive dependencies', 'find a library in the dependency graph'. Use this whenever someone wants to see, search, or document what libraries (direct and transitive) a project pulls in, especially to hunt for a specific lib/version."
---

# SCA Documentation (dependency-tree report)

Produce a single, self-contained HTML file that shows a repository's **full dependency
tree** (direct + transitive) and lets you **search for a library and version** — the
core question of software composition analysis ("is `log4j 1.2` anywhere in here?").
The report also flags **version conflicts** (the same library resolved at multiple
versions), which is where supply-chain risk and "works on my machine" bugs hide.

Supported ecosystems and the command each uses:

| Ecosystem | Detected by | Dependency-tree command |
|-----------|-------------|-------------------------|
| **Java** | `pom.xml` | `mvn dependency:tree` |
| **Node** | `package.json` | `npm ls --all --json` |
| **Python** | `requirements.txt` / `pyproject.toml` / `Pipfile` | `pipdeptree --json-tree` |

## How to run it

One command does detection, data-gathering, parsing, and rendering:

```bash
python3 scripts/generate_sca.py <repo-path>
```

It auto-detects the ecosystem, runs the right command **inside the repo**, and writes
`<repo>/SCA.html`. Useful flags:

- `--type java|node|python` — force the ecosystem.
- `--out <path>` — choose the output file.
- `--from-file <captured-output>` — skip running the command and parse output you
  already captured (a saved `mvn dependency:tree` log, `npm ls --all --json`, or
  `pipdeptree --json-tree`). Use this in CI, for testing, or when dependencies were
  resolved in a separate step.

The script itself is standard-library Python (no install). The **live** commands need
the ecosystem's toolchain present **and dependencies already resolved**, so for an
accurate, complete tree make sure the project is installed first:

- Java: a working `mvn` and a resolvable build (it will download what it needs).
- Node: run `npm install` (or `ci`) first so `node_modules` reflects the lockfile.
- Python: install into the active environment first (`pip install -r requirements.txt`
  or `poetry install`) and `pip install pipdeptree` — `pipdeptree` reports the
  **installed** environment, not just the requirements file. For Poetry you can also
  capture `poetry show --tree` and pass it via `--from-file` (text), but the JSON path
  is preferred.

## What the report gives you

- **Search box** — type `log4j 1.2` (space-separated tokens are AND-matched across the
  library name and version), matches are highlighted and their branches auto-expanded,
  with a live match count. An "only matches" toggle prunes everything else.
- **Collapsible tree** — expand/collapse any node, or all at once.
- **Version-conflict panel** — every library that appears at more than one version,
  click one to search it instantly.

## When to use

Run it standalone whenever someone wants to see or search a project's dependencies, or
as one step of the `agent-enablement` composite (which produces it alongside
`architecture.md`, `AGENT.md`, and `PROJECT_SUMMARY.md`).

## Security

- **Resolving dependencies runs untrusted code.** `mvn`, `npm install`, and
  installing Python packages execute build scripts / lifecycle hooks (e.g. npm
  `postinstall`, Maven plugins) from the target repo. Treat the repo as untrusted and
  run this in a sandboxed/ephemeral environment, not on a workstation with secrets.
  The HTML renderer (`generate_sca.py`) only reads already-captured output and never
  executes anything.
- **The generated `SCA.html` is safe to open and share.** Dependency names/versions
  are escaped before being embedded, so a hostile coordinate (e.g. a package literally
  named `</script>…`) is rendered as inert text, not executed.

## Notes & limits

- The tree reflects what the command resolves. If deps aren't installed/resolvable,
  the tree will be partial — the report says which command and date it came from.
- This documents *composition*; it does not itself check a vulnerability database.
  Searching for a known-bad coordinate (like `log4j 1.2`) is the manual hook — pairing
  the output with an advisory feed is a natural future extension.
- Gradle isn't wired in yet (Java support targets Maven). `gradle dependencies` output
  can be parsed similarly if needed.

## Reference

- `scripts/generate_sca.py` — detection + command runner + parsers (Maven text, npm
  JSON, pipdeptree JSON) + self-contained HTML renderer. Standard-library Python.
