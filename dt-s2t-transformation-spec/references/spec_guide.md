# Transformation Spec Contract

One YAML file per target table, named `<layer>.<table>.yaml`. The expression
language is ANSI SQL — never English prose in a `rule`. Prose is ambiguous;
SQL is executable. The spec must read literally with zero indirection, because
its consumers include code-generating agents that must not infer.

## File structure

```yaml
spec_version: "1.0"
target: silver.membership          # <layer>.<table>
description: >                     # one-sentence business purpose
layer: bronze -> silver
grain: one row per group_id + coverage_month   # REQUIRED
owner: data-platform
tags: []                           # optional

sources:                           # alias: layer.table — primary source first
  m: bronze.com2_membership
  g: bronze.edw_client_summary

join:                              # LEFT unless prefixed INNER/FULL
  - "g ON m.group_nbr = g.group_nbr"

filter: "m.record_status != 'D'"   # SQL WHERE fragment, optional

dedupe:                            # optional
  key: [m.group_nbr, m.coverage_month]
  order_by: "m.feed_ts DESC"       # keep first row per key by this ordering

load:
  mode: merge                      # merge | append | full_refresh | scd2
  merge_key: [group_id, coverage_month]   # required for merge/scd2
  # scd2 only: track_columns: [...], effective_from: <col>

columns: { ... }                   # see vocabulary below
tests: [ ... ]                     # table-level tests
notes: >                           # caveats, rationale, OPEN QUESTIONS
```

## Transformation type vocabulary (closed set — never add types)

| type | Meaning | Required fields |
|---|---|---|
| `direct` | Copy source column as-is (optional cast via `target_type`) | `source` |
| `expression` | SQL scalar expression over one or more columns | `source`, `rule` |
| `conditional` | CASE logic, shorthand `in -> out; in -> out; else X` | `source`, `rule` |
| `aggregate` | Aggregation; rule states fn, GROUP BY, optional WHERE | `source`, `rule` |
| `lookup` | Fetch value from reference table by key | `source`, `lookup` |
| `constant` | Hardcoded literal | `rule` |
| `system` | Runtime-generated (timestamp, batch id, hash) | `rule` |

### One example of each

```yaml
group_id:        { type: direct, source: m.group_nbr, target_type: string }

member_count:    { type: expression, source: [m.active_members, m.pended_members],
                   rule: "COALESCE(active_members,0) + COALESCE(pended_members,0)" }

segment:         { type: conditional, source: m.segment_cd,
                   rule: "'SG' -> 'Small Group'; 'LG' -> 'Large Group'; else 'Unknown'" }

total_members:   { type: aggregate, source: silver.membership.member_count,
                   rule: "SUM(member_count) GROUP BY agency_id, coverage_month" }

cancel_reason:   { type: lookup, source: m.cancel_reason_cd,
                   lookup: { table: silver.ref_cancel_reason, key: reason_cd, return: reason_desc },
                   default: null }

source_system:   { type: constant, rule: "'COM2'" }

load_ts:         { type: system, rule: "current_timestamp()" }
```

## Structural rules

1. `grain` is mandatory and every join, dedupe, and aggregate must preserve
   it. `tests.unique_combination` must list exactly the grain columns — this
   makes the grain claim machine-checkable.
2. Every target column appears exactly once under `columns`. `source` is
   required for all types except `constant`/`system`, giving column-level
   lineage for free. For `aggregate`, use the fully qualified
   `layer.table.column` form.
3. Rules are literal and self-contained: no macros, no "same as above", no
   references to another spec's logic. An agent reading one file must be able
   to generate the transformation without opening any other spec.
4. Joins are LEFT by default; prefix `INNER` or `FULL` to override. The first
   source listed is the join base.
5. `merge` and `scd2` require `merge_key`; the merge key should equal the
   grain columns.
6. `default` states the value on NULL source or lookup miss; absent means
   NULL passes through.
7. An `expression` may reference previously defined target columns (derived
   metrics) — list those columns in `source` so lineage stays complete.
8. Conditional shorthand: input values and outputs are literals; `NULL` (bare)
   matches SQL NULL; the `else` branch is required.

## Tests vocabulary

Column-level (list under the column's `tests`):
`not_null` · `unique` · `accepted_values: [...]` ·
`relationships: {to: <layer>.<table>, field: <col>}`

Table-level (list under top-level `tests`):
`unique_combination: [...]` · `row_count: {min, max}` ·
`custom_sql: "<query>"` (must return 0 rows to pass)

## Contract for a consuming agent

- Implement exactly what the spec says. If a rule is ambiguous or a required
  field is missing, stop and ask — never infer business logic.
- Generate one pipeline unit (model/job) per spec file, plus assertions from
  `tests`.
- Verify every column in `columns` is produced and no extras are added.
- Read `notes` for caveats; never invent content that belongs in `notes`.
- Derive execution order from `sources` references — they form the DAG.

## Authoring checklist (run before delivering)

- [ ] Grain stated and `unique_combination` matches it
- [ ] Every column has a valid `type` from the closed set
- [ ] No English prose in any `rule`
- [ ] `source` present everywhere except constant/system
- [ ] Load mode chosen deliberately (and merge_key set if merge/scd2)
- [ ] Known quirks and open questions written into `notes`
- [ ] `scripts/validate_spec.py` passes
