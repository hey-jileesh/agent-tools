---
name: project-summary-generator
description: "Create or update a PROJECT_SUMMARY.md that gives an AI assistant a fast, dense understanding of a codebase — overview, key file paths with one-line descriptions, dependencies and versions, available commands, and the core architecture/design patterns. Modelled on the clojure-mcp PROJECT_SUMMARY.md style. Actions: detect the stack, enumerate key files with purpose annotations, list pinned dependencies and versions, summarise design patterns and extension points, and write PROJECT_SUMMARY.md at the repo root. Domains: ReactJS, Angular, Java Spring Boot, Python, AI-assistant onboarding, codebase summarisation, progressive disclosure. Triggers: 'create a PROJECT_SUMMARY.md', 'write a project overview', 'summarize this codebase for an AI', 'generate a project summary like clojure-mcp', 'give an assistant a map of this repo'. Use this whenever someone wants a quick-reference summary of a project's structure, files, and dependencies aimed at helping an AI assistant work effectively, even if they just ask for a 'project overview'."
---

# PROJECT_SUMMARY.md Generator

`PROJECT_SUMMARY.md` is a dense, reference-style map of a codebase written *for an AI
assistant* (and useful to humans). Where `architecture.md` explains the design with
diagrams and `AGENT.md` lists operational commands, `PROJECT_SUMMARY.md` is the
annotated index: every important file with a one-line "what it does", the dependency
list with versions, the available tools/commands, and the design patterns — all in
one scannable document.

The canonical example is the
[clojure-mcp PROJECT_SUMMARY.md](https://github.com/bhauman/clojure-mcp/blob/main/PROJECT_SUMMARY.md):
notice how it leads with an overview, then a long "Key File Paths and Descriptions"
section where each path gets a crisp annotation, then pinned dependencies, then
patterns and extension points. Reproduce that *spirit* — adapted to the repo's stack.

## Workflow

### Step 1 — Detect the stack and scan the inventory

Run this tool's inventory scanner. It is specialized for the summary: it returns
**dependencies with pinned versions** and a **categorized key-file inventory**
(entrypoints, routing, config, manifests, tests) plus source-dir file counts:

```bash
python3 scripts/scan_inventory.py <repo-path>
```

That gives you the raw material: the `dependencies` (name + version) for Step 3 and
the `key_files` groups to seed the annotated index in Step 2. (If you can't run it,
read the manifest and walk the tree manually.)

### Step 2 — Build the annotated file index

This is the heart of the document. Walk the source roots and, for each file or
small group of files that matters, write a **one-line description of its purpose**.
Don't list every file — list the ones an assistant needs to know to navigate:
entry points, routing, core domain/services, data access, config, and notable
utilities. Group by area (e.g. "Controllers", "Services", "Components", "Models").

Read enough of each file to describe it accurately. A wrong annotation is worse than
an omitted one.

### Step 3 — Capture dependencies with versions

List the notable dependencies **with their pinned versions** from the manifest
(`package.json`, `pom.xml`/`build.gradle`, `pyproject.toml`/`requirements.txt`),
grouped (core framework, data, testing, build/tooling). Versions matter to an
assistant choosing APIs, so include them.

### Step 4 — Summarise commands, patterns, and extension points

- The key build/test/run commands (you can cross-reference `AGENT.md`).
- The **architecture & design patterns** the code uses, in prose — the layering,
  the conventions, the idioms. This is where you explain *how the code thinks*.
- **Extension points** — where and how a developer adds a new feature of the common
  kinds (a new endpoint, component, model, etc.).

### Step 5 — Write PROJECT_SUMMARY.md

Follow `references/project-summary-template.md`. Write it at the repo root.

If `PROJECT_SUMMARY.md` already exists, **update** it rather than overwrite: refresh
the file index and dependencies (these drift fastest), preserve hand-written
"Recent Changes" notes and any human commentary, and add a dated note about what
this pass refreshed. The clojure-mcp example explicitly keeps a "Recent
Organizational Changes" section — that pattern of recording what changed is worth
continuing.

## Relationship to the other docs

Three docs, three jobs — keep them distinct so they don't become redundant:

- `architecture.md` — the *design*, with diagrams. Why the system is shaped this way.
- `AGENT.md` — the *operations*. How to build, run, and test; conventions to follow.
- `PROJECT_SUMMARY.md` — the *index*. Where everything is and what each piece does.

It's fine for them to cross-reference each other. Don't duplicate the full content.

Run this tool standalone on any repo ("write a PROJECT_SUMMARY for this project"), or
as one step of the `agent-enablement` composite.

## Reference files

- `scripts/scan_inventory.py` — this tool's detector: stack + dependencies-with-
  versions + categorized key-file inventory. Standard-library Python, no install.
- `references/project-summary-template.md` — the section structure, modelled on the
  clojure-mcp PROJECT_SUMMARY.md.
