# Bitbucket Data Center REST API 1.0 — endpoints used

The orchestrator targets **Bitbucket Server / Data Center**, which exposes REST
API **1.0** under `/rest/api/1.0`. (This is different from Bitbucket *Cloud*,
which uses API 2.0 under `api.bitbucket.org/2.0`. If you ever point these scripts
at Cloud, the endpoints and pagination differ — see the note at the bottom.)

All requests authenticate with an **HTTP access token** sent as a bearer token:

```
Authorization: Bearer <BITBUCKET_TOKEN>
Accept: application/json
```

## List repositories in a project

```
GET {BITBUCKET_URL}/rest/api/1.0/projects/{projectKey}/repos?limit=100&start=0
```

Paginated response envelope:

```json
{
  "size": 25,
  "limit": 100,
  "isLastPage": true,
  "start": 0,
  "nextPageStart": null,
  "values": [
    {
      "slug": "payments-service",
      "name": "Payments Service",
      "links": {
        "clone": [
          { "href": "https://bitbucket.mycorp.com/scm/plat/payments-service.git", "name": "http" },
          { "href": "ssh://git@bitbucket.mycorp.com:7999/plat/payments-service.git", "name": "ssh" }
        ],
        "self": [ { "href": "https://bitbucket.mycorp.com/projects/PLAT/repos/payments-service/browse" } ]
      }
    }
  ]
}
```

Pagination contract: keep requesting with `start = nextPageStart` until
`isLastPage` is `true`. The client (`scripts/enable_project.py`, `list_repos`) implements
exactly this loop.

Clone URL selection: prefer the link whose `name` is `http`/`https`; fall back to
the first available clone link. Switch to the `ssh` link if your automation
authenticates via SSH keys instead of token-over-HTTPS.

## Default branch of a repository

```
GET {BITBUCKET_URL}/rest/api/1.0/projects/{projectKey}/repos/{slug}/branches/default
```

```json
{ "id": "refs/heads/main", "displayId": "main", "type": "BRANCH" }
```

Used to branch `feature/agent-enablement` from the right base. Empty repositories
return an error here, which the client treats as "no default branch" (the
`default_branch` lookup is soft — it returns `None` and the code falls back to the
checked-out HEAD).

## Authentication failures

`401` (bad/expired token) and `403` (token lacks repo read, or project
permission) are treated as fatal — `api_get` stops with a clear message rather than
retrying. This is intentional: retrying an auth failure just hammers the server.

## Adjusting for a different Bitbucket version

These endpoints are stable across Bitbucket Server/DC 5.x–8.x. If your instance
differs:

- Repo listing path and pagination keys (`isLastPage`, `nextPageStart`) are the
  ones to check first.
- Older instances may require basic auth (`username:password` or
  `username:http-token`) instead of bearer tokens — change the `Authorization`
  header built in `api_get` (in `scripts/enable_project.py`) to
  `"Basic " + base64(user:token)`.

## If you are on Bitbucket Cloud instead

Cloud uses `https://api.bitbucket.org/2.0/repositories/{workspace}?q=project.key="KEY"`,
auth via app password / API token with basic auth, and a `next` URL for
pagination instead of `nextPageStart`. The client would need a Cloud variant; it
is intentionally not included here because the target is Data Center.
