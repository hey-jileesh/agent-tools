---
name: jira-issue-reader
description: "Read and summarize a Jira issue (story / epic / task / bug / sub-task) given its key, and answer 'what changed since a date or version'. Actions: recognize the issue type; read title, description, and acceptance criteria; list fix versions; identify reporter, assignee, creator, commenters, editors, and watchers (who is involved); and parse the full change history. With a date or fix version, report exactly what changed in the issue after that point. Works with Jira Cloud (email + API token) and Jira Server / Data Center (Bearer PAT). Domains: Jira, Atlassian, issue tracking, stories, epics, tasks, bugs, acceptance criteria, changelog, sprint/release scope, requirements. Triggers: 'read JIRA-123', 'what is in PROJ-456', 'summarize this Jira story/epic', 'what's the acceptance criteria for', 'who is working on this ticket', 'what changed in PROJ-123 since last week / since version 2.1', 'show the history of this issue'. Use whenever someone references a Jira issue key or asks about a Jira story/epic/task's content, people, or history."
---

# Jira Issue Reader

Given a Jira issue key, fetch and summarize it, and answer questions about **what
changed** over time. Handles any issue type (story, epic, task, bug, sub-task).

## Configure (once, via environment)

| Variable | Meaning |
|----------|---------|
| `JIRA_URL` | Base URL — `https://<site>.atlassian.net` (Cloud) or `https://jira.company.com` (Data Center) |
| `JIRA_TOKEN` | API token (Cloud) or Personal Access Token (Data Center) |
| `JIRA_EMAIL` | Your account email — **Cloud only**. Its presence selects Basic auth + REST v3; without it the tool uses Bearer auth + REST v2 (Data Center). |

Get a Cloud API token at id.atlassian.com → Security → API tokens; a Data Center PAT
from your profile → Personal Access Tokens.

## Usage

```bash
python3 scripts/read_issue.py PROJ-123                 # full summary (JSON)
python3 scripts/read_issue.py PROJ-123 --format md     # readable markdown
python3 scripts/read_issue.py PROJ-123 --since 2025-05-01      # what changed since a date
python3 scripts/read_issue.py PROJ-123 --since-version 2.1.0   # what changed since a version was set
python3 scripts/read_issue.py --from-file issue.json   # parse a saved issue JSON (offline)
```

It prints a structured object (or markdown) with: `type`, `summary`, `status`,
`description`, `acceptance_criteria` (+ where it was found), `reporter` / `assignee` /
`creator`, `fix_versions`, `labels` / `components`, `parent` (epic), `comments`,
`people_involved` (each with their roles), and `change_history`.

## Answering "what changed?"

The change history is the issue's changelog — each entry has a timestamp, the author,
and the field-level changes (`field`, `from` → `to`). To answer a user's question:

- **"what changed since <date>?"** → run with `--since <date>` (YYYY-MM-DD or full
  ISO). The result's `changes` array holds only entries on/after that date.
- **"what changed since version <v>?"** → run with `--since-version <v>`. The tool
  finds when that fix version was set (the changelog entry where Fix Version changed to
  include it) and returns everything from that point on. If the version was never set
  in the history, it says so (empty `changes` with a note).
- **"who changed it / who's involved?"** → use `people_involved` (roles include
  reporter, assignee, creator, commenter, editor) and the per-entry `author`.

Then summarize in plain language: group the changes by field or by author, and lead
with the most significant (status, scope/description, fix version, assignee).

## Notes

- **Acceptance criteria** isn't a standard Jira field. The tool looks for a custom
  field whose name matches "Acceptance Criteria", and falls back to an
  "Acceptance Criteria" heading inside the description. If neither exists it returns
  null — say so rather than inventing criteria.
- **Epics** are read like any other issue — its own fields and changelog. Child
  stories/tasks are intentionally **out of scope**: "what changed" for an epic means
  changes to the epic itself, not a roll-up of its children.
- **Descriptions** in Jira Cloud are ADF (rich JSON); the tool flattens them to text.

## Security

The token is sent only in the `Authorization` header (never in the URL or logs); the
issue key is URL-encoded; `JIRA_URL` is checked for scheme and rejected if it carries
embedded credentials; TLS verification is on. The tool only reads (GET) — it never
modifies issues.

## Reference

- `scripts/read_issue.py` — fetch + parse + summarize; `--since` / `--since-version`
  for change queries; `--from-file` for offline parsing. Standard-library Python.
- `references/jira-api.md` — endpoints, auth, and Cloud-vs-Data-Center differences.
