---
name: agent-md-generator
description: "Generate an AGENT.md file that orients a coding agent (or a new engineer) to a repository — the build/test/run commands, conventions, project layout, and gotchas it needs to be productive immediately. Actions: detect the stack, extract real build/test/lint/run commands, document directory layout and naming conventions, list environment/config requirements, and write a concise AGENT.md at the repo root. Domains: ReactJS, Angular, Java Spring Boot, Python, agent onboarding, AGENTS.md / AGENT.md convention, developer experience. Triggers: 'create an agent.md', 'add an AGENTS.md', 'write agent instructions for this repo', 'document the build and test commands for an agent', 'bootstrap onboarding docs for a coding agent'. Use this whenever someone wants a machine-and-human onboarding file describing how to work in a codebase, even if they just say 'help an agent understand this repo'."
---

# AGENT.md Generator

`AGENT.md` is the file a coding agent reads first when it lands in a repository. It
answers the practical questions an agent needs before touching anything: *How do I
build it? How do I run the tests? Where does code live? What conventions must I
follow? What will bite me?*

Keep it **operational and specific**. An AGENT.md full of generic advice ("write
clean code") is useless; one with the exact `mvn`/`npm`/`pytest` invocations and the
real directory map is gold. Favour copy-pasteable commands over prose.

## Workflow

### Step 1 — Detect the stack and the repo's real commands

Run this tool's command detector. Beyond identifying the stack, it extracts the
commands the repo *actually declares* (npm `scripts`, Makefile targets) plus
best-effort defaults, entry points, env files, and services:

```bash
python3 scripts/detect_commands.py <repo-path>
```

It prints `package_scripts` and `make_targets` (repo truth) alongside
`suggested_commands` (generic per-stack defaults), plus `entrypoints`, `env_files`,
and `services`. (If you can't run it, inspect the manifest directly — `package.json`
`scripts`, `pom.xml`/`build.gradle`, `pyproject.toml`, a `Makefile`.)

Always prefer `package_scripts` / `make_targets` over `suggested_commands` — a repo's
own `npm run test:ci` beats a generic `npm test`.

### Step 2 — Pull the commands that matter

Find and record the actual commands for:

- **Install / bootstrap** dependencies
- **Build**
- **Run** locally (and how to point it at config/env)
- **Test** (and how to run a single test — agents need this constantly)
- **Lint / format / typecheck**

Use `references/commands-by-stack.md` as a cheat-sheet of the *usual* commands per
stack, but always prefer what the repo defines (e.g. a custom `npm run test:ci` or a
Makefile target). If a command is only inferred, mark it as such.

### Step 3 — Map the layout and conventions

From the source roots and a quick read of the tree, capture:

- The directory map (where controllers/components/models/tests live).
- Naming and structural conventions the code clearly follows.
- Config/env requirements (env vars, `.env.example`, `application.yml` profiles).
- Any obvious gotchas (codegen steps, required services like a DB, generated files
  not to edit by hand).

### Step 4 — Write AGENT.md

Follow `references/agent-md-template.md`. Keep it tight — aim for something an agent
can absorb in one read. Write it at the repo root as `AGENT.md`.

If an `AGENT.md` (or `AGENTS.md`, `CLAUDE.md`) already exists, **update** it: keep
human-written rules and team conventions, refresh the commands and layout, and don't
delete project-specific guidance you can't verify is obsolete.

## Using this tool

Run it standalone on any repo ("write an AGENT.md for this project"), or as one step
of the `agent-enablement` composite. Either way the output is a single `AGENT.md` at
the repo root. Consistency of *shape* across repos pays off — an agent that sees the
same AGENT.md layout everywhere gets productive faster — but the commands and
conventions must be true for each specific repo, or the file does active harm by
sending the agent down wrong paths.

## Reference files

- `scripts/detect_commands.py` — this tool's detector: stack + real commands
  (npm scripts / Makefile / maven-gradle / pyproject) + entry points + env/services.
  Standard-library Python, no install.
- `references/agent-md-template.md` — the AGENT.md structure to follow.
- `references/commands-by-stack.md` — typical build/test/run/lint commands per stack,
  used as a fallback when the repo doesn't define its own.
