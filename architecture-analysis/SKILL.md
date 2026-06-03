---
name: architecture-analysis
description: "Analyse a software repository and produce or update a high-quality architecture.md with Mermaid diagrams. Actions: detect the project's stack, map its module/layer structure, enumerate dependencies and entry points, document data flow and key decisions, and render C4 context, component, and ER/sequence diagrams as Mermaid. Domains: ReactJS, Angular, Java Spring Boot, Python (Flask/Django/FastAPI), C4 model, Architecture Decision Records, Mermaid.js. Triggers: 'analyze the architecture of this project', 'create an architecture.md', 'document how this codebase is structured', 'what's the architecture here', 'add C4 diagrams', 'reverse-engineer the design of this repo'. Use this whenever someone wants the structure or architecture of a codebase documented, even if they don't name the stack — the skill auto-detects React / Angular / Spring Boot / Python and adapts."
---

# Architecture Analysis

Turn an unfamiliar repository into a clear, diagram-backed `architecture.md`. The
skill auto-detects the stack, then follows a stack-specific playbook so the
resulting document reflects how *that kind* of project is actually organised — a
Spring Boot service and a React SPA deserve different lenses.

The goal is a document a new engineer (or coding agent) can read in ten minutes
and understand: what the system does, how it is layered, what it depends on, how
data flows, and which decisions shaped it.

## Workflow

### Step 1 — Detect the stack (scripted, deterministic)

Run the detector against the repo root. It inspects marker files and prints a JSON
report you build the rest of the analysis on:

```bash
python3 scripts/detect_stack.py <repo-path>
```

It reports something like:

```json
{
  "primary": "spring-boot",
  "candidates": ["spring-boot", "java"],
  "language": "java",
  "build-tool": "maven",
  "entrypoints": ["src/main/java/com/acme/Application.java"],
  "dependencies": ["spring-boot-starter-web", "spring-data-jpa", "..."],
  "source-roots": ["src/main/java", "src/main/resources"],
  "dir-summary": { "src/main/java/com/acme/controller": 12, "...": 0 }
}
```

The detector recognises **ReactJS, Angular, Java Spring Boot, and Python**
(Flask/Django/FastAPI), plus a generic fallback. If `primary` is `unknown`, do a
best-effort manual read and say so in the document.

### Step 2 — Read the stack playbook

Open the matching reference and follow its "what to look for" checklist — it tells
you which files reveal the real structure for that stack:

- `references/react.md`
- `references/angular.md`
- `references/spring-boot.md`
- `references/python.md`

Read only the one(s) the detector flagged. Each playbook lists the high-signal
files (routing, DI/config, data layer, entry points) so you spend your reading
budget well instead of crawling every file.

### Step 3 — Investigate the codebase

Using the playbook, read the high-signal files and build a mental model of:

- **Containers / modules** — the major runnable or deployable pieces.
- **Layers** — e.g. controller→service→repository, or components→hooks→services.
- **External dependencies** — datastores, queues, third-party APIs, auth providers.
- **Data model** — the core entities and their relationships.
- **Cross-cutting concerns** — auth, config, logging, error handling.

Use the codebase's own names. Do not invent components that aren't there, and
don't paper over gaps — if something is unclear, note it as an open question.

### Step 4 — Write architecture.md

Follow the template in `references/architecture-md-template.md` exactly — it defines
the section order and shows the Mermaid blocks to include. The document must contain
**at least**:

1. **System context (C4 level 1)** — a Mermaid `graph` showing the system, its
   users, and external systems.
2. **Container / component view (C4 level 2–3)** — a Mermaid `graph` of the internal
   modules and how they call each other.
3. **Data model** — a Mermaid `erDiagram` of the core entities (or a class diagram
   if there's no relational model).
4. **A key runtime flow** — a Mermaid `sequenceDiagram` of one important request
   path end to end.
5. **Architecture decisions** — a short ADR-style list of notable choices and
   trade-offs you can infer from the code.

Every Mermaid block must be syntactically valid (see "Mermaid hygiene" below) and
must reflect what you actually found — diagrams that don't match the code are worse
than no diagrams.

### Step 5 — Update vs. create

If `architecture.md` already exists, treat it as the source of truth for intent and
**update** it: preserve hand-written prose and ADRs the team added, refresh the
diagrams and structure sections, and append new findings rather than clobbering. If
it doesn't exist, create it from the template.

## Mermaid hygiene

These are the mistakes that most often break rendering — avoid them:

- Wrap node labels containing spaces or punctuation in quotes: `A["Auth Service"]`.
- Don't put raw parentheses/semicolons in unquoted labels.
- Use one diagram type per fenced ` ```mermaid ` block.
- For `erDiagram`, relationship syntax is `CUSTOMER ||--o{ ORDER : places`.
- Keep each diagram focused (roughly < 20 nodes); split very large views into
  multiple diagrams rather than one unreadable graph.

Before finishing, re-read each Mermaid block and mentally parse it. If you have a
sandbox with `npx`, you can optionally validate with `@mermaid-js/mermaid-cli`, but
careful authoring is usually enough.

## Output

A single `architecture.md` at the repo root. Run this tool standalone on any repo, or
as one step of the `agent-enablement` composite (which, under
`bitbucket-project-enablement`, writes into the checked-out working tree so it gets
committed on the `feature/agent-enablement` branch).

## Reference files

- `scripts/detect_stack.py` — this tool's structure detector, run first (stack,
  entry points, dependencies, source roots, dir summary). Standard-library Python,
  no install needed.
- `references/react.md`, `references/angular.md`, `references/spring-boot.md`,
  `references/python.md` — per-stack "what to look for" playbooks.
- `references/architecture-md-template.md` — the exact document structure with
  Mermaid examples for each required diagram.
