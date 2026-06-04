# Jira REST API — what this tool uses

The reader fetches a single issue with its changelog, field display-names, and rendered
fields:

```
GET {JIRA_URL}/rest/api/{2|3}/issue/{KEY}?expand=changelog,names,renderedFields
```

- `changelog` → `changelog.histories[]`, each with `created`, `author`, and `items[]`
  (`field`, `fromString`, `toString`) — the source for "what changed".
- `names` → maps field IDs (e.g. `customfield_10001`) to display names, used to locate
  the "Acceptance Criteria" custom field.
- `renderedFields` → HTML-rendered values, used as a fallback for the description.

## Cloud vs Data Center

| | Jira Cloud | Jira Server / Data Center |
|--|-----------|---------------------------|
| Base URL | `https://<site>.atlassian.net` | `https://jira.company.com` |
| REST version | `3` | `2` |
| Auth | Basic: `email:api_token` (base64) | Bearer: Personal Access Token |
| Description format | ADF (rich JSON) | wiki markup / plain string |
| Selected by | `JIRA_EMAIL` is set | `JIRA_EMAIL` is unset |

Override the version with `--api-version 2|3` if your instance differs.

## Auth headers

- Cloud: `Authorization: Basic base64(email:token)`
- Data Center: `Authorization: Bearer <token>`

A `401`/`403` means the token/permissions are wrong; `404` means the key doesn't exist
or you can't see it.

## Fields of interest

| Field | Path |
|-------|------|
| Type | `fields.issuetype.name` |
| Title | `fields.summary` |
| Status | `fields.status.name` |
| Description | `fields.description` (ADF dict on Cloud, string on DC) |
| Acceptance criteria | a `customfield_*` whose `names` entry matches /acceptance criteria/i, else a heading in the description |
| Reporter / Assignee / Creator | `fields.reporter` / `fields.assignee` / `fields.creator` |
| Fix versions | `fields.fixVersions[].name` |
| Parent / Epic | `fields.parent` |
| Comments | `fields.comment.comments[]` (author, created, body) |

## Scope

- Each issue is read on its own — including epics. Child stories/tasks of an epic are
  **out of scope** by design (no roll-up).
- **Watchers** are an optional separate call (`GET /rest/api/{v}/issue/{KEY}/watchers`)
  and are not fetched.
